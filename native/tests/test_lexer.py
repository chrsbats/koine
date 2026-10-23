import copy
import importlib.util
from pathlib import Path
import re
import sys
import unittest

from safer_yaml import load

from koine import Parser, PlaceholderParser


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("lexer_reference", ROOT / "python/koine/parser.py")
reference = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reference
spec.loader.exec_module(reference)


def token_grammar(lexer):
    config = copy.deepcopy(lexer)
    for token in config["tokens"]:
        token.pop("ast", None)
    names = {token["token"] for token in config["tokens"] if "token" in token}
    names.update(("INDENT", "DEDENT"))
    # The reference encodes tokens as name strings; try longer labels first.
    choices = [{"token": name} for name in sorted(names, key=lambda name: (-len(name), name))]
    return {"lexer": config, "start_rule": "all", "rules": {"all": {
        "ast": {"promote": True}, "zero_or_more": {"choice": choices},
    }}}


class NativeLexerTests(unittest.TestCase):
    def assert_same(self, grammar, source, start_rule=None, placeholders=False):
        native_type = PlaceholderParser if placeholders else Parser
        python_type = reference.PlaceholderParser if placeholders else reference.Parser
        actual = native_type(grammar).parse(source, start_rule=start_rule)
        expected = python_type(grammar).parse(source, start_rule=start_rule)
        self.assertEqual(actual["status"], expected["status"], (source, actual, expected))
        if expected["status"] == "success":
            self.assertEqual(actual["ast"], expected["ast"])
        else:
            self.assertEqual(re.search(r"L\d+:C\d+", actual["message"]).group(),
                             re.search(r"L\d+:C\d+", expected["message"]).group(), (source, actual, expected))
        return actual

    def test_longest_match_and_first_specification_ties(self):
        lexer = {"tokens": [
            {"regex": r"\s+", "action": "skip"},
            {"regex": "if", "token": "IF"},
            {"regex": "[a-z]+", "token": "NAME"},
            {"regex": "=", "token": "EQ"},
            {"regex": "==", "token": "EQEQ"},
        ]}
        result = self.assert_same(token_grammar(lexer), "if iffy = ==")
        self.assertEqual([token["tag"] for token in result["ast"]], ["IF", "NAME", "EQ", "EQEQ"])
        lexer["tokens"][1:3] = reversed(lexer["tokens"][1:3])
        result = self.assert_same(token_grammar(lexer), "if")
        self.assertEqual(result["ast"][0]["tag"], "NAME")

    def test_raw_tokens_normalization_unicode_and_indentation(self):
        lexer = {"tokens": [
            {"regex": "[ \\t]+", "action": "skip"},
            {"regex": "\\n[ \\t]*", "action": "handle_indent"},
            {"regex": "'[^']*'", "token": "STRING"},
            {"regex": r"\w+", "token": "WORD"},
            {"regex": r"\x00", "token": "NUL"},
        ]}
        grammar = token_grammar(lexer)
        native = Parser(grammar)
        python = reference.StatefulLexer(lexer)
        for source in ("", " \t\r\n", "a\n    b\n        café\n    d\ne", "a\n\n    b\n\n    c\n",
                       "a\r\n\tb\r\n\t\tcafé\r\n\td\r\ne", "a\r\tb", "é\t'café\tz'", "a\0b", "a\n    b\n  \n"):
            with self.subTest(source=source):
                expected = [{"tag": t.type, "text": t.value, "line": t.line, "col": t.col, "value": t.value}
                            for t in python.tokenize(source)]
                actual = native.parse(source)
                self.assertEqual(actual["status"], "success", actual)
                self.assertEqual(actual["ast"], expected)

    def test_complete_subject_assertions_in_lexer_regexes(self):
        lexer = {"tokens": [{"regex": "a", "token": "A"}, {"regex": r"(?<=a)b\Z", "token": "B"}]}
        grammar = token_grammar(lexer)
        self.assertEqual(self.assert_same(grammar, "ab")["status"], "success")
        self.assertEqual(self.assert_same(grammar, "abb")["status"], "error")

    def test_empty_stream_aliases_wrapped_leaves_and_placeholders(self):
        lexer = {"tokens": [{"regex": r"\s+", "action": "skip"}, {"regex": r"\w+", "token": "NAME"}]}
        for node, source in (
            ({"token": "NAME"}, "café"),
            ({"choice": [{"token": "NAME"}], "ast": {"tag": "ignored_alias"}}, "hello"),
            ({"sequence": [{"token": "NAME"}, {"token": "NAME"}], "ast": {"leaf": True, "tag": "joined"}}, "a b"),
            ({"optional": {"token": "NAME"}, "ast": {"promote": True}}, "  \n"),
        ):
            self.assert_same({"lexer": lexer, "start_rule": "main", "rules": {"main": node}}, source)
        grammar = {"lexer": lexer, "start_rule": "main", "rules": {"main": {"sequence": [
            {"subgrammar": {"file": "missing.yaml", "placeholder": {"token": "NAME"}}, "ast": {"name": "part"}},
        ]}}}
        self.assert_same(grammar, "hello", placeholders=True)

    def test_token_ast_directives_and_alternate_starts(self):
        grammar = {"lexer": {"tokens": [
            {"regex": "[ \\t]+", "action": "skip"},
            {"regex": "[0-9]+", "token": "NUMBER", "ast": {"type": "number"}},
            {"regex": "=", "token": "EQUALS", "ast": {"discard": True}},
            {"regex": "true|false", "token": "BOOL", "ast": {"type": "bool"}},
            {"regex": "none", "token": "NIL", "ast": {"type": "null"}},
        ]}, "start_rule": "main", "rules": {"main": {"sequence": [
            {"token": "NUMBER", "ast": {"leaf": True, "tag": "number", "type": "number"}},
            {"token": "EQUALS"}, {"token": "BOOL"}, {"token": "NIL"},
        ]}}}
        self.assert_same(grammar, "123 = true none")
        self.assert_same(grammar, "17", start_rule="NUMBER")
        parser = Parser(grammar)
        token = "9007199254740993"
        result = parser.parse(token, start_rule="NUMBER")["ast"]
        self.assertEqual(result["text"], token)
        self.assertEqual(result["value"], 9007199254740993)
        with self.assertRaisesRegex(ValueError, "range"):
            parser.parse("18446744073709551616", start_rule="NUMBER")

    def test_unicode_decimal_number_values_preserve_text(self):
        grammar = {"lexer": {"tokens": [
            {"regex": r"\d+(\.\d+)?", "token": "NUMBER", "ast": {"type": "number"}},
        ]}, "start_rule": "number", "rules": {"number": {"token": "NUMBER"}}}
        for source in ("١٢٣", "１２３", "𝟡𝟚", "١٢٣.٤٥"):
            result = self.assert_same(grammar, source)
            self.assertEqual(result["ast"]["text"], source)
        source = "٩٠٠٧١٩٩٢٥٤٧٤٠٩٩٣"
        result = Parser(grammar).parse(source)["ast"]
        self.assertEqual(result["text"], source)
        self.assertEqual(result["value"], 9007199254740993)

    def test_source_mapped_errors_and_reuse_after_failures(self):
        grammar = load(ROOT / "tests/py_parser.yaml")
        native = Parser(grammar)
        for source in ("def f():\n    a = $", "def f():\r\n\ta = $", "def f():\n    a = 1\n  b = 2",
                       "def f():\n    return for", "def f(x, y):\n    return", "", " \r\n\t"):
            with self.subTest(source=source):
                result = self.assert_same(grammar, source)
                self.assertEqual(result["status"], "error")
                self.assertEqual(native.parse(source)["status"], "error")
        self.assertEqual(native.parse("def f():\n    return 1")["status"], "success")

    def test_raw_python_javascript_asts(self):
        for filename, sources in (
            ("py_parser.yaml", ["def f(x):\n    return x", "def f(x):\r\n\treturn x\r\n",
                                "def f(x):\n\n    a = 0\n\n    return a\n"]),
            ("js_parser.yaml", ["function f(x) { return x; }", "function f(x) {\r\n\tlet a = 0;\r\n\treturn a;\r\n}"]),
        ):
            grammar = load(ROOT / "tests" / filename)
            for source in sources:
                with self.subTest(filename=filename, source=source):
                    self.assert_same(grammar, source)

    def test_invalid_token_grammars_and_nonprogress(self):
        for part in ({"literal": "x"}, {"regex": "x"}):
            with self.subTest(part=part), self.assertRaisesRegex(ValueError, "not supported when a lexer is defined"):
                Parser({"lexer": {"tokens": []}, "start_rule": "main", "rules": {"main": part}})
        # The reference lacks a progress guard; do not invoke its infinite loop.
        grammar = token_grammar({"tokens": [{"regex": r"\s*", "action": "skip"}, {"regex": "a", "token": "A"}]})
        parser = Parser(grammar)
        result = parser.parse("!")
        self.assertEqual(result["status"], "error")
        self.assertIn("matched empty input", result["message"])
        self.assertEqual(parser.parse("a")["status"], "success")


if __name__ == "__main__":
    unittest.main()
