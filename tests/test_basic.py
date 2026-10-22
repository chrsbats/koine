"""
Basic smoke tests to ensure the package imports and a trivial parse succeeds.
"""
import importlib

def test_imports_and_symbols():
    pkg = importlib.import_module("koine")
    assert hasattr(pkg, "Parser")
    assert hasattr(pkg, "Transpiler")
    assert hasattr(pkg, "PlaceholderParser")

def test_smoke_parse_number():
    from koine import Parser
    grammar = {
        "start_rule": "num",
        "rules": {
            "num": {"ast": {"leaf": True, "type": "number"}, "regex": r"\d+"}
        }
    }
    p = Parser(grammar)
    result = p.parse("42")
    assert result["status"] == "success"
    assert result["ast"]["value"] == 42


def test_combined_parse_transpile_matches_separate_calls():
    from koine import Parser, Transpiler
    grammar = {
        "start_rule": "num",
        "rules": {
            "num": {"ast": {"leaf": True, "type": "number", "tag": "number"}, "regex": r"\d+"}
        },
    }
    parser = Parser(grammar)
    transpiler = Transpiler({})
    combined = parser.parse_transpile("42", transpiler)
    separate = parser.parse("42")
    assert combined == {"status": "success", "text": transpiler.transpile(separate["ast"])}
    error = parser.parse_transpile("not a number", transpiler)
    assert error["status"] == "error" and "message" in error
    try:
        parser.parse_transpile("42", object())
    except TypeError:
        pass
    else:
        raise AssertionError("non-Transpiler must be rejected")
