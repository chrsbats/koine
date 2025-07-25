import re
from bisect import bisect_right
import json
import ast
from functools import reduce
from operator import getitem
from pathlib import Path
import yaml
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor
from parsimonious.expressions import Literal, Quantifier, Lookahead
from parsimonious.exceptions import ParseError, IncompleteParseError, LeftRecursionError, VisitationError

# ==============================================================================
# 0. LEXER
# ==============================================================================
class Token:
    """A simple token container."""
    def __init__(self, type, value, line, col):
        self.type = type
        self.value = value
        self.line = line
        self.col = col
    def __repr__(self):
        return f"Token({self.type}, '{self.value}', L{self.line}:C{self.col})"

class StatefulLexer:
    """
    A stateful lexer that handles tokenizing text, including indentation-based
    syntax.
    """
    def __init__(self, lexer_config: dict, tab_width=8):
        self.token_specs = lexer_config.get('tokens', [])
        self.tab_width = tab_width
        # Compile regexes for efficiency
        self.compiled_specs = []
        for spec in self.token_specs:
            self.compiled_specs.append(
                (re.compile(spec['regex']), spec.get('action'), spec.get('token'))
            )
        self.handles_indentation = any(
            spec.get('action') == 'handle_indent' for spec in self.token_specs
        )

    def tokenize(self, text: str) -> list[Token]:
        # The caller is responsible for stripping any unwanted leading/trailing whitespace.
        text = text.expandtabs(self.tab_width)
        tokens = []
        indent_stack = [0]
        line_num = 1
        line_start = 0
        pos = 0

        while pos < len(text):
            longest_match, best_spec = None, None
            for regex, action, token_type in self.compiled_specs:
                match = regex.match(text, pos)
                if match and (longest_match is None or len(match.group(0)) > len(longest_match.group(0))):
                    longest_match, best_spec = match, (action, token_type)

            if longest_match:
                value = longest_match.group(0)
                action, token_type = best_spec
                
                col = pos - line_start + 1

                if action == 'handle_indent':
                    # This is a newline token, value is like "\n    "
                    # We don't emit a token for the newline itself.
                    indent_level = len(value) - 1 # Length of whitespace after '\n'
                    
                    if indent_level > indent_stack[-1]:
                        indent_stack.append(indent_level)
                        tokens.append(Token('INDENT', '', line_num + 1, 1))
                    
                    while indent_level < indent_stack[-1]:
                        indent_stack.pop()
                        tokens.append(Token('DEDENT', '', line_num + 1, 1))
                    
                    if indent_level != indent_stack[-1]:
                        raise IndentationError(f"Indentation error at L{line_num+1}")
                
                elif action != 'skip':
                    tokens.append(Token(token_type, value, line_num, col))
                
                # Update line and column counters
                newlines = value.count('\n')
                if newlines > 0:
                    line_num += newlines
                    line_start = pos + value.rfind('\n') + 1
                
                pos = longest_match.end()
            else:
                col = pos - line_start + 1
                raise SyntaxError(f"Unexpected character at L{line_num}:C{col}: '{text[pos]}'")

        # At end of file, dedent all remaining levels
        if self.handles_indentation:
            while len(indent_stack) > 1:
                indent_stack.pop()
                tokens.append(Token('DEDENT', '', line_num, 1))
            
        return tokens

# ==============================================================================
# 1. GRAMMAR-TO-STRING TRANSPILER
# ==============================================================================

