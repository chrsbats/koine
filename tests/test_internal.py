
import pytest
import yaml
from koine.parser import PlaceholderParser

# This grammar provides a minimal, self-contained test case to replicate a bug
# in PlaceholderParser where discarded literals in a sequence are not correctly
# handled when a `subgrammar` placeholder is present.
TEST_GRAMMAR = """
# Koine grammar for parsing the internal structure of a single SLIP path string.
# This grammar does not parse sub-expressions within dynamic segments `()`, `[]`,
# or metadata blocks `#()`, instead capturing their contents as text.

start_rule: any_path

rules:
  any_path:
    ast: { promote: true }
    choice:
      - { rule: set_path }
      - { rule: del_path }
      - { rule: get_path }

  embedded_del_path:
    ast: { tag: "del-path" }
    sequence:
      - { literal: "~", ast: { discard: true } }
      - { rule: path_body }
      - optional: { rule: metadata_block }

  del_path:
    ast: { promote: true }
    sequence:
      - { rule: embedded_del_path }
      - { rule: EOI }

  embedded_set_path:
    ast: { promote: true }
    choice:
      - { rule: multi_set_path }
      - { rule: simple_set_path }

  simple_set_path:
    ast: { tag: "set-path" }
    sequence:
      - { rule: actual_path }
      - optional: { rule: metadata_block }
      - { literal: ":", ast: { discard: true } }

  multi_set_path:
    ast: { tag: "set-path" }
    sequence:
      - { literal: "[", ast: { discard: true } }
      - { rule: ws_opt_path }
      - optional: { rule: multi_set_targets }
      - { rule: ws_opt_path }
      - { literal: "]", ast: { discard: true } }
      - { literal: ":", ast: { discard: true } }

  multi_set_targets:
    ast: { promote: true }
    sequence:
      - { rule: multi_set_target }
      - zero_or_more:
          ast: { promote: true }
          sequence:
            - { rule: ws_opt_path }
            - { literal: ",", ast: { discard: true } }
            - { rule: ws_opt_path }
            - { rule: multi_set_target }

  multi_set_target:
    ast: { tag: "set-path" }
    rule: actual_path

  set_path:
    ast: { promote: true }
    sequence:
      - { rule: embedded_set_path }
      - { rule: EOI }

  # =================================================================
  # Top-level Path Structure
  # =================================================================

  embedded_get_path:
    ast: { tag: "get-path" }
    sequence:
      - { rule: path_body }
      - optional: { rule: metadata_block }

  get_path:
    ast: { promote: true }
    sequence:
      - { rule: embedded_get_path }
      - { rule: EOI } # End of Input, ensures the whole string is consumed

  path_body:
    ast: { promote: true }
    sequence:
      - optional:
          ast: { promote: true }
          rule: pipe_segment
      - { rule: actual_path }

  actual_path:
    ast: { promote: true }
    choice:
      - sequence: # A path starting with a prefix-like segment
          - one_or_more:
              ast: { promote: true }
              choice:
                - { rule: root_segment }
                - { rule: parent_segment }
                - { rule: pwd_segment }
          - optional: { rule: path_chain } # The rest of the path is optional
      - { rule: path_chain } # Any other valid path chain

  path_chain:
    ast: { promote: true }
    sequence:
      - { rule: base_segment }
      - zero_or_more:
          ast: { promote: true }
          rule: suffix_segment

  base_segment:
    ast: { promote: true }
    choice:
      - { rule: any_name_segment }
      - { rule: group_segment }
      - { rule: bracket_segment }

  suffix_segment:
    ast: { promote: true }
    choice:
      - sequence: # A segment that must be preceded by a separator
          - { rule: separator }
          - ast: { promote: true }
            choice:
              # parent/pwd can be followed by a name without another separator.
              # This must be tried before the other, more general rules.
              - sequence:
                  - { rule: parent_segment, ast: { promote: true } }
                  - optional: { rule: any_name_segment, ast: { promote: true } }
              - sequence:
                  - { rule: pwd_segment, ast: { promote: true } }
                  - optional: { rule: any_name_segment, ast: { promote: true } }
              # Fallback to a plain name segment
              - { rule: any_name_segment }
              - { rule: group_segment }
              - { rule: bracket_segment }
      # Segments that don't need a separator
      - { rule: group_segment }
      - { rule: bracket_segment }

  separator:
    ast: { discard: true }
    choice:
      - { literal: "." }
      - { literal: "/" }

  # =================================================================
  # Individual Segment Definitions
  # =================================================================

  pipe_segment: { ast: { tag: "pipe" }, literal: "|" }
  root_segment: { ast: { tag: "root" }, literal: "/" }
  parent_segment: { ast: { tag: "parent" }, literal: "../" }
  pwd_segment: { ast: { tag: "pwd" }, literal: "./" }

  any_name_segment:
    ast: { promote: true }
    choice:
      - { rule: operator_segment }
      - { rule: name_segment }

  operator_segment:
    ast: { tag: "name", leaf: true }
    # Longest first: **, !=, >=, <=, then single-character operators
    regex: '(\*\*|!=|>=|<=|[-+*=><])'

  name_segment:
    ast: { tag: "name", leaf: true }
    regex: '[a-zA-Z0-9-]+(?:\.\.\.)?'

  group_segment:
    ast: { tag: "group" }
    sequence:
      - { literal: "(", ast: { discard: true } }
      - { rule: expr_for_paren }
      - { literal: ")", ast: { discard: true } }

  bracket_segment:
    ast: { promote: true }
    choice:
      # Slices must be tried before index. Order of variants is important.
      - { rule: slice_full }
      - { rule: slice_from }
      - { rule: slice_until }
      - { rule: slice_all }
      - { rule: index_def }

  index_def:
    ast: { tag: "index" }
    sequence:
      - { literal: "[", ast: { discard: true } }
      - { rule: expr_for_bracket }
      - { literal: "]", ast: { discard: true } }

  slice_full:
    ast: { tag: "slice" }
    sequence:
      - { literal: "[", ast: { discard: true } }
      - { rule: slice_expr }
      - { literal: ":", ast: { discard: true } }
      - { rule: slice_expr }
      - { literal: "]", ast: { discard: true } }

  slice_from:
    ast: { tag: "slice_from" }
    sequence:
      - { literal: "[", ast: { discard:true } }
      - { rule: slice_expr }
      - { literal: ":", ast: { discard: true } }
      - { literal: "]", ast: { discard: true } }

  slice_until:
    ast: { tag: "slice_until" }
    sequence:
      - { literal: "[", ast: { discard: true } }
      - { literal: ":", ast: { discard: true } }
      - { rule: slice_expr }
      - { literal: "]", ast: { discard: true } }

  slice_all:
    ast: { tag: "slice" } # same tag as full, but no children
    sequence:
      - { literal: "[", ast: { discard: true } }
      - { literal: ":", ast: { discard: true } }
      - { literal: "]", ast: { discard: true } }

  slice_expr:
    ast: { promote: true }
    subgrammar:
      file: "slip_grammar.yaml"
      rule: "expression_list"
      placeholder: { ast: { tag: "expr", leaf: true }, regex: '[^:\]]+' }

  metadata_block:
    ast: { tag: "meta" }
    sequence:
      - { literal: "#(", ast: { discard: true } }
      - { rule: expr_for_paren }
      - { literal: ")", ast: { discard: true } }

  # =================================================================
  # Expression Content Capturers & Helpers
  # =================================================================

  # Captures the raw text inside `(...)`
  # Captures the raw text inside `(...)`
  expr_for_paren:
    ast: { promote: true }
    subgrammar:
      file: "slip_grammar.yaml"
      rule: "expression_list"
      placeholder: { ast: { tag: "expr", leaf: true }, regex: "[^)]*" }

  # Captures the raw text inside `[...]` for an index.
  # It must not contain a colon to distinguish it from a slice.
  expr_for_bracket:
    ast: { promote: true }
    subgrammar:
      file: "slip_grammar.yaml"
      rule: "expression_list"
      placeholder: { ast: { tag: "expr", leaf: true }, regex: '[^:\]]+' }

  ws_opt_path:
    ast: { discard: true }
    regex: '[ \t]*'

  # Marks the end of input
  EOI:
    ast: { discard: true }
    regex: '\Z'
"""

