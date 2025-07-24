from koine.parser import Parser, Transpiler
import yaml
import json
import pytest

from pathlib import Path
TESTS_DIR = Path(__file__).parent

@pytest.mark.parametrize("code, expected_ast, expected_translation", [
    (
        "(2 * 3) ^ 5",
        {
            "tag": "binary_op",
            "op": { "tag": "power_op", "text": "^", "line": 1, "col": 9 },
            "left": {
                "tag": "binary_op",
                "op": { "tag": "mul_op", "text": "*", "line": 1, "col": 4 },
                "left": { "tag": "number", "text": "2", "line": 1, "col": 2, "value": 2 },
                "right": { "tag": "number", "text": "3", "line": 1, "col": 6, "value": 3 },
                "line": 1, "col": 4
            },
            "right": { "tag": "number", "text": "5", "line": 1, "col": 11, "value": 5 },
            "line": 1, "col": 9
        },
        "(pow (mul 2 3) 5)"
    ),
    (
        "1 + 2 * 3",
        {
            "tag": "binary_op",
            "op": { "tag": "add_op", "text": "+", "line": 1, "col": 3 },
            "left": { "tag": "number", "text": "1", "line": 1, "col": 1, "value": 1 },
            "right": {
                "tag": "binary_op",
                "op": { "tag": "mul_op", "text": "*", "line": 1, "col": 7 },
                "left": { "tag": "number", "text": "2", "line": 1, "col": 5, "value": 2 },
                "right": { "tag": "number", "text": "3", "line": 1, "col": 9, "value": 3 },
                "line": 1, "col": 7
            },
            "line": 1, "col": 3
        },
        "(add 1 (mul 2 3))"
    ),
    (
        "8 - 2 - 1",
        {
            "tag": "binary_op",
            "op": { "tag": "add_op", "text": "-", "line": 1, "col": 7 },
            "left": {
                "tag": "binary_op",
                "op": { "tag": "add_op", "text": "-", "line": 1, "col": 3 },
                "left": { "tag": "number", "text": "8", "line": 1, "col": 1, "value": 8 },
                "right": { "tag": "number", "text": "2", "line": 1, "col": 5, "value": 2 },
                "line": 1, "col": 3
            },
            "right": { "tag": "number", "text": "1", "line": 1, "col": 9, "value": 1 },
            "line": 1, "col": 7
        },
        "(sub (sub 8 2) 1)"
    ),
    (
        "2 ^ 3 ^ 2",
        {
            "tag": "binary_op",
            "op": { "tag": "power_op", "text": "^", "line": 1, "col": 3 },
            "left": { "tag": "number", "text": "2", "line": 1, "col": 1, "value": 2 },
            "right": {
                "tag": "binary_op",
                "op": { "tag": "power_op", "text": "^", "line": 1, "col": 7 },
                "left": { "tag": "number", "text": "3", "line": 1, "col": 5, "value": 3 },
                "right": { "tag": "number", "text": "2", "line": 1, "col": 9, "value": 2 },
                "line": 1, "col": 7
            },
            "line": 1, "col": 3
        },
        "(pow 2 (pow 3 2))"
    ),
])
def test_calc(code, expected_ast, expected_translation):
    with open(TESTS_DIR / "calculator_grammar.yaml", "r") as f:
        my_grammar = yaml.safe_load(f)

    my_parser = Parser(my_grammar)
    
    # Test validation
    valid, msg = my_parser.validate(code)
    assert valid, f"Validation failed for '{code}': {msg}"

    # Test parsing
    parse_result = my_parser.parse(code, rule="expression")
    assert parse_result['status'] == 'success'
    assert parse_result['ast'] == expected_ast
    
    # Test transpilation
    transpiled_result = my_parser.transpile(code, rule="expression")
    assert transpiled_result['status'] == 'success'
    assert transpiled_result['translation'] == expected_translation