def transpile_rule(rule_definition, is_token_grammar=False):
    """Recursively transpiles a single rule dictionary into a Parsimonious grammar string component."""
    if not isinstance(rule_definition, dict):
        raise ValueError(f"Rule definition must be a dictionary, got {type(rule_definition)}")

    rule_keys = {
        'literal', 'regex', 'rule', 'choice', 'sequence',
        'zero_or_more', 'one_or_more', 'optional', 'token',
        'positive_lookahead', 'negative_lookahead'
    }
    found_keys = [key for key in rule_definition if key in rule_keys]

    if len(found_keys) != 1:
        raise ValueError(f"Rule must have exactly one key from {rule_keys}, found {found_keys} in {rule_definition}")

    rule_type, value = found_keys[0], rule_definition[found_keys[0]]

    if rule_type == 'token':
        return value
    elif rule_type in ['literal', 'regex'] and is_token_grammar:
        raise ValueError(f"'{rule_type}' is not supported when a lexer is defined. Use 'token' instead.")
    elif rule_type == 'literal':
        escaped_value = value.replace("\"", "\\\"")
        return f'"{escaped_value}"'
    elif rule_type == 'regex':
        return f'~r"{value}"'
    elif rule_type == 'rule':
        return value
    elif rule_type in ['choice', 'sequence']:
        if not value:
            return '("")?' if rule_type == 'sequence' else (_ for _ in ()).throw(ValueError("Choice cannot be empty"))
        parts = [transpile_rule(part, is_token_grammar) for part in value]
        joiner = " / " if rule_type == 'choice' else " "
        return f'({joiner.join(parts)})'
    else:  # Quantifiers and lookaheads
        # Postfix operators
        if rule_type in ['zero_or_more', 'one_or_more', 'optional']:
            op_map = {'zero_or_more': '*', 'one_or_more': '+', 'optional': '?'}
            return f"({transpile_rule(value, is_token_grammar)}){op_map[rule_type]}"
        # Prefix operators
        else:  # positive_lookahead, negative_lookahead
            op_map = {'positive_lookahead': '&', 'negative_lookahead': '!'}
            return f"{op_map[rule_type]}({transpile_rule(value, is_token_grammar)})"

