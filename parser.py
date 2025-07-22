import json
import yaml
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor
from parsimonious.exceptions import ParseError

# ==============================================================================
# The Transpiler (Now Simpler and Correct)
# ==============================================================================

def transpile_rule(rule_definition):
    """Recursively transpiles a single rule dictionary into a string component."""
    if not isinstance(rule_definition, dict):
        raise ValueError(f"Rule definition must be a dictionary, got {type(rule_definition)}")

    rule_keys = {'literal', 'regex', 'rule', 'choice', 'sequence', 'zero_or_more', 'one_or_more'}
    found_keys = [key for key in rule_definition if key in rule_keys]

    if len(found_keys) != 1:
        raise ValueError(f"Rule definition must contain exactly one type key, but found {len(found_keys)}: {found_keys} in {rule_definition}")

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
        parts = [transpile_rule(part) for part in value]
        return f'({" / ".join(parts)})'
    elif rule_type == 'sequence':
        parts = [transpile_rule(part) for part in value]
        return " ".join(parts)
    elif rule_type == 'zero_or_more':
        return f"({transpile_rule(value)})*"
    elif rule_type == 'one_or_more':
        return f"({transpile_rule(value)})+"

def transpile_grammar(grammar_dict):
    """
    Takes a full grammar dictionary and transpiles it into a
    single grammar string compatible with Parsimonious.
    """
    if 'rules' not in grammar_dict:
        raise ValueError("Grammar definition must have a 'rules' key.")
        
    grammar_lines = []
    for rule_name, rule_definition in grammar_dict['rules'].items():
        transpiled_rhs = transpile_rule(rule_definition)
        grammar_lines.append(f"{rule_name} = {transpiled_rhs}")
        
    return "\n".join(grammar_lines)

# ==============================================================================
# The Visitor and Parser (Unchanged, they were already correct)
# ==============================================================================

class AstBuilderVisitor(NodeVisitor):
    def __init__(self, grammar_dict):
        self.grammar_rules = grammar_dict['rules']

    def generic_visit(self, node, visited_children):
        rule_name = node.expr_name
        if rule_name not in self.grammar_rules and node.is_literal():
             return { "tag": "literal", "text": node.text, "line": node.lineno, "col": node.colno }

        rule_def = self.grammar_rules.get(rule_name, {})
        ast_config = rule_def.get('ast', {})

        if ast_config.get('discard'):
            return None

        children = [c for c in visited_children if c is not None]

        if ast_config.get('promote'):
            # The actual expression is the middle child of `( _ expr _ )`
            if len(children) > 1 and children[0] is None and children[-1] is None:
                 return children[1]
            return children[0] if children else None

        structure_type = ast_config.get('structure')
        if structure_type == 'left_associative_op':
            left = children[0]
            rest_of_children = children[1] if len(children) > 1 else []
            for group in rest_of_children:
                op = group[1]
                right = group[3]
                left = {
                    "tag": "binary_op", "op": op, "left": left, "right": right,
                    "line": op['line'], "col": op['col']
                }
            return left

        base_node = {
            "tag": rule_name, "text": node.text,
            "line": node.lineno, "col": node.colno
        }
        if ast_config.get('leaf'):
            if ast_config.get('type') == 'number':
                val = float(node.text)
                base_node['value'] = int(val) if val.is_integer() else val
            return base_node

        base_node['children'] = children
        return base_node

class Parser:
    def __init__(self, grammar_dict: dict):
        self.grammar_string = transpile_grammar(grammar_dict)
        self.grammar = Grammar(self.grammar_string)
        self.visitor = AstBuilderVisitor(grammar_dict)
        self.start_rule = grammar_dict.get('start_rule', 'start')

    def parse(self, text: str, rule: str = None):
        start_rule = rule if rule is not None else self.start_rule
        try:
            tree = self.grammar[start_rule].parse(text)
            ast = self.visitor.visit(tree)
            return {"status": "success", "ast": ast}
        except (ParseError, IncompleteParseError) as e:
            return {"status": "error", "message": f"Syntax error at L{e.lineno}:C{e.colno}"}

# --- DEMONSTRATION ---
if __name__ == "__main__":
    with open("calculator_grammar.yaml", "r") as f:
        calculator_grammar_dict = yaml.safe_load(f)

    calc_parser = Parser(calculator_grammar_dict)
    
    print("--- Transpiled Grammar String (for debugging) ---")
    print(calc_parser.grammar_string)
    print("\n" + "="*50 + "\n")

    code = "10 * (5 + 2)"
    result = calc_parser.parse(code)

    print("--- Clean, Semantic AST (Generated from Directives) ---")
    print(json.dumps(result, indent=2))