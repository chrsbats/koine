"""Compare raw native/reference ASTs, including text, scalar types and locations."""

import argparse
import importlib.util
from pathlib import Path
import runpy
import sys

from koine import Parser, PlaceholderParser


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("koine_ast_reference", ROOT / "python/koine/parser.py")
reference = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reference
spec.loader.exec_module(reference)


def same(actual, expected, path="ast"):
    assert type(actual) is type(expected), (path, type(actual), type(expected))
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys(), (path, actual.keys(), expected.keys())
        for key in expected:
            same(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert len(actual) == len(expected), (path, len(actual), len(expected))
        for index, (left, right) in enumerate(zip(actual, expected)):
            same(left, right, f"{path}[{index}]")
    else:
        assert actual == expected, (path, actual, expected)


def compare(native, python, source, rule=None):
    actual, expected = native.parse(source, start_rule=rule), python.parse(source, start_rule=rule)
    assert actual["status"] == expected["status"], (source[:80], actual, expected)
    if expected["status"] == "success":
        same(actual["ast"], expected["ast"])
    else:
        assert actual.get("message"), actual


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--slip-root", type=Path)
    slip = args.parse_args().slip_root
    checks = 0
    for filename, sources, rule in (
        ("calculator_parser.yaml", ["1 + 2 * 3", "8 - 2 - 1", "2 ^ 3 ^ 2", "(2 * 3) ^ 5", "2 + + 3", "((1)"], "expression"),
        ("advanced_parser.yaml", ["CLONE /path/to/repo TO /new/path", "CLONE /another/repo", "CLONE /bad/repo TO"], None),
    ):
        path = ROOT / "tests" / filename
        native, python = Parser.from_file(path), reference.Parser.from_file(path)
        for source in sources:
            compare(native, python, source, rule)
            checks += 1
    if slip:
        grammar = slip / "grammar/slip_grammar.yaml"
        native, python = Parser.from_file(grammar), reference.Parser.from_file(grammar)
        tests = runpy.run_path(str(slip / "tests/test_parser.py"))["TEST_CASES"]
        for _, source, _ in tests:
            compare(native, python, source)
            checks += 1
        for source in ("'café' é", "'café'\nname: 2", "#[", "#{", "(", "'unterminated", "f: fn {x: A or B and C} []"):
            compare(native, python, source)
            checks += 1
        source = (slip / "slip/root.slip").read_text(encoding="utf-8")
        compare(native, python, source)
        assert native.validate(source) == (True, "success")
        checks += 1

        path = slip / "grammar/slip_path.yaml"
        path_tests = runpy.run_path(str(slip / "tests/test_parser_paths.py"))
        for native_cls, python_cls in ((Parser, reference.Parser), (PlaceholderParser, reference.PlaceholderParser)):
            integrated = native_cls is Parser
            native, python = native_cls.from_file(grammar if integrated else path), python_cls.from_file(grammar if integrated else path)
            for rule in ("get_path", "piped_path", "set_path", "del_path"):
                for _, source, _ in path_tests[rule.upper() + "_TEST_CASES"]:
                    compare(native, python, source, "SlipPath_" + rule if integrated else rule)
                    checks += 1
        path = slip / "grammar/slip_sig.yaml"
        for native_cls, python_cls in ((Parser, reference.Parser), (PlaceholderParser, reference.PlaceholderParser)):
            integrated = native_cls is Parser
            native, python = native_cls.from_file(grammar if integrated else path), python_cls.from_file(grammar if integrated else path)
            for source in ("", "a, b, rest...", "x: 10, y: 'raw' -> int", "x: {A or B}",
                           "x: Player and (OnFire or Poisoned)", "this: Combat, amount |where amount > 10 -> ok",
                           "x: A or B and C"):
                compare(native, python, source, "SlipSig_sig" if integrated else None)
                checks += 1

        # This precision difference is approved, and must not be normalized away.
        native, python = Parser.from_file(grammar), reference.Parser.from_file(grammar)
        token = "9007199254740993"
        actual = native.parse(token)["ast"]["children"][0]["children"][0]
        expected = python.parse(token)["ast"]["children"][0]["children"][0]
        assert actual["text"] == expected["text"] == token
        assert actual["value"] == 9007199254740993
        assert expected["value"] == 9007199254740992
    print(f"{checks} raw AST/status comparisons passed" + (", including complete SLIP root.slip and approved numeric divergence" if slip else ""))


if __name__ == "__main__":
    main()