def transpile_grammar(grammar_dict):
    """Takes a full grammar dictionary and transpiles it into a single grammar string."""
    if 'rules' not in grammar_dict:
        raise ValueError("Grammar definition must have a 'rules' key.")
    
    is_token_grammar = 'lexer' in grammar_dict
    grammar_lines = [f"{name} = {transpile_rule(rule, is_token_grammar)}" for name, rule in grammar_dict['rules'].items()]
    
    if is_token_grammar:
        token_types = {spec['token'] for spec in grammar_dict['lexer']['tokens'] if 'token' in spec}
        token_types.update(['INDENT', 'DEDENT'])
        for token_type in token_types:
            # Match the token name and consume any trailing whitespace that separates it
            grammar_lines.append(f'{token_type} = ~r"{token_type}\\s*"')

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
# 3. PARSE-TREE-TO-AST VISITOR
# ==============================================================================
class AstBuilderVisitor(NodeVisitor):
    def __init__(self, grammar_dict: dict, finder: LineColumnFinder, tokens: list[Token] = None):
        self.grammar_dict = grammar_dict
        self.grammar_rules = grammar_dict['rules']
        self.finder = finder
        self.tokens = tokens
        self.token_idx = 0
        self.token_rule_names = set()
        if self.tokens:
            lexer_tokens = {spec['token'] for spec in grammar_dict['lexer']['tokens'] if 'token' in spec}
            lexer_tokens.update(['INDENT', 'DEDENT'])
            self.token_rule_names = lexer_tokens

    def get_pos(self, node, children):
        if self.tokens:
            if children:
                for child in children:
                    if isinstance(child, dict) and 'line' in child: return child['line'], child['col']
            return 1, 1
        return self.finder.find(node.start)

    def generic_visit(self, node, visited_children):
        rule_name = node.expr_name

        if self.tokens and rule_name in self.token_rule_names:
            if self.token_idx < len(self.tokens):
                token = self.tokens[self.token_idx]
                self.token_idx += 1

                spec_ast = {}
                for spec in self.grammar_dict.get('lexer', {}).get('tokens', []):
                    if spec.get('token') == token.type:
                        spec_ast = spec.get('ast', {})
                        break
                # If the token's own spec says to discard, skip it.
                if spec_ast.get('discard'):
                    return None

                base_node = {"tag": token.type,
                             "text": token.value,
                             "line": token.line,
                             "col": token.col}

                if spec_ast.get('type') == 'number':
                    val = float(token.value)
                    base_node['value'] = int(val) if val.is_integer() else val
                else:
                    base_node['value'] = token.value
                return base_node
            return None

        if rule_name not in self.grammar_rules:
            if isinstance(node.expr, Lookahead) or not visited_children: return None
            if isinstance(node.expr, Quantifier) and node.expr.max == 1: return visited_children[0]
            if isinstance(node.expr, Literal) and not self.tokens:
                line, col = self.finder.find(node.start)
                return {"tag": "literal", "text": node.text, "line": line, "col": col} if node.text else None
            return [c for c in visited_children if c is not None]

        rule_def = self.grammar_rules.get(rule_name, {})
        ast_config = rule_def.get('ast', {})
        if ast_config.get('discard'): return None
        
        children = [c for c in visited_children if c is not None]

        if ast_config.get('leaf') or (not self.tokens and ('literal' in rule_def or 'regex' in rule_def)):
            line, col = self.get_pos(node, children)
            base_node = {"tag": ast_config.get('tag', rule_name), "text": node.text, "line": line, "col": col}
            if ast_config.get('type') == 'number':
                val = float(node.text)
                base_node['value'] = int(val) if val.is_integer() else val
            elif ast_config.get('type') == 'bool': base_node['value'] = node.text.lower() == 'true'
            elif ast_config.get('type') == 'null': base_node['value'] = None
            return base_node

        if ast_config.get('promote'):
            if not children: return None

            # If a choice was promoted, its results might be in a nested list
            if len(children) == 1 and isinstance(children[0], list):
                children = children[0]

            # Special case for `( expression )` style rules.
            if len(children) == 3 and \
               isinstance(children[0], dict) and children[0].get('tag') == 'literal' and \
               isinstance(children[2], dict) and children[2].get('tag') == 'literal':
                return children[1]

            if len(children) > 1:
                return children
            return children[0] if children else None

        structure_config = ast_config.get('structure')
        if isinstance(structure_config, str):
            if structure_config == 'left_associative_op':
                left = children[0]
                if len(children) < 2:
                    return left
                for group in children[1]:
                    clean_group = [item for item in group if item is not None]
                    if not clean_group: continue
                    op, right = clean_group[0], clean_group[1]
                    new_node = {"tag": "binary_op", "op": op, "left": left, "right": right, "line": op['line'], "col": op['col']}
                    left = new_node
                return left
            elif structure_config == 'right_associative_op':
                left = children[0]
                if len(children) < 2 or not children[1]: return left
                op_and_right_list = [item for item in children[1] if item is not None]
                if not op_and_right_list: return left
                op, right = op_and_right_list[0], op_and_right_list[1]
                new_node = {"tag": "binary_op", "op": op, "left": left, "right": right, "line": op['line'], "col": op['col']}
                return new_node
        elif isinstance(structure_config, dict):
            line, col = self.get_pos(node, children)
            new_node = {
                "tag": structure_config.get('tag', rule_name),
                "text": node.text,
                "line": line,
                "col": col,
                "children": {}
            }
            map_children_config = structure_config.get('map_children', {})
            # The direct children from the sequence are in a nested list.
            # Only unwrap **when it is the single element**, otherwise keep the
            # full list so we don't accidentally drop siblings that follow.
            child_nodes = visited_children[0] if len(visited_children) == 1 and isinstance(visited_children[0], list) else visited_children
            # A filtered view that omits placeholders such as None or empty lists.
            filtered_nodes = [c for c in child_nodes if c not in (None, [])]

            for name, mapping in map_children_config.items():
                idx = mapping['from_child']

                # Try to pick the element at the same ordinal position, but
                # fall-forward until we hit the next real node.  This makes
                # the mapping robust when optional / discarded parts are
                # omitted, so the remaining children “collapse” leftward.
                selected = None
                scan_idx = idx
                while scan_idx < len(child_nodes):
                    cand = child_nodes[scan_idx]
                    if cand not in (None, []):
                        selected = cand
                        break
                    scan_idx += 1

                if selected not in (None, []):
                    new_node['children'][name] = selected
            return new_node

        # Default node creation
        line, col = self.get_pos(node, children)
        base_node = {"tag": ast_config.get('tag', rule_name), "text": node.text, "line": line, "col": col}
        
        named_children = {}
        sequence_def = rule_def.get('sequence', [])
        
        child_producing_parts = []
        for part in sequence_def:
            is_lookahead = 'positive_lookahead' in part or 'negative_lookahead' in part
            if is_lookahead:
                continue

            is_discarded = False
            if 'ast' in part and part['ast'].get('discard'):
                is_discarded = True
            elif 'rule' in part:
                # If it's a rule reference, we must look up that rule's definition.
                ref_rule_def = self.grammar_rules.get(part['rule'], {})
                if ref_rule_def.get('ast', {}).get('discard'):
                    is_discarded = True

            if not is_discarded:
                child_producing_parts.append(part)

        # When children are from a sequence they are often in a nested list
        unwrapped_children = children[0] if (children and isinstance(children[0], list) and len(children) == 1) else children

        for i, part in enumerate(child_producing_parts):
            if 'ast' in part and 'name' in part['ast']:
                child_name = part['ast']['name']
                if i < len(children):
                    named_children[child_name] = children[i]
                else: # Handle optional named children that didn't match
                    named_children[child_name] = []
        
        if named_children:
             base_node['children'] = named_children
        elif children is None or not children:
             base_node['children'] = []
        else:
             base_node['children'] = unwrapped_children

        return base_node

