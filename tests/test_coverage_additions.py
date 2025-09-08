"""
Additional coverage tests to exercise less common branches and error paths.
"""
import pytest
import yaml
from koine.parser import Parser, Transpiler, PlaceholderParser

def test_transpiler_unknown_node_error():
    # No rule for 'container' or 'weird', and neither has 'text' or 'value'.
    t = Transpiler({"rules": {}})
    ast = {"tag": "container", "children": [{"tag": "weird", "children": []}]}
    with pytest.raises(ValueError, match=r"Don't know how to transpile node"):
        t.transpile(ast)

def test_transpiler_state_set_missing_placeholder_value_error():
    # Missing placeholder in state_set value should raise a clear error.
    grammar = {
        "rules": {
            "node": {
                "template": "ok",
                "state_set": { "x": "{name}" }  # 'name' placeholder not provided
            }
        }
    }
    t = Transpiler(grammar)
    with pytest.raises(ValueError, match=r"Missing placeholder 'name' in state_set value for tag 'node'"):
        t.transpile({"tag": "node"})

def test_parser_validate_false_on_error():
    # Simple grammar that only accepts the literal 'a'
    grammar = {"start_rule": "main", "rules": {"main": {"literal": "a"}}}
    p = Parser(grammar)
    valid, msg = p.validate("b")
    assert valid is False
    assert isinstance(msg, str) and "Syntax error in input text" in msg

def test_inline_token_ast_normalization():
    # Inline token with its own AST config must be normalized and honored
    grammar = {
        "lexer": { "tokens": [ { "regex": "[a-zA-Z_][a-zA-Z0-9_]*", "token": "NAME" } ] },
        "start_rule": "id",
        "rules": {
            "id": {
                "sequence": [
                    { "token": "NAME", "ast": { "tag": "ID", "leaf": True } }
                ]
            }
        }
    }
    p = Parser(grammar)
    r = p.parse("foo")
    assert r["status"] == "success"
    assert r["ast"]["tag"] == "ID"
    assert r["ast"]["text"] == "foo"

def test_python_parser_handles_blank_line_before_indent():
    # Ensure handle_indent skips blank lines and still emits a correct INDENT
    py = yaml.safe_load((__import__("pathlib").Path(__file__).parent / "py_parser.yaml").read_text())
    p = Parser(py)
    code = "def f(x):\n\n    return x"
    result = p.parse(code)
    assert result["status"] == "success"
