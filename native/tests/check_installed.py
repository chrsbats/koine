"""Exercise a clean installation of either package variant."""
import argparse
import gc
from importlib.util import find_spec
from pathlib import Path
import sys
import tempfile

import koine
from koine import Parser, PlaceholderParser, Transpiler


def check_common():
    parser = Parser({"start_rule": "x", "rules": {"x": {"regex": r"[\s\S]+"}}})
    saved = parser.parse("café\0text")["ast"]
    del parser
    gc.collect()
    assert Transpiler().transpile(saved) == "café\0text"
    placeholder = PlaceholderParser({"start_rule": "main", "rules": {"main": {"subgrammar": {
        "file": "missing.yaml", "placeholder": {"literal": "local"}
    }}}})
    assert placeholder.validate("local") == (True, "success")
    with tempfile.TemporaryDirectory(prefix="koine-文件-") as directory:
        path = Path(directory) / "输出.yaml"
        path.write_text("rules:\n  leaf: {value: on}\n", encoding="utf-8")
        assert Transpiler.from_file(path).transpile({"tag": "leaf"}) == "on"


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("fixtures", type=Path)
    args.add_argument("--pure", action="store_true", help="verify the pure-Python wheel")
    options = args.parse_args()
    package = Path(koine.__file__).resolve().parent
    assert Path(koine.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), koine.__file__
    library = "koine.dll" if sys.platform == "win32" else "libkoine.dylib" if sys.platform == "darwin" else "libkoine.so"
    if options.pure:
        assert not (package / library).exists()
        for dependency in ("parsimonious", "safer_yaml"):
            assert find_spec(dependency) is not None, dependency
    else:
        assert (package / library).exists(), library
        for dependency in ("parsimonious", "safer_yaml", "yaml", "regex"):
            assert find_spec(dependency) is None, dependency
        number = Parser({"start_rule": "n", "rules": {"n": {"regex": "[0-9]+", "ast": {"type": "number"}}}})
        assert number.parse("18446744073709551615")["ast"]["value"] == 2**64 - 1
        assert number.validate("no")[0] is False
        try:
            number.parse("18446744073709551616")
        except ValueError:
            pass
        else:
            raise AssertionError("Missing explicit integer overflow")
    check_common()
    python = Parser.from_file(options.fixtures / "py_parser.yaml")
    javascript = Transpiler.from_file(options.fixtures / "py_to_js_transpiler.yaml")
    source = "def f(x):\r\n\treturn x\r\n"
    parsed = python.parse(source)
    assert parsed["status"] == "success", parsed
    expected = javascript.transpile(parsed["ast"])
    assert expected == "function f(x) {\n    return x;\n}", expected
    combined = python.parse_transpile(source, javascript)
    assert combined == {"status": "success", "text": expected}, combined
    variant = "dependency-free native" if not options.pure else "pure"
    print(f"Clean {variant} install and parser/lexer/placeholder/transpiler APIs passed: {koine.__file__}")


if __name__ == "__main__":
    main()
