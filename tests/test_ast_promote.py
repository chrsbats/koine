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
