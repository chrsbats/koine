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
                            'tag': 'main_node',
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
        self.assertEqual(ast['tag'], 'main_node')
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

    def test_grammar_with_includes_and_subgrammars(self):
        """Tests that grammars can include and delegate to other files."""
        # --- Create dummy grammar files ---
        shared_rules_content = """
        rules:
          whitespace:
            ast: { discard: true }
            regex: "[ ]+"
          number:
            ast: { leaf: true, type: "number" }
            regex: "[0-9]+"
        """
        
        path_grammar_content = """
        start_rule: path
        rules:
          path:
            ast: { tag: "path" }
            sequence:
              - { rule: segment }
              - zero_or_more:
                  sequence:
                    - { literal: "." }
                    - { rule: segment }
          segment:
            ast: { leaf: true }
            regex: "[a-z]+"
        """
        
        main_grammar_content = """
        includes:
          - "shared.yaml" # non-namespaced include
        start_rule: 'main'
        rules:
          main:
            ast: { promote: true }
            choice:
              - { rule: set_path }
              - { rule: set_number }
          set_path:
            ast: { tag: "set_path" }
            sequence:
              - { subgrammar: "path.yaml", ast: { name: "target" } } # namespaced subgrammar
              - { rule: whitespace }
              - { literal: '=' }
          set_number:
            ast: { tag: "set_number" }
            sequence:
              - { rule: number } # from shared.yaml
        """
        
        shared_path = TESTS_DIR / "shared.yaml"
        path_path = TESTS_DIR / "path.yaml"
        main_path = TESTS_DIR / "main.yaml"
        
        shared_path.write_text(shared_rules_content)
        path_path.write_text(path_grammar_content)
        main_path.write_text(main_grammar_content)

        try:
            # --- Test multi-grammar parsing ---
            parser = Parser({
                "main": str(main_path),
                "path_only": str(path_path)
            })

            # Test parsing with the main grammar that uses includes and subgrammars
            result_main = parser.parse("foo.bar =", grammar="main")
            self.assertEqual(result_main['status'], 'success')
            ast = result_main['ast']
            self.assertEqual(ast['tag'], 'set_path')
            self.assertEqual(ast['children']['target']['tag'], 'path')
            
            # Test parsing with just the subgrammar
            result_path = parser.parse("foo.bar", grammar="path_only")
            self.assertEqual(result_path['status'], 'success')
            self.assertEqual(result_path['ast']['tag'], 'path')

            # Test rule from included file
            result_include = parser.parse("123", grammar="main")
            self.assertEqual(result_include['status'], 'success')
            self.assertEqual(result_include['ast']['tag'], 'set_number')

        finally:
            # Clean up the dummy files
            if shared_path.exists(): shared_path.unlink()
            if path_path.exists(): path_path.unlink()
            if main_path.exists(): main_path.unlink()

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


if __name__ == '__main__':
    unittest.main()
