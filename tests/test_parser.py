from koine.parser import Parser, PlaceholderParser, Transpiler
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
    parse_result = my_parser.parse(code, start_rule="expression")
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
        ("((1)", (1, 5), "", "Unexpected end of input."),
    ]

    for code, expected_pos, expected_snippet, expected_error_text in expression_error_cases:
        result = my_parser.parse(code, start_rule="expression")
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

    def test_implicitly_empty_rule_raises_error(self):
        """
        Tests that a rule that is not explicitly discarded but always
        produces an empty AST node raises a ValueError during linting.
        """
        grammar = {
            'start_rule': 'main',
            'rules': {
                'main': { 'rule': 'empty_one' },
                'empty_one': {
                    'sequence': [ {'rule': 'discarded_a'}, {'rule': 'discarded_b'} ]
                },
                'discarded_a': { 'literal': 'a', 'ast': {'discard': True} },
                'discarded_b': { 'literal': 'b', 'ast': {'discard': True} }
            }
        }
        with self.assertRaisesRegex(ValueError, "always produce an empty AST node.*Rules: empty_one, main"):
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

    def test_inline_ast_definition_normalization(self):
        """
        Tests that an inline rule definition with an 'ast' block is
        correctly normalized into a named rule. This is a core feature
        for writing concise grammars.
        """
        grammar = {
            'start_rule': 'main',
            'rules': {
                'main': {
                    'ast': {'tag': 'main'},
                    'sequence': [
                        # This is an inline definition with an AST block.
                        # Koine should handle this by creating an anonymous rule.
                        {'literal': 'a', 'ast': {'tag': 'item_a', 'leaf': True}}
                    ]
                }
            }
        }
        
        try:
            parser = Parser(grammar)
            result = parser.parse('a')
            self.assertEqual(result['status'], 'success')
            expected_ast = {
                'tag': 'main',
                'text': 'a',
                'line': 1, 'col': 1,
                'children': [
                    {'tag': 'item_a', 'text': 'a', 'line': 1, 'col': 1}
                ]
            }
            # The structure of the AST proves that the inline 'ast' block was respected.
            self.assertEqual(result['ast'], expected_ast)
        except Exception as e:
            self.fail(f"Parser construction failed for grammar with inline ast block. Error: {e}")

    def test_one_or_more_quantifier(self):
        """
        Tests that the `one_or_more` quantifier correctly parses one or more
        items and fails on zero items.
        """
        grammar = {
            'start_rule': 'main',
            'rules': {
                'main': {
                    'ast': {'tag': 'main'},
                    'one_or_more': {'rule': 'item_and_space'}
                },
                'item_and_space': {
                    'ast': {'promote': True},
                    'sequence': [
                        {'literal': 'a', 'ast': {'tag': 'item', 'leaf': True}},
                        {'regex': r'\s*', 'ast': {'discard': True}}
                    ]
                }
            }
        }
        parser = Parser(grammar)
        
        # Should succeed on one and many items
        result_one = parser.parse('a')
        self.assertEqual(result_one['status'], 'success')
        self.assertEqual(len(result_one['ast']['children']), 1)
        
        result_many = parser.parse('a a a ')
        self.assertEqual(result_many['status'], 'success')
        self.assertEqual(len(result_many['ast']['children']), 3)

        # Should fail on zero items
        result_zero = parser.parse('')
        self.assertEqual(result_zero['status'], 'error')

    def test_map_children_with_optional_rules(self):
        """
        Tests that `structure.map_children` correctly indexes children when
        an optional rule is not present in the input.
        """
        grammar = {
            'start_rule': 'main',
            'rules': {
                'main': {
                    'ast': {
                        'structure': {
                            'tag': 'node',
                            'map_children': {
                                'child_a': {'from_child': 0},
                                'child_c': {'from_child': 2}
                            }
                        }
                    },
                    'sequence': [
                        {'rule': 'item_a'},
                        {'optional': {'rule': 'item_b'}}, # Optional child at index 1
                        {'rule': 'item_c'}
                    ]
                },
                'item_a': {'ast': {'leaf': True, 'tag': 'A'}, 'literal': 'a'},
                'item_b': {'ast': {'leaf': True, 'tag': 'B'}, 'literal': 'b'},
                'item_c': {'ast': {'leaf': True, 'tag': 'C'}, 'literal': 'c'}
            }
        }
        parser = Parser(grammar)

        # Case 1: Optional rule is NOT present
        result = parser.parse("ac")
        self.assertEqual(result['status'], 'success')
        ast = result['ast']
        self.assertEqual(ast['tag'], 'node')
        self.assertIn('child_a', ast['children'])
        self.assertIn('child_c', ast['children'])
        self.assertEqual(ast['children']['child_a']['tag'], 'A')
        self.assertEqual(ast['children']['child_c']['tag'], 'C')
        self.assertNotIn('child_b', ast['children'])

        # Case 2: Optional rule IS present
        result_with_b = parser.parse("abc")
        self.assertEqual(result_with_b['status'], 'success')
        ast_b = result_with_b['ast']
        self.assertEqual(ast_b['children']['child_a']['tag'], 'A')
        self.assertEqual(ast_b['children']['child_c']['tag'], 'C')
        # We didn't map 'b', so it shouldn't be in the final children map
        self.assertNotIn('child_b', ast_b['children'])


    def test_subgrammar_with_circular_reference(self):
        """
        Tests that a subgrammar can reference a rule defined in its parent,
        enabling circular dependencies between grammar files.
        """
        parent_grammar_content = """
        start_rule: a
        rules:
          a:
            ast: { tag: "a" }
            sequence:
              - { literal: "a_start", ast: {discard: true} }
              - { rule: _ }
              - { subgrammar: { file: "child.yaml", placeholder: { regex: "child_placeholder" } }, ast: { name: "child_part" } }
              - { rule: _ }
              - { literal: "a_end", ast: {discard: true} }
          parent_only_rule:
            ast: { tag: "from_parent", leaf: true }
            literal: "parent_rule_text"
          _:
            ast: { discard: true }
            regex: "\\\\s+"
        """

        child_grammar_content = """
        start_rule: b
        rules:
          b:
            ast: { tag: "b" }
            sequence:
              - { literal: "b_start", ast: {discard: true} }
              - { rule: _ }
              # This rule is defined in the parent, not here.
              - { rule: parent_only_rule, ast: { name: "parent_ref" } }
              - { rule: _ }
              - { literal: "b_end", ast: {discard: true} }
          _:
            ast: { discard: true }
            regex: "\\\\s+"
        """

        parent_path = TESTS_DIR / "parent.yaml"
        child_path = TESTS_DIR / "child.yaml"
        
        parent_path.write_text(parent_grammar_content)
        child_path.write_text(child_grammar_content)

        try:
            parser = Parser.from_file(str(parent_path))

            # Test 1: Full parsing with circular reference
            source_code = "a_start b_start parent_rule_text b_end a_end"
            result = parser.parse(source_code)

            self.assertEqual(result['status'], 'success', result.get('message'))
            
            ast = result['ast']
            self.assertEqual(ast['tag'], 'a')
            self.assertIn('child_part', ast['children'])
            
            child_ast = ast['children']['child_part']
            self.assertEqual(child_ast['tag'], 'b')
            self.assertIn('parent_ref', child_ast['children'])
            
            parent_ref_ast = child_ast['children']['parent_ref']
            self.assertEqual(parent_ref_ast['tag'], 'from_parent')
            self.assertEqual(parent_ref_ast['text'], 'parent_rule_text')
            
            # Test 2: Structural parsing using the regex placeholder
            structural_source = "a_start child_placeholder a_end"
            placeholder_parser = PlaceholderParser.from_file(str(parent_path))
            struct_result = placeholder_parser.parse(structural_source)
            self.assertEqual(struct_result['status'], 'success', struct_result.get('message'))
            
            struct_ast = struct_result['ast']
            self.assertEqual(struct_ast['tag'], 'a')
            self.assertIsInstance(struct_ast['children'], dict)
            self.assertIn('child_part', struct_ast['children'])
            
            child_struct_ast = struct_ast['children']['child_part']
            # The placeholder becomes a simple node. Since the subgrammar was
            # inline and its placeholder is a regex, the node is tagged 'regex'.
            self.assertEqual(child_struct_ast['tag'], 'regex')
            self.assertEqual(child_struct_ast['text'], 'child_placeholder')

        finally:
            if parent_path.exists(): parent_path.unlink()
            if child_path.exists(): child_path.unlink()

    def test_parse_with_placeholders(self):
        """
        Tests that `PlaceholderParser` correctly uses `regex` or `literal`
        placeholders instead of loading a subgrammar.
        """
        parent_grammar_content = """
        start_rule: main
        rules:
          main:
            ast: { tag: "main" }
            sequence:
              - { rule: placeholder_regex, ast: { name: "regex_part" } }
              - { literal: " ", ast: { discard: true } }
              - { rule: placeholder_literal, ast: { name: "literal_part" } }
          
          placeholder_regex:
            subgrammar:
              file: "placeholder_child.yaml"
              placeholder:
                regex: "REGEX_PLACEHOLDER"

          placeholder_literal:
            subgrammar:
              file: "placeholder_child.yaml"
              placeholder:
                literal: "LITERAL_PLACEHOLDER"
        """
        child_grammar_content = """
        start_rule: sub
        rules:
          sub:
            ast: { tag: "sub_node", leaf: true }
            literal: "actual_sub_content"
        """
        
        parent_path = TESTS_DIR / "placeholder_parent.yaml"
        child_path = TESTS_DIR / "placeholder_child.yaml"
        parent_path.write_text(parent_grammar_content)
        child_path.write_text(child_grammar_content)

        try:
            # 1. Test with PlaceholderParser
            placeholder_parser = PlaceholderParser.from_file(str(parent_path))
            placeholder_source = "REGEX_PLACEHOLDER LITERAL_PLACEHOLDER"
            result = placeholder_parser.parse(placeholder_source)
            self.assertEqual(result['status'], 'success', result.get('message'))
            
            ast = result['ast']
            self.assertEqual(ast['tag'], 'main')
            self.assertIn('regex_part', ast['children'])
            self.assertIn('literal_part', ast['children'])
            
            regex_node = ast['children']['regex_part']
            # With placeholders, the node gets the tag of the rule that defines the subgrammar.
            self.assertEqual(regex_node['tag'], 'placeholder_regex')
            self.assertEqual(regex_node['text'], 'REGEX_PLACEHOLDER')
            
            literal_node = ast['children']['literal_part']
            self.assertEqual(literal_node['tag'], 'placeholder_literal')
            self.assertEqual(literal_node['text'], 'LITERAL_PLACEHOLDER')

            # 2. Test with regular Parser to ensure it still works
            full_parser = Parser.from_file(str(parent_path))
            full_source = "actual_sub_content actual_sub_content"
            full_result = full_parser.parse(full_source)
            self.assertEqual(full_result['status'], 'success', full_result.get('message'))
            
            full_ast = full_result['ast']
            self.assertEqual(full_ast['tag'], 'main')
            self.assertIn('regex_part', full_ast['children'])
            self.assertIn('literal_part', full_ast['children'])
            
            self.assertEqual(full_ast['children']['regex_part']['tag'], 'sub_node')
            self.assertEqual(full_ast['children']['literal_part']['tag'], 'sub_node')
            
        finally:
            if parent_path.exists(): parent_path.unlink()
            if child_path.exists(): child_path.unlink()

    def test_transpiler_fallback_behavior(self):
        """
        Tests that the transpiler falls back to using 'value' or 'text'
        when no specific rule is found for a node's tag.
        """
        transpiler_grammar = {
            "rules": {
                "container": {
                    "join_children_with": " ",
                    "template": "{children}"
                }
                # No rules for 'node_with_value' or 'node_with_text'
            }
        }

        ast = {
            "tag": "container",
            "children": [
                {"tag": "node_with_value", "value": 123, "text": "value_should_be_ignored"},
                {"tag": "node_with_text", "text": "abc"},
            ]
        }

        transpiler = Transpiler(transpiler_grammar)
        translation = transpiler.transpile(ast)

        # Expects value to be preferred over text
        self.assertEqual(translation, "123 abc")

    def test_parent_tag_wraps_promoted_child_list(self):
        """
        Tests that a parent rule with a 'tag' correctly wraps the result of
        a child rule that uses 'promote' and returns a list.
        """
        grammar = {
            'start_rule': 'wrapper',
            'rules': {
                'wrapper': {
                    'ast': {'tag': 'wrapper'},
                    'rule': 'content'
                },
                'content': {
                    'ast': {'promote': True},
                    'sequence': [
                        {'rule': 'item'},
                        {'regex': r'\s+', 'ast': {'discard': True}},
                        {'rule': 'item'}
                    ]
                },
                'item': {
                    'ast': {'tag': 'item', 'leaf': True},
                    'regex': r'\w+'
                }
            }
        }
        parser = Parser(grammar)
        result = parser.parse("word1 word2")
        self.assertEqual(result['status'], 'success')
        
        expected_ast = {
            'tag': 'wrapper',
            'text': 'word1 word2',
            'line': 1,
            'col': 1,
            'children': [
                {'tag': 'item', 'text': 'word1', 'line': 1, 'col': 1},
                {'tag': 'item', 'text': 'word2', 'line': 1, 'col': 7}
            ]
        }
        self.assertEqual(result['ast'], expected_ast)


    def test_subgrammar_start_rule_handling(self):
        """
        Tests that subgrammars correctly handle missing start_rules,
        both in normal and circular dependency scenarios.
        """
        # --- Case 1: Success when 'rule' is specified for a subgrammar without a start_rule ---
        sub_no_start_content = """
        rules:
          sub_rule: { literal: 'sub' }
        """
        parent_with_rule_content = """
        start_rule: main
        rules:
          main: { subgrammar: { file: "sub.yaml", rule: "sub_rule" } }
        """
        sub_path = TESTS_DIR / "sub.yaml"
        parent_path = TESTS_DIR / "parent.yaml"
        sub_path.write_text(sub_no_start_content)
        parent_path.write_text(parent_with_rule_content)
        try:
            parser = Parser.from_file(str(parent_path))
            result = parser.parse("sub")
            self.assertEqual(result['status'], 'success')
        finally:
            if sub_path.exists(): sub_path.unlink()
            if parent_path.exists(): parent_path.unlink()

        # --- Case 2: Failure when no 'rule' is specified and subgrammar has no start_rule ---
        parent_no_rule_content = """
        start_rule: main
        rules:
          main: { subgrammar: { file: "sub.yaml" } }
        """
        sub_path.write_text(sub_no_start_content)
        parent_path.write_text(parent_no_rule_content)
        try:
            with self.assertRaisesRegex(ValueError, "Subgrammar 'sub.yaml' must have a 'start_rule' or a 'rule' must be specified."):
                Parser.from_file(str(parent_path))
        finally:
            if sub_path.exists(): sub_path.unlink()
            if parent_path.exists(): parent_path.unlink()

        # --- Case 3: Failure in a circular dependency with no start_rule ---
        circ_content = """
        start_rule: main
        rules:
          main: { subgrammar: { file: 'a.yaml', rule: 'a_rule' } }
        """
        # 'a.yaml' has no start_rule, which is key for the circular check failure.
        a_circ_content = """
        rules:
          a_rule: { subgrammar: { file: 'b.yaml' } }
        """
        b_circ_content = """
        start_rule: b_rule
        rules:
          b_rule: { subgrammar: { file: 'a.yaml' } }
        """
        
        path = TESTS_DIR / "circ.yaml"
        a_path = TESTS_DIR / "a.yaml"
        b_path = TESTS_DIR / "b.yaml"
        path.write_text(circ_content)
        a_path.write_text(a_circ_content)
        b_path.write_text(b_circ_content)

        try:
            with self.assertRaisesRegex(ValueError, "Subgrammar 'a.yaml' must have a 'start_rule' or a 'rule' must be specified."):
                Parser.from_file(str(path))
        finally:
            if path.exists(): path.unlink()
            if a_path.exists(): a_path.unlink()
            if b_path.exists(): b_path.unlink()


    def test_subgrammar_sibling_reference(self):
        """
        Tests that a subgrammar can reference a rule from a sibling subgrammar
        that has already been processed.
        """
        content = """
        start_rule: main
        rules:
          main:
            ast: { tag: "main" }
            sequence:
              - { subgrammar: { file: 'sub_a.yaml' } }
              - { subgrammar: { file: 'sub_b.yaml' } }
        """
        sub_a_content = """
        start_rule: rule_a
        rules:
          rule_a:
            ast: { tag: 'node_a', leaf: true }
            literal: 'a'
          rule_from_a:
            ast: { tag: 'from_a', leaf: true }
            literal: 'from_a'
        """
        sub_b_content = """
        start_rule: rule_b
        rules:
          rule_b:
            ast: { tag: 'node_b' }
            sequence:
              - { literal: 'b', ast: { tag: 'literal_b', leaf: true } }
              # This rule is namespaced and comes from a sibling subgrammar
              - { rule: SubA_rule_from_a }
        """

        path = TESTS_DIR / "main.yaml"
        a_path = TESTS_DIR / "sub_a.yaml"
        b_path = TESTS_DIR / "sub_b.yaml"
        path.write_text(content)
        a_path.write_text(sub_a_content)
        b_path.write_text(sub_b_content)

        try:
            parser = Parser.from_file(str(path))
            result = parser.parse("abfrom_a")
            self.assertEqual(result['status'], 'success', result.get('message'))
            
            ast = result['ast']
            self.assertEqual(ast['tag'], 'main')
            self.assertEqual(len(ast['children']), 2)
            
            child_a, child_b = ast['children']
            self.assertEqual(child_a['tag'], 'node_a')
            self.assertEqual(child_b['tag'], 'node_b')
            
            self.assertEqual(len(child_b['children']), 2)
            self.assertEqual(child_b['children'][0]['tag'], 'literal_b')
            self.assertEqual(child_b['children'][1]['tag'], 'from_a')
        finally:
            if path.exists(): path.unlink()
            if a_path.exists(): a_path.unlink()
            if b_path.exists(): b_path.unlink()

    def test_subgrammar_forward_reference(self):
        """
        Tests that a subgrammar can reference a rule from a sibling that is
        defined *after* it in the parent grammar. This requires a two-pass
        loading strategy.
        """
        # sub_b references a rule from sub_a, but sub_b is listed first.
        content = """
        start_rule: main
        rules:
          main:
            ast: { tag: "main" }
            sequence:
              - { subgrammar: { file: 'sub_b.yaml' }, ast: { name: "b_part" } }
              - { subgrammar: { file: 'sub_a.yaml' }, ast: { name: "a_part" } }
        """
        sub_a_content = """
        start_rule: rule_a
        rules:
          rule_a:
            ast: { tag: 'node_a', leaf: true }
            literal: 'a'
          rule_from_a:
            ast: { tag: 'from_a', leaf: true }
            literal: 'from_a'
        """
        sub_b_content = """
        start_rule: rule_b
        rules:
          rule_b:
            ast: { tag: 'node_b' }
            sequence:
              - { literal: 'b', ast: { leaf: true, discard: true } }
              # This is a forward reference to a rule in a sibling grammar.
              - { rule: SubA_rule_from_a }
        """
        path = TESTS_DIR / "main.yaml"
        a_path = TESTS_DIR / "sub_a.yaml"
        b_path = TESTS_DIR / "sub_b.yaml"
        path.write_text(content)
        a_path.write_text(sub_a_content)
        b_path.write_text(sub_b_content)

        try:
            parser = Parser.from_file(str(path))
            result = parser.parse("bfrom_aa")
            self.assertEqual(result['status'], 'success', result.get('message'))
            
            ast = result['ast']
            self.assertEqual(ast['tag'], 'main')
            
            b_part = ast['children']['b_part']
            self.assertEqual(b_part['tag'], 'node_b')
            self.assertEqual(b_part['children'][0]['tag'], 'from_a')

        finally:
            if path.exists(): path.unlink()
            if a_path.exists(): a_path.unlink()
            if b_path.exists(): b_path.unlink()

    def test_promote_with_structure_raises_error(self):
        """
        Tests that using 'promote' and 'structure' in the same AST block
        raises a ValueError.
        """
        grammar = {
            'start_rule': 'test',
            'rules': {
                'test': {
                    'ast': {'promote': True, 'structure': 'left_associative_op'},
                    'literal': 'a'
                }
            }
        }
        with self.assertRaisesRegex(ValueError, "'promote' and 'structure' directives are mutually exclusive"):
            Parser(grammar)

    def test_promote_with_discard_raises_error(self):
        """
        Tests that using 'promote' and 'discard' in the same AST block
        raises a ValueError.
        """
        grammar = {
            'start_rule': 'test',
            'rules': {
                'test': {
                    'ast': {'promote': True, 'discard': True},
                    'literal': 'a'
                }
            }
        }
        with self.assertRaisesRegex(ValueError, "'promote: true' is redundant when 'discard: true' is also present"):
            Parser(grammar)

    def test_leaf_with_subgrammar_raises_error(self):
        """
        Tests that a rule with `ast: {leaf: true}` directly containing a `subgrammar`
        directive raises a ValueError.
        """
        grammar_content = """
        start_rule: test
        rules:
          test:
            ast: {leaf: true}
            subgrammar: {file: 'sub.yaml'}
        """
        sub_grammar_content = "start_rule: sub\nrules:\n  sub: {literal: 'sub'}"
        path = TESTS_DIR / "main.yaml"
        sub_path = TESTS_DIR / "sub.yaml"
        path.write_text(grammar_content)
        sub_path.write_text(sub_grammar_content)

        try:
            with self.assertRaisesRegex(ValueError, "Rule 'test' is defined as a 'leaf' node but contains a 'subgrammar' directive. These are mutually exclusive."):
                Parser.from_file(str(path))
        finally:
            if path.exists(): path.unlink()
            if sub_path.exists(): sub_path.unlink()

    def test_leaf_with_nested_subgrammar_raises_error(self):
        """
        Tests that a leaf rule containing a subgrammar nested inside another
        construct (like a sequence) also raises an error.
        """
        grammar_content = """
        start_rule: test
        rules:
          test:
            ast: {leaf: true}
            sequence:
              - { subgrammar: {file: 'sub.yaml'} }
        """
        sub_grammar_content = "start_rule: sub\nrules:\n  sub: {literal: 'sub'}"
        path = TESTS_DIR / "main.yaml"
        sub_path = TESTS_DIR / "sub.yaml"
        path.write_text(grammar_content)
        sub_path.write_text(sub_grammar_content)

        try:
            with self.assertRaisesRegex(ValueError, "Rule 'test' is defined as a 'leaf' node but contains a 'subgrammar' directive. These are mutually exclusive."):
                Parser.from_file(str(path))
        finally:
            if path.exists(): path.unlink()
            if sub_path.exists(): sub_path.unlink()

    def test_subgrammar_unqualified_reference_to_sibling_fails_gracefully(self):
        """
        Tests that an unqualified reference to a rule in a sibling subgrammar
        fails during parsimonious compilation, not due to a premature
        validation check in Koine. This is the correct behavior.
        """
        content = """
        start_rule: main
        rules:
          main:
            sequence:
              - { subgrammar: { file: 'sub_a.yaml' } }
              - { subgrammar: { file: 'sub_b.yaml' } }
        """
        sub_a_content = """
        start_rule: rule_a
        rules:
          rule_a: { literal: 'a' }
          rule_from_a: { literal: 'from_a' }
        """
        sub_b_content = """
        start_rule: rule_b
        rules:
          rule_b:
            # Unqualified reference to a rule in a sibling grammar.
            # This is not supported and should fail during compilation.
            rule: rule_from_a
        """

        path = TESTS_DIR / "main.yaml"
        a_path = TESTS_DIR / "sub_a.yaml"
        b_path = TESTS_DIR / "sub_b.yaml"
        path.write_text(content)
        a_path.write_text(sub_a_content)
        b_path.write_text(sub_b_content)

        try:
            # This should fail when parsimonious tries to build the grammar
            # because 'rule_from_a' will not be defined in the final grammar string
            # for the SubB part.
            with self.assertRaisesRegex(ValueError, "is not defined in grammar"):
                Parser.from_file(str(path))
        finally:
            if path.exists(): path.unlink()
            if a_path.exists(): a_path.unlink()
            if b_path.exists(): b_path.unlink()

    def test_unreachable_rule_in_subgrammar_raises_error(self):
        """
        Tests that the linter correctly identifies an unreachable rule within a
        subgrammar when the parent grammar is compiled.
        """
        parent_content = """
        start_rule: main
        rules:
          main:
            subgrammar: { file: 'child.yaml' }
        """
        child_content = """
        start_rule: child_start
        rules:
          child_start: { literal: 'a' }
          # This rule is not referenced by anything, so it should be flagged.
          unreachable: { literal: 'b' }
        """
        parent_path = TESTS_DIR / "parent.yaml"
        child_path = TESTS_DIR / "child.yaml"
        parent_path.write_text(parent_content)
        child_path.write_text(child_content)

        try:
            # The linter runs on the combined grammar and should find the unreferenced rule.
            # The subgrammar file 'child.yaml' becomes the namespace 'Child'.
            with self.assertRaisesRegex(ValueError, "Unreachable rules detected: Child_unreachable"):
                Parser.from_file(str(parent_path))
        finally:
            if parent_path.exists(): parent_path.unlink()
            if child_path.exists(): child_path.unlink()

    def test_subgrammar_rule_is_reachable_if_referenced_externally(self):
        """
        Tests that a rule in a subgrammar is NOT flagged as unreachable if it
        is referenced by the parent grammar.
        """
        parent_content = """
        start_rule: main
        rules:
          main:
            sequence:
              - { subgrammar: { file: 'child.yaml' } }
              # Externally reference the otherwise unreachable rule
              - { rule: Child_reachable_by_parent }
        """
        child_content = """
        start_rule: child_start
        rules:
          child_start: { literal: 'a' }
          # This rule is now referenced by the parent.
          reachable_by_parent: { literal: 'b' }
        """
        parent_path = TESTS_DIR / "parent.yaml"
        child_path = TESTS_DIR / "child.yaml"
        parent_path.write_text(parent_content)
        child_path.write_text(child_content)

        try:
            # Should not raise an unreachable rule error
            parser = Parser.from_file(str(parent_path))
            result = parser.parse("ab")
            self.assertEqual(result['status'], 'success')
        except ValueError as e:
            self.fail(f"Parser initialization failed unexpectedly: {e}")
        finally:
            if parent_path.exists(): parent_path.unlink()
            if child_path.exists(): child_path.unlink()

    def test_subgrammar_A_B_A_circular_reference(self):
        """
        Tests a circular dependency where grammar A includes B, and B refers
        back to a rule in A. This ensures that namespacing is handled correctly
        in nested, circular scenarios.
        """
        content = """
        start_rule: main
        rules:
          main:
            subgrammar: { file: 'a.yaml' }
        """
        a_content = """
        start_rule: rule_a
        rules:
          rule_a:
            ast: { tag: 'node_a' }
            sequence:
              - { literal: 'a_start', ast: { discard: true } }
              - { rule: _ }
              - { subgrammar: { file: 'b.yaml' }, ast: { name: 'b_part' } }
              - { rule: _ }
              - { literal: 'a_end', ast: { discard: true } }
          rule_from_a:
            ast: { tag: 'from_a', leaf: true }
            literal: 'text_from_a'
          _:
            ast: { discard: true }
            regex: "\\\\s+"
        """
        b_content = """
        start_rule: rule_b
        rules:
          rule_b:
            ast: { tag: 'node_b' }
            sequence:
              - { literal: 'b_start', ast: { discard: true } }
              - { rule: _ }
              # This is a reference back to a rule in the parent subgrammar 'a'
              - { rule: A_rule_from_a, ast: { name: 'a_ref' } }
              - { rule: _ }
              - { literal: 'b_end', ast: { discard: true } }
          _:
            ast: { discard: true }
            regex: "\\\\s+"
        """
        path = TESTS_DIR / "main.yaml"
        a_path = TESTS_DIR / "a.yaml"
        b_path = TESTS_DIR / "b.yaml"
        path.write_text(content)
        a_path.write_text(a_content)
        b_path.write_text(b_content)

        try:
            parser = Parser.from_file(str(path))
            source = "a_start b_start text_from_a b_end a_end"
            result = parser.parse(source)
            self.assertEqual(result['status'], 'success', result.get('message'))

            ast = result['ast']
            self.assertEqual(ast['tag'], 'node_a')
            b_part = ast['children']['b_part']
            self.assertEqual(b_part['tag'], 'node_b')
            a_ref = b_part['children']['a_ref']
            self.assertEqual(a_ref['tag'], 'from_a')
            self.assertEqual(a_ref['text'], 'text_from_a')

        finally:
            if path.exists(): path.unlink()
            if a_path.exists(): a_path.unlink()
            if b_path.exists(): b_path.unlink()


if __name__ == '___':
    unittest.main()
