import pytest
from koine.parser import Parser, Transpiler, transpile_grammar

def test_transpile_grammar_disallows_literal_when_lexer_defined():
    # When a lexer is present, using 'literal' in rules should raise a clear error
    grammar = {
        "lexer": { "tokens": [ { "regex": r"\s+", "action": "skip" } ] },
        "rules": { "main": { "literal": "x" } }
    }
    with pytest.raises(ValueError, match=r"'literal' is not supported when a lexer is defined"):
        transpile_grammar(grammar)

def test_transpile_grammar_subgrammar_placeholder_injection():
    # Ensure subgrammar nodes that leak to transpile_grammar become a safe empty matcher
    grammar = {
        "rules": {
            "main": {
                "sequence": [
                    { "subgrammar": { "file": "child.yaml" } }
                ]
            }
        }
    }
    s = transpile_grammar(grammar)
    # The subgrammar node should be converted to a no-op group
    assert '("")?' in s

def test_transpile_grammar_sequence_of_one_injects_noop():
    # Sequence with a single item should get a no-op to prevent optimization
    grammar = {
        "rules": { "single_seq": { "sequence": [ { "literal": "x" } ] } }
    }
    s = transpile_grammar(grammar)
    # Verify the rule embeds the no-op ("")?
    assert "single_seq =" in s and '("")?' in s

def test_transpile_grammar_rule_ref_with_ast_is_wrapped():
    # A rule reference with its own ast (beyond just 'name') must be wrapped to avoid optimization
    grammar = {
        "rules": {
            "child": { "literal": "x" },
            "wrap": { "rule": "child", "ast": { "tag": "wrapped" } }
        }
    }
    s = transpile_grammar(grammar)
    assert "wrap = (child (\"\")?)" in s

def test_error_message_includes_anonymous_regex_expected():
    # Anonymous regex in a rule should surface as a human-readable expected item
    grammar = {
        "start_rule": "main",
        "rules": {
            "main": {
                # Keep regex anonymous so _get_expected_from_error reports it as regex matching r"..."
                "sequence": [ { "regex": r"\d+" } ]
            }
        }
    }
    parser = Parser(grammar)
    result = parser.parse("a")
    assert result["status"] == "error"
    assert 'regex matching r"\\d+"' in result["message"]

def test_transpiler_cases_truthiness_without_equals():
    # Exercise _evaluate_condition truthiness path (no 'equals')
    transpiler_grammar = {
        "rules": {
            "seq": { "join_children_with": " ", "template": "{children}" },
            "setter": { "template": "s", "state_set": { "flag": True } },
            "cond": {
                "cases": [
                    { "if": { "path": "state.flag" }, "then": "on" },
                    { "default": "off" }
                ]
            }
        }
    }
    ast = {
        "tag": "seq",
        "children": [
            { "tag": "setter" },
            { "tag": "cond" }
        ]
    }
    t = Transpiler(transpiler_grammar)
    out = t.transpile(ast)
    assert out == "s on"

def test_transpiler_missing_placeholder_in_template_error():
    # Missing placeholders in template should raise a clear ValueError
    transpiler_grammar = { "rules": { "node": { "template": "{missing}" } } }
    t = Transpiler(transpiler_grammar)
    with pytest.raises(ValueError, match=r"Missing placeholder 'missing' in template for tag 'node'"):
        t.transpile({ "tag": "node" })

def test_transpiler_state_set_missing_placeholder_key_error():
    # Missing placeholders in state_set key should raise a clear ValueError
    transpiler_grammar = {
        "rules": {
            "node": {
                "template": "ok",
                "state_set": { "vars.{name}": True } # {name} not provided anywhere
            }
        }
    }
    t = Transpiler(transpiler_grammar)
    with pytest.raises(ValueError, match=r"Missing placeholder 'name' in state_set key for tag 'node'"):
        t.transpile({ "tag": "node" })