# ==============================================================================
# 4. AST-TO-STRING TRANSPILER
# ==============================================================================
class Transpiler:
    def __init__(self, transpile_grammar: dict = None):
        if transpile_grammar is None:
            transpile_grammar = {}
        transpiler_config = transpile_grammar.get('transpiler', {})
        self.transpile_rules = transpile_grammar.get('rules', {})
        self.indent_str = transpiler_config.get('indent', '    ')
        self.indent_level = 0
        self.state = {}

    def _get_path(self, path: str):
        try:
            return reduce(getitem, path.split('.'), self.state)
        except (KeyError, TypeError):
            return None

    def _set_path(self, path: str, value):
        keys = path.split('.')
        d = self.state
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value

    def _resolve_path_in_context(self, path: str, context: dict):
        """Resolves a dot-notation path against a context dictionary."""
        try:
            return reduce(getitem, path.split('.'), context)
        except (KeyError, TypeError, AttributeError):
            return None

    def _evaluate_condition(self, condition_dict: dict, context: dict) -> bool:
        """Evaluates a condition defined as a dictionary."""
        if 'path' not in condition_dict:
            raise ValueError(f"Condition must have a 'path' key: {condition_dict}")

        path_template = condition_dict['path']
        path = path_template.format(**context)
        actual_val = self._resolve_path_in_context(path, context)

        result = False
        if 'equals' in condition_dict:
            # Equality check
            expected_val = condition_dict['equals']
            result = str(actual_val) == str(expected_val)
        else:
            # Existence check
            result = bool(actual_val)

        if condition_dict.get('negate', False):
            return not result
        return result

    def transpile(self, node: dict) -> str:
        if not isinstance(node, dict) or 'tag' not in node:
            raise ValueError("Transpilation must start from a valid AST node.")
        self.indent_level = 0
        self.state = {}
        out = self._transpile_node(node)
        return out

    def _transpile_node(self, node):
        if isinstance(node, list):
            return " ".join(self._transpile_node(n) for n in node if n not in (None, []))

        if not isinstance(node, dict):
            return str(node or "")
        
        transpile_config = self.transpile_rules.get(node.get('tag'), {})
        
        if transpile_config.get('indent'): self.indent_level += 1
        
        output = ""
        current_indent = self.indent_str * self.indent_level

        # Prepare substitutions once for use in conditions, templates, and state_set
        subs = {}
        children = node.get('children', [])
        if isinstance(children, dict):
            for name, child in children.items(): subs[name] = self._transpile_node(child)
        elif isinstance(children, list):
            joiner = transpile_config.get('join_children_with', ' ')
            if '\n' in joiner:
                joiner = joiner.replace('\n', '\n' + current_indent)
            child_strings = [self._transpile_node(c) for c in children]
            child_strings = [s for s in child_strings if s]  # drop blanks
            joined = joiner.join(child_strings)
            if transpile_config.get('indent') and joined:
                joined = current_indent + joined
            subs['children'] = joined
        
        if 'op' in node: subs['op'] = self._transpile_node(node['op'])
        if 'left' in node: subs['left'] = self._transpile_node(node['left'])
        if 'right' in node: subs['right'] = self._transpile_node(node['right'])

        template = None
        # Check for the new 'cases' structure first.
        if 'cases' in transpile_config:
            # The full context for evaluation has access to the raw node, state, and transpiled children
            context = {'node': node, 'state': self.state, **subs}
            
            for case in transpile_config['cases']:
                if 'if' in case:
                    if self._evaluate_condition(case['if'], context):
                        template = case['then']
                        break
                elif 'default' in case:
                    template = case['default']
                    break
        elif 'template' in transpile_config:
            template = transpile_config['template']
        
        if template is not None:
            output = template.format(**subs)
        elif transpile_config.get('use') == 'value': output = str(node.get('value', ''))
        elif transpile_config.get('use') == 'text': output = node['text']
        elif 'value' in transpile_config:
            output = transpile_config['value']
        else:
            if 'value' in node:
                output = str(node['value'])
            elif 'text' in node:
                output = node['text']
            else:
                raise ValueError(f"Don't know how to transpile node: {node}")
        
        # After producing output, update state for subsequent nodes.
        if 'state_set' in transpile_config:
            for key_template, value in transpile_config['state_set'].items():
                final_key = key_template.format(**subs)
                final_value = value
                if isinstance(value, str):
                    final_value = value.format(**subs)
                self._set_path(final_key, final_value)

        if transpile_config.get('indent'):
            self.indent_level -= 1
        return output