@pytest.fixture(scope="module")
def failing_parser():
    """Provides a parser instance for a grammar known to cause issues."""
    grammar_def = yaml.safe_load(TEST_GRAMMAR)
    return PlaceholderParser(grammar_def)


def _assert_no_internal_tags(node):
    """
    Recursively asserts that no node in the AST has a tag containing '__'.
    These are internal tags for unnamed rules that should be discarded.
    """
    if isinstance(node, list):
        for item in node:
            _assert_no_internal_tags(item)
    elif isinstance(node, dict):
        if 'tag' in node:
            assert '__' not in node['tag'], f"Found unexpected internal tag: {node['tag']}"
        if 'children' in node:
            _assert_no_internal_tags(node['children'])

def test_placeholder_parser_discards_literals(failing_parser):
    """
    Tests that the PlaceholderParser correctly discards literals marked with
    `ast: { discard: true }` and does not generate internal `__` tags for them.
    This test uses a minimal grammar that replicates the structure of
    `slip_path.yaml`'s `slice_from` rule, which was found to trigger the bug.
    """
    source_string = "a[1:]"
    # The start rule `get_path` is specified in the grammar itself.
    parse_result = failing_parser.parse(source_string)

    assert parse_result["status"] == "success", f"Parsing failed unexpectedly: {parse_result.get('error_message')}"

    result_ast = parse_result["ast"]

    # This assertion is expected to fail, revealing the bug where PlaceholderParser
    # generates internal `__` tags for discarded literals in a sequence.
    _assert_no_internal_tags(result_ast)

if __name__ == "__main__":
    pytest.main(['-s', __file__])
