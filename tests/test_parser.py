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
    with open(TESTS_DIR / "calculator_parser.yaml", "r") as f:
        parser_grammar = yaml.safe_load(f)
    with open(TESTS_DIR / "calculator_to_lisp_transpiler.yaml", "r") as f:
        transpiler_grammar = yaml.safe_load(f)

    my_parser = Parser(parser_grammar)
    my_transpiler = Transpiler(transpiler_grammar)
    
    # Test validation
    valid, msg = my_parser.validate(code)
    assert valid, f"Validation failed for '{code}': {msg}"

    # Test parsing
    parse_result = my_parser.parse(code, rule="expression")
    assert parse_result['status'] == 'success'
    assert parse_result['ast'] == expected_ast
    
    # Test transpilation
    translation = my_transpiler.transpile(parse_result['ast'])
    assert translation == expected_translation

def test_calc_errors():
    with open(TESTS_DIR / "calculator_parser.yaml", "r") as f:
        my_grammar = yaml.safe_load(f)

    my_parser = Parser(my_grammar)

    # Test cases that should result in a ParseError when parsed as 'expression'
    expression_error_cases = [
        ("2 + + 3", (1, 2), " + + 3", "Failed to consume entire input"),
        ("2 +", (1, 2), " +", "Failed to consume entire input"),
        ("((1)", (1, 5), "", "Unexpected end of input"),
    ]

    for code, expected_pos, expected_snippet, expected_error_text in expression_error_cases:
        result = my_parser.parse(code, rule="expression")
        assert result['status'] == 'error', f"Code that should have failed with rule 'expression': '{code}'"
        message = result['message']
        expected_line, expected_col = expected_pos
        assert f"L{expected_line}:C{expected_col}" in message, \
            f"For '{code}', expected L:C '{expected_pos}' in message:\n{message}"
        assert expected_snippet in message, \
            f"For '{code}', expected snippet '{expected_snippet}' in message:\n{message}"
        assert expected_error_text in message, \
            f"For '{code}', expected text '{expected_error_text}' in message:\n{message}"

    # Test cases that should result in IncompleteParseError with the default 'program' rule
    program_error_cases = [
        ("2 $ 3", (1, 3), "$ 3", "Failed to consume entire input"),
        ("1 + 2\n3 * 4\n5 $ 6", (3, 3), "$ 6", "Failed to consume entire input"),
    ]

    for code, expected_pos, expected_snippet, expected_error_text in program_error_cases:
        result = my_parser.parse(code)
        assert result['status'] == 'error', f"Code that should have failed with rule 'program': '{code}'"
        message = result['message']
        expected_line, expected_col = expected_pos

        assert f"L{expected_line}:C{expected_col}" in message, \
            f"For '{code}', expected L:C '{expected_pos}' in message:\n{message}"
        assert expected_snippet in message, \
            f"For '{code}', expected snippet '{expected_snippet}' in message:\n{message}"
        assert expected_error_text in message, \
            f"For '{code}', expected text '{expected_error_text}' in message:\n{message}"

