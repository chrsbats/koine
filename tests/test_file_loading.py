import json

import pytest

from koine import Parser, PlaceholderParser


@pytest.mark.parametrize("parser_class", [Parser, PlaceholderParser])
@pytest.mark.parametrize("word", ["yes", "no", "on", "off"])
def test_from_file_uses_yaml_12_scalars(tmp_path, parser_class, word):
    grammar_path = tmp_path / "grammar.yaml"
    grammar_path.write_text(
        "start_rule: word\n"
        "rules:\n"
        "  word:\n"
        "    ast: {leaf: true, discard: false}\n"
        f"    literal: {word}\n",
        encoding="utf-8",
    )

    parser = parser_class.from_file(grammar_path)

    assert parser.parse(word) == {
        "status": "success",
        "ast": {"tag": "word", "text": word, "line": 1, "col": 1},
    }


def test_from_file_uses_yaml_12_in_relative_subgrammars(tmp_path):
    child_dir = tmp_path / "nested"
    child_dir.mkdir()
    (child_dir / "child.yaml").write_text(
        "start_rule: off\n"
        "rules:\n"
        "  off:\n"
        "    ast: {leaf: true}\n"
        "    literal: no\n",
        encoding="utf-8",
    )
    grammar_path = tmp_path / "grammar.yaml"
    grammar_path.write_text(
        "start_rule: command\n"
        "rules:\n"
        "  command:\n"
        "    sequence:\n"
        "      - {literal: 'say ', ast: {discard: true}}\n"
        "      - subgrammar: {file: nested/child.yaml}\n"
        "        ast: {name: word}\n",
        encoding="utf-8",
    )

    parser = Parser.from_file(grammar_path)

    assert parser.parse("say no") == {
        "status": "success",
        "ast": {
            "tag": "command",
            "text": "say no",
            "line": 1,
            "col": 1,
            "children": {
                "word": {"tag": "Child_off", "text": "no", "line": 1, "col": 5},
            },
        },
    }


@pytest.mark.parametrize("parser_class", [Parser, PlaceholderParser])
def test_from_file_accepts_json(tmp_path, parser_class):
    grammar_path = tmp_path / "grammar.json"
    grammar_path.write_text(
        json.dumps({
            "start_rule": "word",
            "rules": {
                "word": {"ast": {"leaf": True, "discard": False}, "literal": "café"},
            },
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    parser = parser_class.from_file(str(grammar_path))

    assert parser.parse("café") == {
        "status": "success",
        "ast": {"tag": "word", "text": "café", "line": 1, "col": 1},
    }


def test_subgrammar_files_are_loaded_once(tmp_path, monkeypatch):
    import koine.parser as parser_module

    if not hasattr(parser_module, "safer_yaml"):
        pytest.skip("native package does not use the YAML loader")

    leaf = tmp_path / "leaf.yaml"
    leaf.write_text(
        "start_rule: word\n"
        "rules:\n"
        "  word:\n"
        "    literal: hi\n"
        "    ast: {leaf: true}\n",
        encoding="utf-8",
    )
    main = tmp_path / "main.yaml"
    main.write_text(
        "start_rule: main\n"
        "rules:\n"
        "  main:\n"
        "    sequence:\n"
        "      - subgrammar: {file: leaf.yaml}\n"
        "      - subgrammar: {file: leaf.yaml}\n",
        encoding="utf-8",
    )
    loads = {}
    original = parser_module.safer_yaml.load

    def counted(path):
        resolved = str(path)
        loads[resolved] = loads.get(resolved, 0) + 1
        return original(path)

    monkeypatch.setattr(parser_module.safer_yaml, "load", counted)
    parser = Parser.from_file(main)

    assert loads == {str(main.resolve()): 1, str(leaf.resolve()): 1}, loads
    assert parser.parse("hihi")["status"] == "success"