def test_calc_errors():
    with open(TESTS_DIR / "calculator_grammar.yaml", "r") as f:
        my_grammar = yaml.safe_load(f)

    my_parser = Parser(my_grammar)

    test_cases = [
        ("2 + + 3", (1, 3), "+ + 3"),
        ("2 +", (1, 3), "+"),
        ("2 $ 3", (1, 3), "$ 3"),
        ("1 + 2\n3 * 4\n5 $ 6", (3, 3), "$ 6"),
    ]

    for code, expected_pos, expected_snippet in test_cases:
        result = my_parser.parse(code)
        assert result['status'] == 'error'
        message = result['message']
        expected_line, expected_col = expected_pos
        # Check the line and column are in the message
        assert f"L{expected_line}:C{expected_col}" in message
        # Check the snippet is in the message
        assert expected_snippet in message

def test_advanced():
    with open(TESTS_DIR / "advanced_grammar.yaml", "r") as f:
        my_grammar = yaml.safe_load(f)

    my_parser = Parser(my_grammar)
    my_transpiler = Transpiler(my_grammar)

    
    test_cases = [
        "CLONE /path/to/repo TO /new/path",
        "CLONE /another/repo",
        "CLONE /bad/repo TO" # This should fail gracefully
    ]

    expected_asts =[ 
        {
            "tag": "clone_to",
            "text": "CLONE /path/to/repo TO /new/path",
            "line": 1,
            "col": 1,
            "children": {
                "repo": {
                "tag": "path",
                "text": "/path/to/repo",
                "line": 1,
                "col": 7
                },
                "dest": {
                "tag": "path",
                "text": "/new/path",
                "line": 1,
                "col": 24
                }
            }
        },
        {
            "tag": "clone",
            "text": "CLONE /another/repo",
            "line": 1,
            "col": 1,
            "children": {
                "repo": {
                "tag": "path",
                "text": "/another/repo",
                "line": 1,
                "col": 7
                }
            }
        },
        {}
    ]

    expected_translations = ["(clone-to /path/to/repo /new/path)","(clone /another/repo)",""]

    for code,expected_ast,expected_translation in zip(test_cases,expected_asts,expected_translations):
        print(f"--- Input: '{code}' ---")
        parse_result = my_parser.parse(code)
        
        if parse_result['status'] == 'success':
            print("✅ AST:")
            print(json.dumps(parse_result['ast'], indent=2))
            assert parse_result['ast'] == expected_ast
            print("\n✅ Transpiled Output:")
            transpiled_code = my_transpiler.transpile(parse_result['ast'])
            print(transpiled_code)
            assert transpiled_code == expected_translation
        else:
            print(f"❌ Parse Error: {parse_result['message']}")
        print("-" * 25)

import unittest
from koine import Parser
from parsimonious.exceptions import IncompleteParseError

