import yaml
from pathlib import Path
import pytest

from koine import Parser
from koine.parser import Transpiler, PlaceholderParser

TESTS_DIR = Path(__file__).parent

def test_transpiler_missing_placeholder_in_template_error():
    transpiler_grammar = {
        "rules": {
            "greet": {
                "template": "Hello, {name}!"
            }
        }
    }
    node = {"tag": "greet", "children": {}}
    t = Transpiler(transpiler_grammar)
    with pytest.raises(ValueError) as ei:
        t.transpile(node)
    assert "Missing placeholder 'name' in template for tag 'greet'" in str(ei.value)

def test_transpiler_state_set_missing_placeholder_key_error():
    transpiler_grammar = {
        "rules": {
            "item": {
                "template": "x",
                "state_set": { "vars.{name}": True }
            }
        }
    }
    node = {"tag": "item", "children": {}}
    t = Transpiler(transpiler_grammar)
    with pytest.raises(ValueError) as ei:
        t.transpile(node)
    assert "Missing placeholder 'name' in state_set key for tag 'item'" in str(ei.value)

def test_transpiler_state_set_missing_placeholder_value_error():
    transpiler_grammar = {
        "rules": {
            "item": {
                "template": "x",
                "state_set": { "last": "{name}" }
            }
        }
    }
    node = {"tag": "item", "children": {}}
    t = Transpiler(transpiler_grammar)
    with pytest.raises(ValueError) as ei:
        t.transpile(node)
    assert "Missing placeholder 'name' in state_set value for tag 'item'" in str(ei.value)

def test_parser_validate_false_on_error():
    with open(TESTS_DIR / "calculator_parser.yaml", "r") as f:
        grammar = yaml.safe_load(f)
    p = Parser(grammar)
    ok, msg = p.validate("2 $ 3")
    assert ok is False
    assert isinstance(msg, str) and msg

def test_token_grammar_unexpected_error_message_mentions_rule():
    with open(TESTS_DIR / "py_parser.yaml", "r") as f:
        grammar = yaml.safe_load(f)
    p = Parser(grammar)
    code = "def f(x, y):\n    return"
    result = p.parse(code)
    assert result["status"] == "error"
    assert "while parsing rule 'function_definition'" in result["message"]

def test_python_parser_handles_blank_line_before_indent():
    with open(TESTS_DIR / "py_parser.yaml", "r") as f:
        grammar = yaml.safe_load(f)
    p = Parser(grammar)
    code = "def f(x, y):\n    a = 0\n\n    return a\n"
    result = p.parse(code)
    assert result["status"] == "success"

def test_error_message_includes_anonymous_regex_expected():
    grammar = {
        "start_rule": "main",
        "rules": {
            "main": { "rule": "number" },
            "number": { "regex": r"\d+" }
        }
    }
    p = Parser(grammar)
    result = p.parse("a")
    assert result["status"] == "error"
    assert 'regex matching r"\\d+"' in result["message"]

def test_placeholder_parser_validate_false_on_error():
    grammar = {
        "start_rule": "main",
        "rules": {
            "main": {
                "sequence": [
                    {"literal": "A"},
                    {"sequence": []}
                ]
            }
        }
    }
    pp = PlaceholderParser(grammar)
    ok, msg = pp.validate("X")
    assert ok is False
    assert isinstance(msg, str) and msg
