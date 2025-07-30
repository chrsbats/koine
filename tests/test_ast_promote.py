import pytest
import yaml
from koine import Parser

# This clean_ast function is a simplified copy from the main test suite
# to make this test case self-contained.
def clean_ast(node):
    """
    Recursively removes location info ('line', 'col') and verbose text from non-leaf
    nodes to make AST comparison in tests simpler and more focused on structure.
    """
    if 'ast' in node:
        node = node['ast']
    if isinstance(node, list):
        return [clean_ast(n) for n in node]
    if not isinstance(node, dict):
        return node

    # It's a dict (an AST node)
    new_node = {}
    if 'tag' in node:
        new_node['tag'] = node['tag']

    # For leaf nodes, capture the essential value (typed or text)
    if 'children' not in node:
        if 'value' in node:
            new_node['value'] = node['value']
        elif 'tag' in node: # Leaf without a type, like a 'name'
            new_node['text'] = node['text']

    # For branch nodes, recurse on children
    if 'children' in node:
        new_node['children'] = clean_ast(node['children'])

    return new_node

# This grammar is designed to specifically test the case where a `zero_or_more`
# with `promote: true` contains a rule that also has `promote: true`.
# The desired behavior is for the collected children to be flattened into the
# parent's list, not wrapped in nested lists.
TEST_GRAMMAR = """
start_rule: list
rules:
  list:
    ast: { tag: "list" }
    sequence:
      - { rule: item }
      - zero_or_more:
          ast: { promote: true }
          rule: subsequent_item

  subsequent_item:
    ast: { promote: true }
    sequence:
      - { regex: '\\s+', ast: { discard: true } }
      - { rule: item }

  item:
    ast: { tag: "item", leaf: true }
    regex: "[a-zA-Z]+"
"""

def test_nested_promote_in_quantifier_flattens_children():
    """
    Tests that a `promote` on a rule inside a `zero_or_more` quantifier
    correctly flattens into the parent's child list.
    """
    grammar_def = yaml.safe_load(TEST_GRAMMAR)
    parser = Parser(grammar_def)

    source_code = "a b c"
    expected_ast = {
        'tag': 'list',
        'children': [
            {'tag': 'item', 'text': 'a'},
            {'tag': 'item', 'text': 'b'},
            {'tag': 'item', 'text': 'c'}
        ]
    }

    try:
        result_ast = parser.parse(source_code)
    except Exception as e:
        pytest.fail(f"Parsing failed unexpectedly:\n{e}", pytrace=False)

    cleaned_result_ast = clean_ast(result_ast)

    assert cleaned_result_ast == expected_ast


def test_promoted_sequence_with_one_child_returns_list():
    """
    Tests that a promoted sequence with only one resulting child still
    returns a list containing that one child.
    """
    grammar_def = yaml.safe_load(PROMOTED_SEQUENCE_GRAMMAR)
    parser = Parser(grammar_def)

    source_code = "a"
    expected_ast = [
        {'tag': 'item', 'text': 'a'}
    ]

    try:
        result_ast = parser.parse(source_code)
    except Exception as e:
        pytest.fail(f"Parsing failed unexpectedly:\n{e}", pytrace=False)

    cleaned_result_ast = clean_ast(result_ast)

    assert cleaned_result_ast == expected_ast


# This grammar tests a promoted rule that contains a sequence with a quantifier.
# The expected result is a flat list of children.
PROMOTED_SEQUENCE_GRAMMAR = """
start_rule: items_list
rules:
  items_list:
    ast: { promote: true }
    sequence:
      - { rule: item }
      - zero_or_more:
          rule: item

  item:
    ast: { tag: "item", leaf: true }
    regex: "[a-z]"
"""

def test_promoted_rule_with_quantifier_flattens_children():
    """
    Tests that a promoted rule containing a sequence with a quantifier
    correctly flattens the resulting list of children.
    """
    grammar_def = yaml.safe_load(PROMOTED_SEQUENCE_GRAMMAR)
    parser = Parser(grammar_def)

    source_code = "abc"
    expected_ast = [
        {'tag': 'item', 'text': 'a'},
        {'tag': 'item', 'text': 'b'},
        {'tag': 'item', 'text': 'c'}
    ]

    try:
        result_ast = parser.parse(source_code)
    except Exception as e:
        pytest.fail(f"Parsing failed unexpectedly:\n{e}", pytrace=False)

    cleaned_result_ast = clean_ast(result_ast)

    assert cleaned_result_ast == expected_ast


# Grammars for testing consistent list returns from quantifiers
ONE_OR_MORE_GRAMMAR = """
start_rule: items_list
rules:
  items_list:
    ast: { promote: true }
    one_or_more:
      rule: item

  item:
    ast: { tag: "item", leaf: true }
    regex: "[a-z]"
"""

ZERO_OR_MORE_GRAMMAR = """
start_rule: items_list
rules:
  items_list:
    ast: { promote: true }
    zero_or_more:
      rule: item

  item:
    ast: { tag: "item", leaf: true }
    regex: "[a-z]"
"""

OPTIONAL_GRAMMAR = """
start_rule: optional_item
rules:
  optional_item:
    ast: { promote: true }
    optional:
      rule: item

  item:
    ast: { tag: "item", leaf: true }
    regex: "[a-z]"
"""

