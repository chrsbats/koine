import std/[json, os, tempfiles, unittest]
import koine

let fixtures = getEnv("KOINE_FIXTURES")
doAssert fixtures.len > 0, "Set KOINE_FIXTURES to the existing grammar fixture directory"

suite "Koine's ordinary Nim API":
  test "runtime data, selectable starts, errors and automatic shared ownership":
    let grammar = %* {"start_rule": "word", "rules": {
      "word": {"regex": "[a-zé]+", "ast": {"leaf": true}}
    }}
    var saved: JsonNode
    var alias: Parser
    block:
      let parser = newParser(grammar)
      alias = parser
      saved = parser.parse("café", startRule = "word")
      check parser.validate("hello") == (true, "success")
      check not parser.validate("!").valid
      expect ValueError:
        discard parser.parse("x", startRule = "missing")
    check alias.parse("stillalive")["status"].getStr == "success"
    alias = nil
    check saved["ast"]["text"].getStr == "café"
    check saved["ast"]["col"].getInt == 1

  test "all exact numeric representations survive JsonNode and transpilation":
    let parser = newParser(%* {"start_rule": "n", "rules": {
      "n": {"regex": "[-+0-9.eE]+", "ast": {"type": "number"}}
    }})
    let transpiler = newTranspiler()
    for token in ["9007199254740993", "9223372036854775807", "-9223372036854775808",
                  "9223372036854775808", "18446744073709551615"]:
      let ast = parser.parse(token)["ast"]
      check ast["text"].getStr == token
      check $ast["value"] == token
      check transpiler.transpile(ast) == token
    check parser.parse("18446744073709551615")["ast"]["value"].to(uint64) == high(uint64)
    check parser.parse("123.5")["ast"]["value"].getFloat == 123.5
    expect ValueError:
      discard parser.parse("18446744073709551616")

  test "UTF-8 and embedded NUL are length-delimited":
    let source = "a\0é"
    let parser = newParser(%* {"start_rule": "main", "rules": {"main": {"literal": source}}})
    let ast = parser.parse(source)["ast"]
    check ast["text"].getStr == source
    check newTranspiler().transpile(ast) == source

  test "native YAML files, alternate starts, lexer and real output grammars":
    let parser = parserFromFile(fixtures / "calculator_parser.yaml")
    let transpiler = transpilerFromFile(fixtures / "calculator_to_lisp_transpiler.yaml")
    check transpiler.transpile(parser.parse("1 + 2 * 3", "expression")["ast"]) == "(add 1 (mul 2 3))"
    let python = parserFromFile(fixtures / "py_parser.yaml")
    let javascript = transpilerFromFile(fixtures / "py_to_js_transpiler.yaml")
    let parsed = python.parse("def f(x):\r\n\treturn x\r\n")
    check parsed["status"].getStr == "success"
    check javascript.transpile(parsed["ast"]) == "function f(x) {\n    return x;\n}"
    check placeholderParserFromFile(fixtures / "calculator_parser.yaml").validate("2").valid

  test "relative subgrammars, base paths and placeholders":
    let directory = createTempDir("koine-nim-", "")
    defer: removeDir(directory)
    writeFile(directory / "child.yaml", "start_rule: word\nrules:\n  word: {literal: no}\n")
    let grammar = %* {"start_rule": "main", "rules": {"main": {"subgrammar": {
      "file": "child.yaml", "placeholder": {"literal": "local"}
    }}}}
    check newParser(grammar, basePath = directory).parse("no")["ast"]["tag"].getStr == "Child_word"
    let placeholder = newPlaceholderParser(grammar)
    check placeholder.validate("local") == (true, "success")
    check not placeholder.validate("no").valid

  test "state snapshots, resets and failure recovery":
    let transpiler = newTranspiler(%* {"rules": {
      "seq": {"template": "{children}"},
      "x": {"cases": [
        {"if": {"path": "state.seen", "negate": true}, "then": "first"},
        {"default": "again"}
      ], "state_set": {"seen": true}}
    }})
    let ast = %* {"tag": "seq", "children": [{"tag": "x"}, {"tag": "x"}]}
    check transpiler.transpile(ast) == "first again"
    let snapshot = transpiler.state
    snapshot["seen"] = %false
    check transpiler.state["seen"].getBool
    expect ValueError:
      discard transpiler.transpile(%* {"tag": "invalid"})
    check transpiler.transpile(ast) == "first again"

  test "combined parse and transpile matches separate calls":
    let parser = parserFromFile(fixtures / "calculator_parser.yaml")
    let transpiler = transpilerFromFile(fixtures / "calculator_to_lisp_transpiler.yaml")
    let combined = parser.parseTranspile(transpiler, "1 + 2 * 3", "expression")
    check combined["status"].getStr == "success"
    check combined["text"].getStr == "(add 1 (mul 2 3))"
    check not combined.hasKey("ast")
    let failed = parser.parseTranspile(transpiler, "1 +", "expression")
    check failed["status"].getStr == "error"
    expect ValueError:
      discard parseTranspile(Parser(nil), transpiler, "1")

  test "construction failures and repeated deterministic cleanup":
    expect ValueError:
      discard newParser(%* {})
    expect ValueError:
      discard newTranspiler(%* [])
    expect ValueError:
      discard parserFromFile("koine-missing-file.yaml")
    expect ValueError:
      discard transpilerFromFile("koine-missing-file.yaml")
    expect ValueError:
      discard Parser(nil).parse("x")
    for i in 0..<100:
      let parser = newParser(%* {"start_rule": "x", "rules": {"x": {"literal": "x"}}})
      let transpiler = newTranspiler()
      check transpiler.transpile(parser.parse("x")["ast"]) == "x"