# ==============================================================================
# 5. MAIN PARSER CLASS
# ==============================================================================

class Parser:
    """The main entry point that orchestrates the parsing process."""
    @classmethod
    def from_file(cls, filepath: str):
        """Loads a grammar from a main YAML file, processing `includes` directives."""
        
        def load_and_merge(file_path_obj: Path):
            current_dir = file_path_obj.parent
            with open(file_path_obj, 'r') as f:
                grammar = yaml.safe_load(f) or {}

            final_rules = {}

            if 'includes' in grammar:
                for include_file in grammar['includes']:
                    # Resolve include path relative to the CURRENT file's path
                    include_path = current_dir / include_file
                    included_grammar = load_and_merge(include_path)
                    final_rules.update(included_grammar.get('rules', {}))
                del grammar['includes']
            
            final_rules.update(grammar.get('rules', {}))
            grammar['rules'] = final_rules
            
            return grammar

        final_grammar = load_and_merge(Path(filepath))
        return cls(final_grammar)

    def __init__(self, grammar_dict: dict):
        self.grammar_dict = self._normalize_grammar(grammar_dict)
        self._lint_grammar()
        self.is_token_grammar = 'lexer' in self.grammar_dict
        
        if self.is_token_grammar:
            self.lexer = StatefulLexer(self.grammar_dict['lexer'])
        
        self.grammar_string = transpile_grammar(self.grammar_dict)
        try:
            self.grammar = Grammar(self.grammar_string)
        except (LeftRecursionError, VisitationError) as e:
            raise ValueError(f"Left-recursion detected in grammar. Parsimonious error: {e}")
        self.start_rule = self.grammar_dict.get('start_rule', 'start')
        
        # For richer error messages
        self.expression_map = {self.grammar[k]: k for k in self.grammar_dict['rules']}

    def _lint_grammar(self):
        """
        Performs static analysis on the grammar to find common issues like
        unreachable rules.
        """
        self._check_for_unreachable_rules()

    def _check_for_unreachable_rules(self):
        """
        Checks for rules that are defined in the grammar but can never be
        reached from the start_rule.
        """
        all_rules = set(self.grammar_dict['rules'].keys())
        start_rule = self.grammar_dict.get('start_rule', 'start')
        if start_rule not in all_rules:
            # This will be caught later by parsimonious, but it prevents
            # the linter from running on an invalid start_rule.
            return

        def find_references(rule_def):
            """Recursively find all rule references in a definition."""
            refs = set()
            if isinstance(rule_def, dict):
                if 'rule' in rule_def:
                    refs.add(rule_def['rule'])
                for value in rule_def.values():
                    refs.update(find_references(value))
            elif isinstance(rule_def, list):
                for item in rule_def:
                    refs.update(find_references(item))
            return refs

        reachable = set()
        queue = [start_rule]
        
        while queue:
            current_rule = queue.pop(0)
            if current_rule in reachable:
                continue
            
            reachable.add(current_rule)
            
            if current_rule not in self.grammar_dict['rules']:
                # This indicates a reference to a non-existent rule.
                # Parsimonious will catch this with a better error message,
                # so we can ignore it here.
                continue

            rule_definition = self.grammar_dict['rules'][current_rule]
            references = find_references(rule_definition)
            
            for ref in references:
                if ref not in reachable:
                    queue.append(ref)
        
        unreachable = all_rules - reachable
        if unreachable:
            raise ValueError(f"Unreachable rules detected: {', '.join(sorted(list(unreachable)))}")

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
                'one_or_more', 'optional', 'positive_lookahead', 'negative_lookahead',
                'token'            # allow inline token defs with their own ast block
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
        finder = LineColumnFinder(text)
        
        try:
            if self.is_token_grammar:
                tokens = self.lexer.tokenize(text)
                token_string = " ".join([t.type for t in tokens])
                visitor = AstBuilderVisitor(self.grammar_dict, finder, tokens)
                tree = self.grammar[start_rule].parse(token_string)
            else:
                visitor = AstBuilderVisitor(self.grammar_dict, finder)
                tree = self.grammar[start_rule].parse(text)
            
            ast = visitor.visit(tree)
            return {"status": "success", "ast": ast}

        except (ParseError, IncompleteParseError, SyntaxError, IndentationError) as e:
            if isinstance(e, (ParseError, IncompleteParseError)) and self.is_token_grammar:
                # Find the token corresponding to the error position in the token string
                error_token = None
                
                # Find which token index corresponds to the character position of the error
                error_token_idx = len(token_string[:e.pos].split(' ')) - 1
                
                if error_token_idx < len(tokens):
                    error_token = tokens[error_token_idx]
                    line, col = error_token.line, error_token.col
                    message = f"Syntax error at L{line}:C{col} near '{error_token.value}'. Unexpected token: {error_token.type}."
                else:
                    message = "Syntax error at end of input."
                
                return {"status": "error", "message": message}
            elif isinstance(e, (ParseError, IncompleteParseError)):
                line, col = finder.find(e.pos)
                
                if isinstance(e, IncompleteParseError):
                    snippet = text[e.pos:e.pos+20].split('\n')[0]
                    message = f"Syntax error at L{line}:C{col}. Failed to consume entire input. Unconsumed input begins with: '{snippet}...'"
                else: # It's a ParseError
                    expected_things = set()
                    if hasattr(e, 'exprs'):
                        for expr in e.exprs:
                            if expr in self.expression_map:
                                expected_things.add(self.expression_map[expr])
                            elif isinstance(expr, Literal) and expr.literal:
                                expected_things.add(f'literal "{expr.literal}"')
                    
                    snippet = text[e.pos:e.pos+20].split('\n')[0]
                    message = f"Syntax error at L{line}:C{col}"
                    if snippet:
                        message += f" near '{snippet}...'"
                    
                    if expected_things:
                        message += f". Expected one of: {', '.join(sorted(list(expected_things)))}."
                    elif not snippet:
                        message += ". Unexpected end of input."

                return {"status": "error", "message": message}
            else: # SyntaxError or IndentationError from our lexer
                 return {"status": "error", "message": str(e)}

    def validate(self, text: str):
        result = self.parse(text)
        if result['status'] == 'success':
            return True, 'success'
        else:
            return False, result['message']