def test_promoted_one_or_more_with_one_child_returns_list():
    """
    Tests that a promoted one_or_more with only one resulting child still
    returns a list containing that one child for AST consistency.
    """
    grammar_def = yaml.safe_load(ONE_OR_MORE_GRAMMAR)
    parser = Parser(grammar_def)

    source_code = "a"
    expected_ast = [
        {'tag': 'item', 'text': 'a'}
    ]

    try:
        result_ast = parser.parse(source_code)
    except Exception as e:
        pytest.fail(f"Parsing failed unexpectedly:\n{e}", pytrace=False)

    cleaned_result_ast = clean_ast(result_ast)
    assert cleaned_result_ast == expected_ast


def test_promoted_sequence_with_nested_list_child_flattens():
    """
    Tests that a promoted sequence with a child that is itself a list
    (e.g., from a promoted quantifier) correctly flattens into a single list.
    This reproduces a bug where a structure like `[ node_a, [node_b, node_c] ]`
    was not flattened, and could sometimes result in only the first element
    being returned.
    """
    grammar = """
start_rule: main
rules:
  main:
    ast: { promote: true }
    sequence:
      - { rule: item_a }
      - { rule: list_of_b }

  item_a:
    ast: { tag: "item_a", leaf: true }
    literal: "a"

  list_of_b:
    ast: { promote: true } # This makes list_of_b return a list of its children
    one_or_more:
      rule: item_b

  item_b:
    ast: { tag: "item_b", leaf: true }
    literal: "b"
"""
    grammar_def = yaml.safe_load(grammar)
    parser = Parser(grammar_def)
    result = parser.parse('abb')

    assert result['status'] == 'success'
    cleaned_ast = clean_ast(result)
    expected_ast = [
        {'tag': 'item_a', 'text': 'a'},
        {'tag': 'item_b', 'text': 'b'},
        {'tag': 'item_b', 'text': 'b'}
    ]
    assert cleaned_ast == expected_ast


def test_promoted_zero_or_more_with_one_child_returns_list():
    """
    Tests that a promoted zero_or_more with only one resulting child still
    returns a list containing that one child for AST consistency.
    """
    grammar_def = yaml.safe_load(ZERO_OR_MORE_GRAMMAR)
    parser = Parser(grammar_def)

    source_code = "a"
    expected_ast = [
        {'tag': 'item', 'text': 'a'}
    ]

    try:
        result_ast = parser.parse(source_code)
    except Exception as e:
        pytest.fail(f"Parsing failed unexpectedly:\n{e}", pytrace=False)

    cleaned_result_ast = clean_ast(result_ast)
    assert cleaned_result_ast == expected_ast


def test_promoted_optional_with_one_child_returns_list():
    """
    Tests that a promoted optional with one resulting child returns a list
    containing that one child for AST consistency.
    """
    grammar_def = yaml.safe_load(OPTIONAL_GRAMMAR)
    parser = Parser(grammar_def)

    source_code = "a"
    expected_ast = [
        {'tag': 'item', 'text': 'a'}
    ]

    try:
        result_ast = parser.parse(source_code)
    except Exception as e:
        pytest.fail(f"Parsing failed unexpectedly:\n{e}", pytrace=False)

    cleaned_result_ast = clean_ast(result_ast)
    assert cleaned_result_ast == expected_ast


def test_promoted_optional_with_no_child_returns_empty_list():
    """
    Tests that a promoted optional that does not match returns an empty list,
    not None.
    """
    grammar_def = yaml.safe_load(OPTIONAL_GRAMMAR)
    parser = Parser(grammar_def)

    source_code = ""
    expected_ast = []

    try:
        result_ast = parser.parse(source_code)
    except Exception as e:
        pytest.fail(f"Parsing failed unexpectedly:\n{e}", pytrace=False)

    cleaned_result_ast = clean_ast(result_ast)
    assert cleaned_result_ast == expected_ast


def test_promote_applies_parent_ast_directives():
    """
    Tests that a parent rule with `promote: true` and other `ast` directives
    (like `tag` or `type`) correctly applies them to the promoted child node.
    """
    grammar = """
    start_rule: retagged_and_typed_node
    rules:
      retagged_and_typed_node:
        ast: { promote: true, tag: "parent_tag", type: "number" }
        rule: child_node

      child_node:
        ast: { tag: "child_tag", leaf: true }
        regex: "\\\\d+"
    """
    grammar_def = yaml.safe_load(grammar)
    parser = Parser(grammar_def)

    source_code = "123"
    expected_ast = {
        'tag': 'parent_tag',
        'value': 123
    }

    try:
        result = parser.parse(source_code)
    except Exception as e:
        pytest.fail(f"Parsing failed unexpectedly:\n{e}", pytrace=False)

    assert result['status'] == 'success'
    cleaned_ast = clean_ast(result)
    assert cleaned_ast == expected_ast


def test_promote_with_tag_on_list_wraps_node():
    """
    Tests that if a rule has `promote: true` and a `tag`, and it promotes a
    child that returns a list, the final result is a new node with that tag
    wrapping the list of children.
    """
    grammar = """
    start_rule: list_wrapper
    rules:
      list_wrapper:
        ast: { promote: true, tag: "wrapper" }
        rule: items

      items:
        ast: { promote: true }
        one_or_more:
          rule: item
      
      item:
        ast: { tag: "item", leaf: true }
        regex: "[a-z]"
    """
    grammar_def = yaml.safe_load(grammar)
    parser = Parser(grammar_def)
    source_code = "abc"
    result = parser.parse(source_code)
    assert result['status'] == 'success'

    cleaned_ast = clean_ast(result)
    expected_ast = {
        'tag': 'wrapper',
        'children': [
            {'tag': 'item', 'text': 'a'},
            {'tag': 'item', 'text': 'b'},
            {'tag': 'item', 'text': 'c'},
        ]
    }
    assert cleaned_ast == expected_ast