class TestKoineGrammarGeneration(unittest.TestCase):

    def test_choice_of_unnamed_sequences_bug(self):
        """
        This test checks that Koine can handle a choice between two
        unnamed sequences, which has been a source of bugs. It should
        parse successfully.
        """
        grammar = {
            'start_rule': 'main',
            'rules': {
                'main': {
                    'choice': [
                        {'sequence': [{'literal': 'a'}]},
                        {'sequence': [{'literal': 'b'}]}
                    ]
                }
            }
        }

        # This test will FAIL if the bug is present.
        try:
            parser = Parser(grammar)
            # To be thorough, check that it can parse something.
            result = parser.parse('a')
            self.assertEqual(result['status'], 'success')
        except IncompleteParseError as e:
            self.fail(f"Koine generated an invalid grammar for a choice of sequences: {e}")

    def test_choice_of_unnamed_sequences_with_empty_alternative(self):
        """
        This test checks that Koine can handle a choice between a non-empty
        unnamed sequence and an empty unnamed sequence. This is a pattern
        that can cause issues if not handled correctly.
        """
        grammar = {
            'start_rule': 'main',
            'rules': {
                'main': {
                    'choice': [
                        {'sequence': [{'literal': 'a'}]},
                        {'sequence': []}  # empty alternative
                    ]
                }
            }
        }

        try:
            parser = Parser(grammar)
            # Check it can parse the non-empty case
            result_a = parser.parse('a')
            self.assertEqual(result_a['status'], 'success')

            # Check it can parse the empty case
            result_empty = parser.parse('')
            self.assertEqual(result_empty['status'], 'success')
        except IncompleteParseError as e:
            self.fail(f"Koine generated an invalid grammar for a choice with an empty sequence: {e}")

    def test_empty_choice_raises_error(self):
        """
        This test checks that Koine raises a ValueError when a 'choice'
        rule has no alternatives, as this is an invalid grammar state.
        """
        grammar = {
            'start_rule': 'main',
            'rules': {
                'main': {
                    'choice': []  # empty choice
                }
            }
        }
        with self.assertRaises(ValueError):
            Parser(grammar)

    def test_bool_type_conversion(self):
        """Tests that a leaf node with type: 'bool' gets a 'value' key."""
        grammar = {
            'start_rule': 'boolean',
            'rules': {
                'boolean': {
                    'ast': {'tag': 'bool', 'leaf': True, 'type': 'bool'},
                    'regex': r'true'
                }
            }
        }
        parser = Parser(grammar)
        result = parser.parse('true')
        self.assertEqual(result['status'], 'success')
        expected_ast = {
            'tag': 'bool',
            'text': 'true',
            'line': 1,
            'col': 1,
            'value': True
        }
        self.assertEqual(result['ast'], expected_ast)

    def test_null_type_conversion(self):
        """Tests that a leaf node with type: 'null' gets a value of None."""
        grammar = {
            'start_rule': 'null_value',
            'rules': {
                'null_value': {
                    'ast': {'leaf': True, 'type': 'null'},
                    'regex': r'null'
                }
            }
        }
        parser = Parser(grammar)
        result = parser.parse('null')
        self.assertEqual(result['status'], 'success')
        expected_ast = {
            'tag': 'null_value',
            'text': 'null',
            'line': 1,
            'col': 1,
            'value': None
        }
        self.assertEqual(result['ast'], expected_ast)

    def test_int_type_conversion(self):
        """Tests that a leaf node with type: 'number' becomes an integer."""
        grammar = {
            'start_rule': 'number',
            'rules': {
                'number': {
                    'ast': {'leaf': True, 'type': 'number'},
                    'regex': r'-?\d+'
                }
            }
        }
        parser = Parser(grammar)
        result = parser.parse('123')
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['ast']['value'], 123)
        self.assertIsInstance(result['ast']['value'], int)

    def test_float_type_conversion(self):
        """Tests that a leaf node with type: 'number' becomes a float."""
        grammar = {
            'start_rule': 'number',
            'rules': {
                'number': {
                    'ast': {'leaf': True, 'type': 'number'},
                    'regex': r'-?\d+\.\d+'
                }
            }
        }
        parser = Parser(grammar)
        result = parser.parse('123.45')
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['ast']['value'], 123.45)
        self.assertIsInstance(result['ast']['value'], float)

    def test_quantifier_empty_match_is_omitted_from_ast(self):
        """
        Tests that a quantifier (zero_or_more, optional) that matches
        zero times does not add an empty list to the parent's children,
        which would clutter the AST.
        """
        grammar = {
            'start_rule': 'main',
            'rules': {
                'main': {
                    'ast': {'tag': 'main'},
                    'sequence': [
                        {'rule': 'a'},
                        {'zero_or_more': {'rule': 'b'}},
                        {'rule': 'c'}
                    ]
                },
                'a': {'literal': 'a', 'ast': {'tag': 'a', 'leaf': True}},
                'b': {'literal': 'b', 'ast': {'tag': 'b', 'leaf': True}},
                'c': {'literal': 'c', 'ast': {'tag': 'c', 'leaf': True}}
            }
        }
        parser = Parser(grammar)
        # Parse 'ac', so 'b' is not matched by zero_or_more
        result = parser.parse('ac')
        self.assertEqual(result['status'], 'success')

        # Current (undesired) behavior would produce children like:
        # [ {'tag': 'a', ...}, [], {'tag': 'c', ...} ]

        # Desired behavior:
        expected_ast = {
            'tag': 'main',
            'text': 'ac',
            'line': 1,
            'col': 1,
            'children': [
                {'tag': 'a', 'text': 'a', 'line': 1, 'col': 1},
                {'tag': 'c', 'text': 'c', 'line': 1, 'col': 2}
            ]
        }
        self.assertEqual(result['ast'], expected_ast)


if __name__ == '__main__':
    unittest.main()
