from bisect import bisect_right
import json
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor
from parsimonious.expressions import Literal, Quantifier, Lookahead
from parsimonious.exceptions import ParseError, IncompleteParseError

# ==============================================================================
# 1. GRAMMAR-TO-STRING TRANSPILER
# ==============================================================================

def transpile_rule(rule_definition):
    """Recursively transpiles a single rule dictionary into a Parsimonious grammar string component."""
    if not isinstance(rule_definition, dict):
        raise ValueError(f"Rule definition must be a dictionary, got {type(rule_definition)}")

    rule_keys = {
        'literal', 'regex', 'rule', 'choice', 'sequence',
        'zero_or_more', 'one_or_more', 'optional',
        'positive_lookahead', 'negative_lookahead'
    }
    found_keys = [key for key in rule_definition if key in rule_keys]

    if len(found_keys) != 1:
        raise ValueError(f"Rule definition must contain exactly one type key from {rule_keys}, but found {len(found_keys)}: {found_keys} in {rule_definition}")

    rule_type = found_keys[0]
    value = rule_definition[rule_type]

    if rule_type == 'literal':
        escaped_value = value.replace('"', '\\"')
        return f'"{escaped_value}"'
    elif rule_type == 'regex':
        return f'~r"{value}"'
    elif rule_type == 'rule':
        return value
    elif rule_type == 'choice':
        if not value:
            raise ValueError("A 'choice' rule must have at least one alternative.")
        parts = [transpile_rule(part) for part in value]
        return f'({" / ".join(parts)})'
    elif rule_type == 'sequence':
        if not value:
            return '""'
        parts = [transpile_rule(part) for part in value]
        return f'({" ".join(parts)})'
    elif rule_type == 'zero_or_more':
        return f"({transpile_rule(value)})*"
    elif rule_type == 'one_or_more':
        return f"({transpile_rule(value)})+"
    elif rule_type == 'optional':
        return f"({transpile_rule(value)})?"
    elif rule_type == 'positive_lookahead':
        return f"&({transpile_rule(value)})"
    elif rule_type == 'negative_lookahead':
        return f"!({transpile_rule(value)})"

def transpile_grammar(grammar_dict):
    """Takes a full grammar dictionary and transpiles it into a single grammar string."""
    if 'rules' not in grammar_dict:
        raise ValueError("Grammar definition must have a 'rules' key.")
    grammar_lines = [f"{name} = {transpile_rule(rule)}" for name, rule in grammar_dict['rules'].items()]
    return "\n".join(grammar_lines)

# ==============================================================================
# 2. POSITION FINDER UTILITY
# ==============================================================================

class LineColumnFinder:
    """A utility to find the line and column of a character offset in a text."""
    def __init__(self, text: str):
        self.text = text
        self.line_starts = [0]
        for i, char in enumerate(text):
            if char == '\n':
                self.line_starts.append(i + 1)

    def find(self, offset: int) -> tuple[int, int]:
        """Returns (line, column) for a given character offset."""
        if offset < 0:
            offset = 0
        if offset > len(self.text):
            offset = len(self.text)

        line_num = bisect_right(self.line_starts, offset)
        # line_num is 1-based. self.line_starts is 0-indexed.
        col_num = offset - self.line_starts[line_num - 1] + 1
        return line_num, col_num


