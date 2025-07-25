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

if __name__ == '__main__':
    unittest.main()
