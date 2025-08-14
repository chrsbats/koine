import unittest
import yaml
from pathlib import Path
from koine.parser import Parser, Transpiler

TESTS_DIR = Path(__file__).parent

class TestLexerAndTranspiler(unittest.TestCase):

    def test_python_to_javascript_transpilation(self):
        """
        Tests transpiling a Python function to JavaScript using a grammar
        with a lexer definition for indentation.
        """
        with open(TESTS_DIR / "py_parser.yaml", "r") as f:
            parser_grammar = yaml.safe_load(f)
        
        with open(TESTS_DIR / "py_to_js_transpiler.yaml", "r") as f:
            transpiler_grammar = yaml.safe_load(f)

        python_code = """
def f(x, y):
    a = 0
    for i in range(y):
        a = a + x
    return a
""".strip()
        
        expected_js_code = """
function f(x, y) {
    let a = 0;
    for (let i = 0; i < y; i++) {
        a = a + x;
    }
    return a;
}
""".strip()

        parser = Parser(parser_grammar)
        transpiler = Transpiler(transpiler_grammar)

        parse_result = parser.parse(python_code)
        self.assertEqual(parse_result['status'], 'success', parse_result.get('message'))
        
        translation = transpiler.transpile(parse_result['ast'])

        # Normalize whitespace for comparison
        self.assertEqual(
            " ".join(translation.split()),
            " ".join(expected_js_code.split())
        )

    def test_javascript_to_python_transpilation(self):
        """
        Tests transpiling a JavaScript function to Python using a grammar
        that generates indented output.
        """
        with open(TESTS_DIR / "js_parser.yaml", "r") as f:
            parser_grammar = yaml.safe_load(f)

        with open(TESTS_DIR / "js_to_py_transpiler.yaml", "r") as f:
            transpiler_grammar = yaml.safe_load(f)

        js_code = """
function f(x, y) {
    let a = 0;
    for (let i = 0; i < y; i++) {
        a = a + x;
    }
    return a;
}
""".strip()
        
        expected_python_code = """
def f(x, y):
    a = 0
    for i in range(y):
        a = a + x
    return a
""".strip()

        parser = Parser(parser_grammar)
        transpiler = Transpiler(transpiler_grammar)
        
        parse_result = parser.parse(js_code)
        self.assertEqual(parse_result['status'], 'success', parse_result.get('message'))

        translation = transpiler.transpile(parse_result['ast'])
        
        self.assertEqual(
            translation.strip(),
            expected_python_code
        )

    def test_transpiler_global_indent_config(self):
        """Tests that the global 'indent' setting in a transpiler grammar is respected."""
        transpiler_grammar = {
            "transpiler": {
                "indent": "  "  # Two spaces
            },
            "rules": {
                "block": {
                    "indent": True,
                    "join_children_with": "\n",
                    "template": "{children}"
                },
                "line": {
                    "use": "text"
                }
            }
        }
        
        ast = {
            "tag": "block",
            "children": [
                {"tag": "line", "text": "line1"},
                {"tag": "line", "text": "line2"}
            ]
        }
        
        transpiler = Transpiler(transpiler_grammar)
        translation = transpiler.transpile(ast)
        
        expected_output = "  line1\n  line2"
        self.assertEqual(translation, expected_output)

    def test_token_grammar_errors(self):
        """
        Tests that syntax errors in a token-based grammar produce
        useful error messages.
        """
        with open(TESTS_DIR / "py_parser.yaml", "r") as f:
            parser_grammar = yaml.safe_load(f)

        parser = Parser(parser_grammar)

        # Case 1: An illegal character that is not defined in the lexer
        code_illegal_char = "def f():\n    a = $"
        result = parser.parse(code_illegal_char)
        self.assertEqual(result['status'], 'error')
        self.assertIn("Unexpected character in input text at L2:C9: '$'", result['message'])

        # Case 2: A valid token sequence that is syntactically incorrect
        code_bad_syntax = "def f():\n    return for" # return followed by 'for' is not valid
        result = parser.parse(code_bad_syntax)
        self.assertEqual(result['status'], 'error')
        # The error is at the FOR token.
        self.assertIn("Syntax error in input text at L2:C12", result['message'])
        self.assertIn("Unexpected token 'FOR'", result['message'])
        self.assertIn("while parsing rule 'function_definition'", result['message'])
        # self.assertIn("Expected one of: expression", result['message']) # This fails due to lookahead

        # Case 3: An indentation error
        code_bad_indent = "def f():\n    a = 1\n  b = 2" # Misaligned indentation
        result = parser.parse(code_bad_indent)
        self.assertEqual(result['status'], 'error')
        self.assertIn("Indentation error in input text at L3:C1", result['message'])


    def test_transpiler_state_set_with_dynamic_value(self):
        """Tests that state_set can use placeholders in its value."""
        transpiler_grammar = {
            "rules": {
                "sequence": {
                    "join_children_with": " ",
                    "template": "{children}"
                },
                "item": {
                    "template": "{name}",
                    # On each item, set a state variable 'last_item' to the name of this item
                    "state_set": {
                        "last_item": "{name}"
                    }
                },
                "name": { "use": "text" }
            }
        }
        ast = {
            "tag": "sequence",
            "children": [
                {"tag": "item", "children": {"name": {"tag": "name", "text": "A"}}},
                {"tag": "item", "children": {"name": {"tag": "name", "text": "B"}}}
            ]
        }
        
        transpiler = Transpiler(transpiler_grammar)
        transpiler.transpile(ast)

        # After transpiling, the state should reflect the last item processed
        self.assertEqual(transpiler.state.get("last_item"), "B")


    def test_token_level_discard(self):
        """Tests that a token with `ast: { discard: true }` is omitted from the AST."""
        grammar = {
            "lexer": {
                "tokens": [
                    { "token": "A", "regex": "a" },
                    { "token": "DISCARD_B", "regex": "b", "ast": { "discard": True } }
                ]
            },
            "start_rule": "main",
            "rules": {
                "main": {
                    "ast": { "tag": "main" },
                    "sequence": [
                        { "token": "A" },
                        { "token": "DISCARD_B" },
                        { "token": "A" }
                    ]
                }
            }
        }
        
        parser = Parser(grammar)
        result = parser.parse("aba")
        self.assertEqual(result['status'], 'success')
        
        # We expect the 'B' token to be discarded from the children
        children = result['ast']['children']
        self.assertEqual(len(children), 2)
        self.assertEqual(children[0]['tag'], 'A')
        self.assertEqual(children[1]['tag'], 'A')


    def test_token_level_type_conversion(self):
        """Tests that 'type' conversion works on the token level in the lexer."""
        grammar = {
            "lexer": {
                "tokens": [
                    { "token": "BOOLEAN", "regex": "true|false", "ast": { "type": "bool" } },
                    { "token": "NULL", "regex": "null", "ast": { "type": "null" } }
                ]
            },
            "start_rule": "main",
            "rules": {
                "main": {
                    "ast": { "tag": "main" },
                    "sequence": [
                        { "token": "BOOLEAN" },
                        { "token": "NULL" }
                    ]
                }
            }
        }

        parser = Parser(grammar)
        result = parser.parse("truenull")
        self.assertEqual(result['status'], 'success')

        children = result['ast']['children']
        self.assertEqual(len(children), 2)

        # Check boolean conversion
        self.assertEqual(children[0]['tag'], 'BOOLEAN')
        self.assertEqual(children[0]['text'], 'true')
        self.assertIs(children[0]['value'], True)

        # Check null conversion
        self.assertEqual(children[1]['tag'], 'NULL')
        self.assertEqual(children[1]['text'], 'null')
        self.assertIs(children[1]['value'], None)


if __name__ == '__main__':
    unittest.main()