def test_advanced():
    with open(TESTS_DIR / "advanced_parser.yaml", "r") as f:
        parser_grammar = yaml.safe_load(f)
    with open(TESTS_DIR / "advanced_transpiler.yaml", "r") as f:
        transpiler_grammar = yaml.safe_load(f)

    my_parser = Parser(parser_grammar)
    my_transpiler = Transpiler(transpiler_grammar)

    
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
                    "col": 7,
                },
                "dest": {
                    "tag": "path",
                    "text": "/new/path",
                    "line": 1,
                    "col": 24,
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
                    "col": 7,
                }
            }
        },
        {}
    ]

    expected_translations = ["(clone-to /path/to/repo /new/path)","(clone /another/repo)",""]

    for code,expected_ast,expected_translation in zip(test_cases,expected_asts,expected_translations):
        parse_result = my_parser.parse(code)
        
        if parse_result['status'] == 'success':
            assert parse_result['ast'] == expected_ast
            transpiled_code = my_transpiler.transpile(parse_result['ast'])
            assert transpiled_code == expected_translation
        else:
            # The test case for failure is an empty AST and empty translation
            assert expected_ast == {}
            assert expected_translation == ""

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

    def test_backtracking_in_choice(self):
        """
        Tests that if the first rule in a choice partially matches
        and then fails, the parser correctly backtracks and tries
        the next choice.
        """
        grammar = {
            'start_rule': 'expression',
            'rules': {
                'expression': {
                    'ast': {'promote': True},
                    'choice': [
                        # This rule for 'ab' will be tried first
                        {'sequence': [
                            {'literal': 'a', 'ast': {'tag': 'a'}},
                            {'literal': 'b', 'ast': {'tag': 'b'}}
                        ]},
                        # This rule for 'ac' should be tried on backtrack
                        {'sequence': [
                            {'literal': 'a', 'ast': {'tag': 'a'}},
                            {'literal': 'c', 'ast': {'tag': 'c'}}
                        ]}
                    ]
                }
            }
        }
        parser = Parser(grammar)
        result = parser.parse('ac')
        self.assertEqual(result['status'], 'success')
        # The AST should be the result of the second choice, `ac`.
        # The bug would result in a parse failure or an incorrect AST.
        expected_ast = [
            {'tag': 'a', 'text': 'a', 'line': 1, 'col': 1},
            {'tag': 'c', 'text': 'c', 'line': 1, 'col': 2}
        ]
        self.assertEqual(result['ast'], expected_ast)

    def test_named_nullable_rule_produces_empty_list(self):
        """
        Tests that a named rule that can match an empty sequence
        produces an empty list `[]` as its result, not `[None]`.
        """
        grammar = {
            'start_rule': 'program',
            'rules': {
                'program': {
                    'ast': {'tag': 'program'},
                    'sequence': [{
                        'ast': {'name': 'items'},
                        'choice': [
                            {'literal': 'a'},
                            {'sequence': []} # The empty choice
                        ]
                    }]
                }
            }
        }
        parser = Parser(grammar)
        result = parser.parse('')
        self.assertEqual(result['status'], 'success')
        expected_ast = {
            'tag': 'program', 'text': '', 'line': 1, 'col': 1,
            'children': {
                'items': []
            }
        }
        self.assertEqual(result['ast'], expected_ast)

    def test_declarative_ast_structure(self):
        """Tests that a declarative `structure` block can build a custom AST node."""
        grammar = {
            'start_rule': 'destructuring_assignment',
            'rules': {
                'destructuring_assignment': {
                    'ast': {
                        'structure': {
                            'tag': 'multi_set',
                            'map_children': {
                                'targets': {'from_child': 0},
                                'value': {'from_child': 2}
                            }
                        }
                    },
                    'sequence': [
                        {'rule': 'list_of_identifiers'},
                        {'literal': ':', 'ast': {'discard': True}},
                        {'rule': 'list_of_numbers'}
                    ]
                },
                'list_of_identifiers': {
                    'ast': {'tag': 'targets'},
                    'sequence': [
                        {'literal': '[', 'ast': {'discard': True}},
                        {'rule': 'identifier'},
                        {'literal': ']', 'ast': {'discard': True}},
                    ]
                },
                'list_of_numbers': {
                    'ast': {'tag': 'numbers'},
                     'sequence': [
                        {'literal': '#[', 'ast': {'discard': True}},
                        {'rule': 'number'},
                        {'literal': ']', 'ast': {'discard': True}},
                    ]
                },
                'identifier': {'ast': {'leaf': True}, 'regex': '[a-z]+'},
                'number': {'ast': {'leaf': True, 'type': 'number'}, 'regex': r'\d+'},
            }
        }
        parser = Parser(grammar)
        result = parser.parse('[a]:#[1]')
        self.assertEqual(result['status'], 'success')

        expected_ast = {
            'tag': 'multi_set',
            'text': '[a]:#[1]',
            'line': 1,
            'col': 1,
            'children': {
                'targets': {
                    'tag': 'targets',
                    'text': '[a]',
                    'line': 1,
                    'col': 1,
                    'children': [
                        {'tag': 'identifier', 'text': 'a', 'line': 1, 'col': 2}
                    ]
                },
                'value': {
                    'tag': 'numbers',
                    'text': '#[1]',
                    'line': 1,
                    'col': 5,
                    'children': [
                        {'tag': 'number', 'text': '1', 'line': 1, 'col': 7, 'value': 1}
                    ]
                }
            }
        }
        self.assertEqual(result['ast'], expected_ast)

    def test_left_recursion_raises_error(self):
        """
        Tests that initializing a Parser with a left-recursive grammar
        raises a ValueError.
        """
        # This is a best-effort check. `parsimonious` detects indirect
        # recursion, but not all forms of direct recursion (e.g., when the
        # recursive rule is inside a group `()`), so we only test for the
        # cases it is known to catch.
        # Indirect left-recursion
        grammar_indirect = {
            'start_rule': 'a',
            'rules': {
                'a': {'rule': 'b'},
                'b': {'rule': 'a'}
            }
        }
        with self.assertRaisesRegex(ValueError, "Left-recursion detected"):
            Parser(grammar_indirect)

    def test_unreachable_rule_raises_error(self):
        """
        Tests that initializing a Parser with unreachable rules raises a
        ValueError.
        """
        grammar = {
            'start_rule': 'a',
            'rules': {
                'a': {'literal': 'foo'},
                'b': {'literal': 'bar'}, # unreachable
                'c': {'literal': 'baz'}  # unreachable
            }
        }
        with self.assertRaisesRegex(ValueError, "Unreachable rules detected: b, c"):
            Parser(grammar)

    def test_regex_with_double_quotes_works(self):
        """
        Tests that a regex with a double quote works correctly, regardless
        of the YAML quoting style used for the grammar definition.
        """
        # In YAML, both of these string styles produce the same Python string.
        # This test ensures Koine handles it correctly.
        # 1. Using single quotes in YAML
        yaml_with_single_quotes = """
        start_rule: non_quote_char
        rules:
          non_quote_char:
            ast: {leaf: true}
            regex: '[^"]'
        """
        # 2. Using double quotes in YAML
        yaml_with_double_quotes = """
        start_rule: non_quote_char
        rules:
          non_quote_char:
            ast: {leaf: true}
            regex: "[^\\"]"
        """

        for i, yaml_string in enumerate([yaml_with_single_quotes, yaml_with_double_quotes]):
            with self.subTest(yaml_style="single_quotes" if i == 0 else "double_quotes"):
                grammar = yaml.safe_load(yaml_string)
                try:
                    parser = Parser(grammar)
                    # Check it parses a valid character
                    result = parser.parse('a')
                    self.assertEqual(result['status'], 'success')
                    # Check it fails to parse the double quote
                    result_fail = parser.parse('"')
                    self.assertEqual(result_fail['status'], 'error')
                except ValueError as e:
                    self.fail(f"Parser construction failed for a regex with quotes, indicating an escaping issue. Error: {e}")

    def test_regex_with_single_quotes_works(self):
        """
        Tests that a regex with a single quote works correctly. This is
        a complement to the double-quote test.
        """
        grammar = {
            'start_rule': 'non_single_quote_char',
            'rules': {
                'non_single_quote_char': {
                    'ast': {'leaf': True},
                    'regex': "[^']"
                }
            }
        }
        try:
            parser = Parser(grammar)
            result = parser.parse('a')
            self.assertEqual(result['status'], 'success')
            # Also test that it fails on a single quote
            result_fail = parser.parse("'")
            self.assertEqual(result_fail['status'], 'error')
        except ValueError as e:
            self.fail(f"Parser construction failed for a regex with quotes, indicating an escaping issue. Error: {e}")

    def test_unreachable_rule_linter_handles_missing_start(self):
        """
        Tests that the unreachable rule linter doesn't crash if the start
        rule is missing from the ruleset. Parsimonious will catch this
        later during parsing.
        """
        grammar = {
            'start_rule': 'nonexistent',
            'rules': {
                'a': {'literal': 'foo'}
            }
        }
        try:
            # The linter should not raise an exception, so construction succeeds.
            # The failure would happen later during parsing.
            Parser(grammar)
        except ValueError as e:
            self.fail(f"Parser initialization failed unexpectedly. The linter should not have run or failed, but got: {e}")


if __name__ == '__main__':
    unittest.main()
