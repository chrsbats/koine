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