# ==============================================================================
# 3. PARSE-TREE-TO-AST VISITOR (Final, Definitive, Corrected Version)
# ==============================================================================
class AstBuilderVisitor(NodeVisitor):
    def __init__(self, grammar_dict: dict, finder: LineColumnFinder):
        self.grammar_rules = grammar_dict['rules']
        self.finder = finder

    def generic_visit(self, node, visited_children):
        rule_name = node.expr_name
        if rule_name not in self.grammar_rules:
            if isinstance(node.expr, Literal):
                if not node.text:
                    return []
                line, col = self.finder.find(node.start)
                return { "tag": "literal", "text": node.text, "line": line, "col": col }
            if isinstance(node.expr, Lookahead):
                return None
            if isinstance(node.expr, Quantifier):
                if not visited_children:
                    return None
                if node.expr.max == 1:
                    return visited_children[0]
            # For other anonymous nodes (sequences, choices), filter out discarded children
            return [c for c in visited_children if c is not None]
        
        rule_def = self.grammar_rules.get(rule_name, {})
        ast_config = rule_def.get('ast', {})
        if ast_config.get('discard'): return None
        
        children = [c for c in visited_children if c is not None]
        
        # Treat rules that directly wrap a terminal as leaves, even if `leaf: true` isn't specified.
        is_simple_terminal_rule = 'literal' in rule_def or 'regex' in rule_def
        if ast_config.get('leaf') or is_simple_terminal_rule:
            line, col = self.finder.find(node.start)
            base_node = {"tag": ast_config.get('tag', rule_name), "text": node.text, "line": line, "col": col}
            if ast_config.get('type') == 'number':
                val = float(node.text)
                base_node['value'] = int(val) if val.is_integer() else val
            elif ast_config.get('type') == 'bool':
                base_node['value'] = node.text.lower() == 'true'
            elif ast_config.get('type') == 'null':
                base_node['value'] = None
            return base_node
        
        if ast_config.get('promote'):
            promoted_item = children[0] if children else None
            # Special case to handle `( expression )` style rules, which create a list of 3 nodes.
            # We check for surrounding literals to avoid accidentally grabbing the wrong element
            # from a different kind of list.
            if isinstance(promoted_item, list) and len(promoted_item) == 3 and \
               isinstance(promoted_item[0], dict) and promoted_item[0].get('tag') == 'literal' and \
               isinstance(promoted_item[2], dict) and promoted_item[2].get('tag') == 'literal':
                return promoted_item[1]
            return promoted_item
        
        structure_type = ast_config.get('structure')
        if structure_type == 'left_associative_op':
            left = children[0]
            if len(children) < 2:
                return left
            for group in children[1]:
                clean_group = [item for item in group if item is not None]
                op, right = clean_group[0], clean_group[1]
                left = {"tag": "binary_op", "op": op, "left": left, "right": right, "line": op['line'], "col": op['col']}
            return left
        elif structure_type == 'right_associative_op':
            left = children[0]
            if len(children) < 2 or not children[1]: return left
            op_and_right_list = [item for item in children[1] if item is not None]
            if not op_and_right_list: return left
            op, right = op_and_right_list[0], op_and_right_list[1]
            return {"tag": "binary_op", "op": op, "left": left, "right": right, "line": op['line'], "col": op['col']}
        
        line, col = self.finder.find(node.start)
        base_node = {"tag": ast_config.get('tag', rule_name), "text": node.text, "line": line, "col": col}
        
        
        named_children = {}
        sequence_def = rule_def.get('sequence', [])
        
        child_producing_parts = []
        for part in sequence_def:
            is_lookahead = 'positive_lookahead' in part or 'negative_lookahead' in part
            
            
            is_discarded = False
            if 'ast' in part and part['ast'].get('discard'):
                is_discarded = True
            elif 'rule' in part:
                # If it's a rule reference, we must look up that rule's definition.
                ref_rule_def = self.grammar_rules.get(part['rule'], {})
                if ref_rule_def.get('ast', {}).get('discard'):
                    is_discarded = True

            if not is_lookahead and not is_discarded:
                child_producing_parts.append(part)

        for i, part in enumerate(child_producing_parts):
            if 'ast' in part and 'name' in part['ast']:
                if i < len(children):
                    named_children[part['ast']['name']] = children[i]
        
        base_node['children'] = named_children if named_children else children
        return base_node

# ==============================================================================
# 4. AST-TO-STRING TRANSPILER
# ==============================================================================
class Transpiler:
    def __init__(self, grammar_dict: dict):
        self.grammar_rules = grammar_dict['rules']
    def transpile(self, node: dict) -> str:
        if not isinstance(node, dict) or 'tag' not in node:
            raise ValueError("Transpilation must start from a valid AST node.")
        return self._transpile_node(node)
    def _transpile_node(self, node):
        if node is None: return "None"
        if not isinstance(node, dict): return str(node)
        tag = node.get('tag')
        if not tag: raise ValueError(f"AST node is missing a 'tag': {node}")
        if tag == 'binary_op':
            op = self._transpile_node(node['op'])
            left = self._transpile_node(node['left'])
            right = self._transpile_node(node['right'])
            return f"({op} {left} {right})"
        
        rule_def = None
        if tag in self.grammar_rules:
            rule_def = self.grammar_rules[tag]
        else:
            for rule in self.grammar_rules.values():
                if rule.get('ast', {}).get('tag') == tag:
                    rule_def = rule
                    break
        if rule_def is None:
            raise ValueError(f"AST node with tag '{tag}' does not correspond to any grammar rule.")
        
        transpile_config = rule_def.get('transpile', {})
        if 'template' in transpile_config:
            substitutions = {name: self._transpile_node(child_node) for name, child_node in node.get('children', {}).items()}
            return transpile_config['template'].format(**substitutions)
        if transpile_config.get('use') == 'value': return str(node['value'])
        if transpile_config.get('use') == 'text': return node['text']
        if 'value' in transpile_config: return transpile_config['value']
        if 'choice' in rule_def:
            for choice in rule_def['choice']:
                if choice.get('literal') == node['text']:
                    choice_transpile_config = choice.get('transpile', {})
                    if 'value' in choice_transpile_config: return choice_transpile_config['value']
            raise ValueError(f"Could not find a transpile rule for text '{node['text']}' in rule '{tag}'")
        raise ValueError(f"Don't know how to transpile node with tag '{tag}': {node}")

