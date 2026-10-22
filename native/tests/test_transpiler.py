import gc
import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import unittest

from safer_yaml import load

from koine import Parser, Transpiler


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("transpiler_reference", ROOT / "reference/koine/parser.py")
reference = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reference
spec.loader.exec_module(reference)


class NativeTranspilerTests(unittest.TestCase):
    def test_default_grammar_and_value_spelling(self):
        native, python = Transpiler(), reference.Transpiler()
        for value in (None, True, False, 0, -3, 2**64 - 1, 1.25, -0.0, 1e15, 1e16, 1e-4, 1e-5,
                      "café\0text", ["a'b", False, None], {"x": [1, None]}):
            with self.subTest(value=value):
                node = {"tag": "leaf", "value": value, "text": "ignored"}
                self.assertEqual(native.transpile(node), python.transpile(node))
        saved = native.transpile({"tag": "x", "text": "saved\0é"})
        del native
        gc.collect()
        self.assertEqual(saved, "saved\0é")

    def test_combined_parse_and_transpile_matches_separate_calls(self):
        parser = Parser.from_file(ROOT / "tests/calculator_parser.yaml")
        transpiler = Transpiler.from_file(Path(__file__).with_name("math_to_slip.yaml"))
        for source, expected in (("10 + 5 * 2", "(10 + (5 * 2))"), ("2 ^ 3 ^ 2", "(2 ** (3 ** 2))")):
            with self.subTest(source=source):
                separate = parser.parse(source, start_rule="expression")
                self.assertEqual(transpiler.transpile(separate["ast"]), expected)
                combined = parser.parse_transpile(source, transpiler, start_rule="expression")
                self.assertEqual(combined, {"status": "success", "text": expected})
                self.assertNotIn("ast", combined)
        self.assertEqual(parser.parse_transpile("2 +", transpiler, start_rule="expression")["status"], "error")
        with self.assertRaisesRegex(TypeError, "Transpiler"):
            parser.parse_transpile("1", object())
        invalid = Transpiler({"rules": {"x": {"cases": [{"if": {}, "then": "bad"}]}}})
        tagged = Parser({"start_rule": "x", "rules": {"x": {"literal": "2", "ast": {"tag": "x"}}}})
        with self.assertRaisesRegex(ValueError, "Condition must have a 'path' key"):
            tagged.parse_transpile("2", invalid, start_rule="x")

    def test_native_output_grammar_files(self):
        with tempfile.TemporaryDirectory() as directory:
            yaml_path = Path(directory) / "output.yaml"
            yaml_path.write_text("rules:\n  leaf: {value: on}\n", encoding="utf-8")
            json_path = Path(directory) / "output.json"
            json_path.write_text(json.dumps({"rules": {"leaf": {"value": "on"}}}), encoding="utf-8")
            for path in (yaml_path, json_path):
                self.assertEqual(Transpiler.from_file(path).transpile({"tag": "leaf"}), "on")
            with self.assertRaisesRegex(ValueError, "Could not open"):
                Transpiler.from_file(Path(directory) / "missing.yaml")
            with self.assertRaisesRegex(ValueError, "NUL"):
                Transpiler.from_file(str(yaml_path) + "\0other")

    def test_templates_do_not_expand_substituted_text(self):
        transpiler = Transpiler({"rules": {"wrapper": {"template": "{{{content}}}"}}})
        self.assertEqual(transpiler.transpile({"tag": "wrapper", "children": {
            "content": {"text": "{literal}\0é"},
        }}), "{{literal}\0é}")

    def test_advanced_format_expressions_are_explicit_errors(self):
        for expression in ("{content:>10}", "{content!r}", "{content[0]}", "{content.upper}"):
            with self.subTest(expression=expression):
                transpiler = Transpiler({"rules": {"x": {"template": expression}}})
                with self.assertRaisesRegex(ValueError, "Unsupported format expression"):
                    transpiler.transpile({"tag": "x", "children": {"content": {"text": "abc"}}})

    def test_cases_truthiness_equality_and_precedence(self):
        grammar = {"rules": {"check": {"cases": [
            {"if": {"path": "node.flag"}, "then": "yes"}, {"default": "no"},
        ]}}}
        for value in (None, False, 0, 0.0, "", [], {}, "0", [False], {"x": None}, 1):
            native, python = Transpiler(grammar), reference.Transpiler(grammar)
            self.assertEqual(native.transpile({"tag": "check", "flag": value}),
                             python.transpile({"tag": "check", "flag": value}))
        for actual, expected in ((True, "True"), (False, 0), (None, "None"), (0, "0"), ([1, False], "[1, False]")):
            grammar["rules"]["check"]["cases"][0]["if"]["equals"] = expected
            native, python = Transpiler(grammar), reference.Transpiler(grammar)
            self.assertEqual(native.transpile({"tag": "check", "flag": actual}),
                             python.transpile({"tag": "check", "flag": actual}))
        transpiler = Transpiler({"rules": {"x": {"cases": [], "template": "unused", "use": "text"}}})
        self.assertEqual(transpiler.transpile({"tag": "x", "text": "fallback"}), "fallback")

    def test_state_order_reset_and_detached_snapshot(self):
        grammar = {"rules": {
            "seq": {"template": "{children}", "join_children_with": "; "},
            "assign": {"cases": [
                {"if": {"path": "state.vars.{name}", "negate": True}, "then": "let {name} = {value}"},
                {"default": "{name} = {value}"},
            ], "state_set": {"vars.{name}": True, "last": "{value}"}},
        }}
        def assignment(value):
            return {"tag": "assign", "children": {"name": {"text": "x"}, "value": {"value": value}}}
        ast = {"tag": "seq", "children": [assignment(1), assignment(2)]}
        native, python = Transpiler(grammar), reference.Transpiler(grammar)
        self.assertEqual(native.state, {})
        for _ in range(2):
            self.assertEqual(native.transpile(ast), "let x = 1; x = 2")
            self.assertEqual(native.transpile(ast), python.transpile(ast))
            self.assertEqual(native.state, python.state)
        snapshot = native.state
        snapshot["vars"]["x"] = False
        self.assertIs(native.state["vars"]["x"], True)
        with self.assertRaisesRegex(ValueError, "Don't know how to transpile"):
            native.transpile({"tag": "seq", "children": [assignment(3), {"tag": "invalid"}]})
        self.assertEqual(native.state, {"vars": {"x": True}, "last": "3"})
        self.assertEqual(native.transpile(ast), "let x = 1; x = 2")

    def test_indentation_nested_lists_and_error_recovery(self):
        grammar = {"transpiler": {"indent": "  "}, "rules": {
            "block": {"indent": True, "template": "{children}", "join_children_with": "\n"},
        }}
        native, python = Transpiler(grammar), reference.Transpiler(grammar)
        ast = {"tag": "block", "children": [
            {"tag": "x", "text": "one"},
            {"tag": "block", "children": [{"tag": "x", "text": "two"}]},
            {"tag": "x", "text": "three"},
        ]}
        self.assertEqual(native.transpile(ast), python.transpile(ast))
        self.assertEqual(native.transpile({"tag": "block", "children": [None, [], "", False, 0]}), "")
        with self.assertRaises(ValueError):
            native.transpile({"tag": "block", "children": [{"tag": "invalid"}]})
        self.assertEqual(native.transpile(ast), python.transpile(ast))
        nested = {"tag": "block", "children": [[{"text": "a"}, None, [], {"text": "b"}], {"text": "c"}]}
        self.assertEqual(native.transpile(nested), python.transpile(nested))

    def test_conditional_paths_and_errors(self):
        transpiler = Transpiler({"rules": {"x": {"cases": [
            {"if": {"path": "node.missing.deep", "equals": None}, "then": "missing"},
        ]}}})
        self.assertEqual(transpiler.transpile({"tag": "x"}), "missing")
        invalid = Transpiler({"rules": {"x": {"cases": [{"if": {}, "then": "bad"}]}}})
        with self.assertRaisesRegex(ValueError, "Condition must have a 'path' key"):
            invalid.transpile({"tag": "x"})
        for node in (None, [], {}, 1):
            with self.subTest(node=node), self.assertRaisesRegex(ValueError, "valid AST node"):
                Transpiler().transpile(node)
        with self.assertRaisesRegex(ValueError, "Unmatched"):
            Transpiler({"rules": {"x": {"template": "{"}}}).transpile({"tag": "x"})

    def test_python_javascript_end_to_end(self):
        python_source = "def f(x, y):\n    a = 0\n    for i in range(y):\n        a = a + x\n    return a"
        javascript_source = "function f(x, y) { let a = 0; for (let i = 0; i < y; i++) { a = a + x; } return a; }"
        for parser_file, output_file, source in (
            ("py_parser.yaml", "py_to_js_transpiler.yaml", python_source),
            ("js_parser.yaml", "js_to_py_transpiler.yaml", javascript_source),
        ):
            with self.subTest(grammar=output_file):
                parsed = Parser.from_file(ROOT / "tests" / parser_file).parse(source)
                expected = reference.Parser.from_file(ROOT / "tests" / parser_file).parse(source)
                self.assertEqual(parsed["status"], "success", parsed)
                self.assertEqual(parsed, expected)
                grammar = load(ROOT / "tests" / output_file)
                native, python = Transpiler(grammar), reference.Transpiler(grammar)
                for _ in range(2):
                    self.assertEqual(native.transpile(parsed["ast"]), python.transpile(expected["ast"]))
                    self.assertEqual(native.state, python.state)

    def test_prepared_transpiler_reuse_from_threads(self):
        transpiler = Transpiler({"rules": {"x": {"template": "<{children}>"}}})
        asts = [{"tag": "x", "children": [{"text": str(i)}]} for i in range(40)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(transpiler.transpile, asts)), [f"<{i}>" for i in range(40)])

    def test_runtime_math_parser_and_transpiler(self):
        parser = Parser(load(ROOT / "tests/calculator_parser.yaml"))
        transpiler = Transpiler(load(Path(__file__).with_name("math_to_slip.yaml")))
        for source, expected in (
            ("10 + 5 * 2", "(10 + (5 * 2))"),
            ("8 - 2 - 1", "((8 - 2) - 1)"),
            ("2 ^ 3 ^ 2", "(2 ** (3 ** 2))"),
            ("9007199254740993 + 1", "(9007199254740993 + 1)"),
        ):
            result = parser.parse(source, start_rule="expression")
            self.assertEqual(result["status"], "success", result)
            self.assertEqual(transpiler.transpile(result["ast"]), expected)


if __name__ == "__main__":
    unittest.main()
