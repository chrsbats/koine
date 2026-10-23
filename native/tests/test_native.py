import gc
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest

from koine import Parser, PlaceholderParser


class NativeParserTests(unittest.TestCase):
    def test_runtime_grammar_and_reuse(self):
        parser = Parser({"start_rule": "word", "rules": {"word": {"regex": r"\w+", "ast": {"leaf": True}}}})
        self.assertEqual(parser.parse("café"), {
            "status": "success", "ast": {"tag": "word", "text": "café", "line": 1, "col": 1},
        })
        self.assertEqual(parser.validate("hello"), (True, "success"))
        self.assertFalse(parser.validate("!hello")[0])
        self.assertFalse(parser.validate("hello!")[0])
        self.assertIn("L1:C5", parser.parse("café!")["message"])
        result = parser.parse("saved")
        del parser
        gc.collect()
        self.assertEqual(result["ast"]["text"], "saved")

    def test_matching_composition_and_positions(self):
        parser = Parser({"start_rule": "start", "rules": {
            "start": {"sequence": [
                {"literal": "é\n", "ast": {"discard": True}},
                {"positive_lookahead": {"regex": "[ab]"}},
                {"negative_lookahead": {"literal": "z"}},
                {"one_or_more": {"choice": [{"rule": "a"}, {"rule": "b"}]}},
                {"optional": {"literal": "!", "ast": {"discard": True}}},
            ]},
            "a": {"literal": "a"}, "b": {"regex": "b"},
        }})
        result = parser.parse("é\nabba!")
        self.assertEqual(result["status"], "success", result)
        self.assertEqual([node["text"] for node in result["ast"]["children"]], list("abba"))
        self.assertEqual(result["ast"]["children"][0]["line"], 2)
        self.assertEqual(result["ast"]["children"][0]["col"], 1)
        self.assertEqual(parser.parse("a", start_rule="a")["status"], "success")
        failure = parser.parse("é\nz")
        self.assertEqual(failure["status"], "error")
        self.assertIn("L2:C1", failure["message"])

    def test_literal_errors_retain_expected_and_unexpected_input(self):
        parser = Parser({"start_rule": "start", "rules": {"start": {"literal": "x"}}})
        for source in ("word", "é", "😀", ""):
            with self.subTest(source=source):
                result = parser.parse(source)
                self.assertEqual(result["status"], "error")
                self.assertIn("L1:C1", result["message"])
                self.assertIn("'x'", result["message"])
                self.assertIn(source if source else "end of input", result["message"])
        parser = Parser({"start_rule": "start", "rules": {"start": {"sequence": [
            {"literal": "é\n"}, {"choice": [{"literal": "x"}, {"literal": "y"}]},
        ]}}})
        result = parser.parse("é\nword")
        self.assertEqual(result["status"], "error")
        for detail in ("L2:C1", "word", "'x'", "'y'"):
            self.assertIn(detail, result["message"])

    def test_full_subject_regex_context(self):
        parser = Parser({"start_rule": "start", "rules": {
            "start": {"sequence": [
                {"literal": "x", "ast": {"discard": True}},
                {"rule": "tail"},
                {"optional": {"literal": "\n", "ast": {"discard": True}}},
            ]},
            "tail": {"regex": r"(?<=x)y\Z"},
        }})
        self.assertEqual(parser.parse("xy")["ast"]["children"][0]["text"], "y")
        self.assertEqual(parser.parse("xy\n")["status"], "error")

    def test_backtracking_and_recursive_rules(self):
        parser = Parser({"start_rule": "group", "rules": {
            "group": {"sequence": [
                {"literal": "("},
                {"choice": [
                    {"sequence": [{"literal": "a"}, {"literal": "b"}]},
                    {"literal": "ac"},
                    {"rule": "group"},
                ]},
                {"literal": ")"},
            ]},
        }})
        self.assertEqual(parser.parse("((ac))")["status"], "success")
        self.assertEqual(parser.parse("(ac)")["ast"]["children"][1]["text"], "ac")
        self.assertEqual(parser.parse("((ac)")["status"], "error")

    def test_nullable_repetition_terminates(self):
        parser = Parser({"start_rule": "start", "rules": {
            "start": {"zero_or_more": {"regex": ""}},
        }})
        self.assertEqual(parser.parse("")["status"], "success")

    def test_same_parser_can_be_called_from_threads(self):
        parser = Parser({"start_rule": "word", "rules": {"word": {"regex": "[a-z]+"}}})
        words = ["one", "two", "three", "four"] * 10
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(parser.parse, words))
        self.assertEqual([result["ast"]["text"] for result in results], words)

    def test_length_delimited_source(self):
        text = "a\0b"
        parser = Parser({"start_rule": "word", "rules": {"word": {"regex": r"[\s\S]+"}}})
        self.assertEqual(parser.parse(text)["ast"]["text"], text)

    def test_json_grammar_with_embedded_nul(self):
        text = "a\0b"
        parser = Parser({"start_rule": "word", "rules": {"word": {"literal": text}}})
        self.assertEqual(parser.parse(text)["ast"]["text"], text)

    def test_escaped_anchor_remains_literal(self):
        parser = Parser({"start_rule": "word", "rules": {"word": {"regex": r"\\Z"}}})
        self.assertEqual(parser.parse(r"\Z")["ast"]["text"], r"\Z")

    def test_yaml_12_json_and_unicode_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grammar.yaml"
            for word in ("yes", "no", "on", "off"):
                path.write_text(f"start_rule: off\nrules:\n  off:\n    literal: {word}\n"
                                "    ast: {leaf: true, discard: false}\n", encoding="utf-8")
                yaml_result = Parser.from_file(path).parse(word)
                self.assertEqual(yaml_result["ast"]["text"], word)
                json_path = Path(directory) / "grammar.json"
                json_path.write_text(json.dumps({"start_rule": "off", "rules": {
                    "off": {"literal": word, "ast": {"leaf": True, "discard": False}},
                }}), encoding="utf-8")
                self.assertEqual(Parser.from_file(json_path).parse(word), yaml_result)
            path = Path(directory) / "grammar.json"
            path.write_text(json.dumps({"start_rule": "word", "rules": {
                "word": {"literal": "café"},
            }}, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(Parser.from_file(path).parse("café")["ast"]["text"], "café")

    def test_errors_are_explicit(self):
        for grammar in (
            {"start_rule": "missing", "rules": {}},
            {"start_rule": "start", "rules": {"start": {"rule": "missing"}}},
            {"start_rule": "start", "rules": {"start": {"regex": "["}}},
            {"start_rule": "start", "rules": {"start": {"choice": []}}},
            {"start_rule": "start", "rules": {"start": {"literal": "x", "ast": {"promote": True, "discard": True}}}},
        ):
            with self.subTest(grammar=grammar), self.assertRaises(ValueError):
                Parser(grammar)

    def test_exact_numbers_and_overflow(self):
        parser = Parser({"start_rule": "n", "rules": {"n": {
            "regex": r"[-+0-9.eE]+", "ast": {"type": "number"},
        }}})
        for token, expected in (
            ("9007199254740993", 9007199254740993),
            ("-9223372036854775808", -(2**63)),
            ("9223372036854775807", 2**63 - 1),
            ("9223372036854775808", 2**63),
            ("18446744073709551615", 2**64 - 1),
            ("+001", 1), ("-0", 0), ("1.25", 1.25), ("1e3", 1000),
            ("123.0", 123), ("1e100", 1e100),
        ):
            with self.subTest(token=token):
                ast = parser.parse(token)["ast"]
                self.assertEqual(ast["text"], token)
                self.assertEqual(ast["value"], expected)
                self.assertIs(type(ast["value"]), type(expected))
        for token in ("18446744073709551616", "-9223372036854775809", "1e309"):
            with self.subTest(token=token), self.assertRaisesRegex(ValueError, "range"):
                parser.parse(token)

    def test_rejected_branch_does_not_convert_numbers(self):
        parser = Parser({"start_rule": "main", "rules": {
            "main": {"choice": [{"sequence": [{"rule": "n"}, {"literal": "!"}]}, {"regex": ".+"}]},
            "n": {"regex": "[0-9]+", "ast": {"type": "number"}},
        }})
        self.assertEqual(parser.parse("18446744073709551616")["status"], "success")

    def test_placeholder_does_not_load_dependencies(self):
        grammar = {"start_rule": "main", "rules": {"main": {
            "subgrammar": {"file": "does-not-exist.yaml", "placeholder": {"literal": "local"}},
        }}}
        self.assertEqual(PlaceholderParser(grammar).validate("local"), (True, "success"))
        with self.assertRaisesRegex(ValueError, "Could not open"):
            Parser(grammar)

    def test_explicit_base_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "child.yaml"
            path.write_text("start_rule: word\nrules:\n  word: {literal: child}\n", encoding="utf-8")
            parser = Parser({"start_rule": "main", "rules": {"main": {
                "subgrammar": {"file": "child.yaml"},
            }}}, base_path=directory)
            self.assertEqual(parser.parse("child")["ast"]["tag"], "Child_word")

    def test_unicode_files_base_paths_and_subgrammars(self):
        with tempfile.TemporaryDirectory(prefix="koine-语法-") as directory:
            base = Path(directory)
            child = base / "子目录" / "café.json"
            child.parent.mkdir()
            child.write_text(json.dumps({"start_rule": "word", "rules": {
                "word": {"literal": "café"},
            }}, ensure_ascii=False), encoding="utf-8")
            grammar = {"start_rule": "main", "rules": {"main": {"subgrammar": {
                "file": "子目录/café.json", "placeholder": {"literal": "local"},
            }}}}
            main = base / "主文件.json"
            main.write_text(json.dumps(grammar, ensure_ascii=False), encoding="utf-8")
            for parser in (Parser.from_file(main), Parser(grammar, base_path=base)):
                self.assertEqual(parser.parse("café"), {
                    "status": "success", "ast": {
                        "tag": "Café_word", "text": "café", "line": 1, "col": 1,
                    },
                })
            self.assertEqual(PlaceholderParser.from_file(main).validate("local"), (True, "success"))
            with self.assertRaises(ValueError) as failure:
                Parser.from_file(base / "不存在.json")
            self.assertIn("不存在.json", str(failure.exception))

    def test_recursive_matching_is_validated_at_construction(self):
        for node in ({"rule": "main"}, {"sequence": [{"regex": "(?=a)"}, {"rule": "main"}]}):
            with self.subTest(node=node), self.assertRaisesRegex(ValueError, "Left-recursion"):
                Parser({"start_rule": "main", "rules": {"main": node}})


if __name__ == "__main__":
    unittest.main()