# ==============================================================================
# 5. MAIN PARSER CLASS
# ==============================================================================

class Parser:
    """The main entry point that orchestrates the parsing process."""
    def __init__(self, grammar_dict: dict):
        self.grammar_dict = self._normalize_grammar(grammar_dict)
        self.grammar_string = transpile_grammar(self.grammar_dict)
        self.grammar = Grammar(self.grammar_string)
        self.start_rule = self.grammar_dict.get('start_rule', 'start')
        self.transpiler = Transpiler(self.grammar_dict)

    def _normalize_grammar(self, grammar_dict: dict):
        """
        Recursively walks the grammar and gives names to any anonymous
        (inline) rule definitions that have an `ast` block. This is
        necessary so that the AstBuilderVisitor can find the `ast` config
        for these rules by name.
        """
        # Deep copy to avoid modifying the user's original dict
        new_grammar = json.loads(json.dumps(grammar_dict))
        rules = new_grammar.get('rules', {})
        anon_counter = 0

        def is_inline_def_with_ast(d):
            if not isinstance(d, dict) or 'ast' not in d:
                return False

            # An inline definition that ONLY specifies a name is for structuring the parent,
            # not for creating a new named anonymous rule.
            if list(d['ast'].keys()) == ['name']:
                return False
            
            # An inline definition cannot be a rule reference.
            if 'rule' in d:
                return False

            rule_keys = {
                'literal', 'regex', 'choice', 'sequence', 'zero_or_more', 
                'one_or_more', 'optional', 'positive_lookahead', 'negative_lookahead'
            }
            # It must contain one of the core grammar keys.
            return any(key in d for key in rule_keys)

        def walker(node):
            nonlocal anon_counter
            if isinstance(node, list):
                for i, item in enumerate(node):
                    if is_inline_def_with_ast(item):
                        anon_counter += 1
                        new_rule_name = f"__koine_anon_{anon_counter}"
                        rules[new_rule_name] = item
                        node[i] = {'rule': new_rule_name}
                    else:
                        walker(item)
            elif isinstance(node, dict):
                for key, value in list(node.items()):
                    if key in ['ast', 'transpile']:
                        continue
                    
                    if is_inline_def_with_ast(value):
                        anon_counter += 1
                        new_rule_name = f"__koine_anon_{anon_counter}"
                        rules[new_rule_name] = value
                        node[key] = {'rule': new_rule_name}
                    else:
                        walker(value)

        # Start walking from inside each of the top-level rule definitions
        rules_map = new_grammar.get('rules', {})
        for rule_def in list(rules_map.values()):
            walker(rule_def)
        return new_grammar

    def parse(self, text: str, rule: str = None):
        start_rule = rule if rule is not None else self.start_rule
        try:
            finder = LineColumnFinder(text)
            visitor = AstBuilderVisitor(self.grammar_dict, finder)
            tree = self.grammar[start_rule].parse(text)
            ast = visitor.visit(tree)
            return {"status": "success", "ast": ast}
        except (ParseError, IncompleteParseError) as e:
            # Clamp the error position to [0, len(text)]
            pos = e.pos
            if pos < 0:
                pos = 0
            if pos > len(text):
                pos = len(text)
            line, col = finder.find(pos)

            if pos >= len(text):
                message = f"Syntax error at L{line}:C{col}. Unexpected end of input"
            else:
                snippet = text[pos:pos+10]
                if len(snippet) > 10:
                    snippet = snippet[:10] + '...'
                message = f"Syntax error at L{line}:C{col}. Unexpected input '{snippet}'"

            return {"status": "error", "message": message}

    def validate(self, text: str):
        result = self.parse(text)
        if result['status'] == 'success':
            return True, 'success'
        else:
            return False, result['message']

    def transpile(self, text: str, rule: str = None):
        result = self.parse(text, rule=rule)
        if result['status'] == 'success':
            output_code = self.transpiler.transpile(result['ast'])
            return {"status": "success", "translation": output_code}
        else:
            return result
