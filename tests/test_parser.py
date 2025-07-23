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
    parse_result = my_parser.parse(code)
    assert parse_result['status'] == 'success'
    assert parse_result['ast'] == expected_ast
    
    # Test transpilation
    transpiled_result = my_parser.transpile(code)
    assert transpiled_result['status'] == 'success'
    assert transpiled_result['translation'] == expected_translation

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

if __name__ == '__main__':
    unittest.main()
