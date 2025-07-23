from koine.parser import Parser, Transpiler
import yaml
import json

from pathlib import Path
TESTS_DIR = Path(__file__).parent

def test_calc():
    with open(TESTS_DIR / "calculator_grammar.yaml", "r") as f:
        my_grammar = yaml.safe_load(f)
    
    my_parser = Parser(my_grammar)
    my_transpiler = Transpiler(my_grammar)
    
    code_to_parse = "(2 * 3) ^ 5"
    valid, _ = my_parser.validate(code_to_parse)
    assert valid
    parse_result = my_parser.parse(code_to_parse)
    transpiled_code = my_parser.transpile(code_to_parse)['translation']
    
    expeected_result = {
        "tag": "binary_op",
        "op": {
            "tag": "power_op",
            "text": "^",
            "line": 1,
            "col": 9
        },
        "left": {
            "tag": "binary_op",
            "op": {
            "tag": "mul_op",
            "text": "*",
            "line": 1,
            "col": 4
            },
            "left": {
            "tag": "number",
            "text": "2",
            "line": 1,
            "col": 2,
            "value": 2
            },
            "right": {
            "tag": "number",
            "text": "3",
            "line": 1,
            "col": 6,
            "value": 3
            },
            "line": 1,
            "col": 4
        },
        "right": {
            "tag": "number",
            "text": "5",
            "line": 1,
            "col": 11,
            "value": 5
        },
        "line": 1,
        "col": 9
    }
    expected_translation = "(pow (mul 2 3) 5)"

    if parse_result['status'] == 'success':
        print("--- AST ---")
        print(json.dumps(parse_result['ast'], indent=2))
        assert parse_result['ast'] == expeected_result
        print("\n--- Transpiled Output ---")
        print(transpiled_code)
        assert transpiled_code == expected_translation
    else:
        print(f"Parse Error: {parse_result['message']}")

def test_advanced():
    with open(TESTS_DIR / "advanced_grammar.yaml", "r") as f:
        my_grammar = yaml.safe_load(f)

    my_parser = Parser(my_grammar)
    my_transpiler = Transpiler(my_grammar)

    
    test_cases = [
        "CLONE /path/to/repo TO /new/path",
        "CLONE /another/repo",
        "CLONE /bad/repo TO" # This should fail gracefully
    ]

    expected_asts =[ 
        {
            "tag": "clone_to",
            "text": "CLONE /path/to/repo TO /new/path",
            "line": 1,
            "col": 1,
            "children": {
                "repo": {
                "tag": "path",
                "text": "/path/to/repo",
                "line": 1,
                "col": 7
                },
                "dest": {
                "tag": "path",
                "text": "/new/path",
                "line": 1,
                "col": 24
                }
            }
        },
        {
            "tag": "clone",
            "text": "CLONE /another/repo",
            "line": 1,
            "col": 1,
            "children": {
                "repo": {
                "tag": "path",
                "text": "/another/repo",
                "line": 1,
                "col": 7
                }
            }
        },
        {}
    ]

    expected_translations = ["(clone-to /path/to/repo /new/path)","(clone /another/repo)",""]

    for code,expected_ast,expected_translation in zip(test_cases,expected_asts,expected_translations):
        print(f"--- Input: '{code}' ---")
        parse_result = my_parser.parse(code)
        
        if parse_result['status'] == 'success':
            print("✅ AST:")
            print(json.dumps(parse_result['ast'], indent=2))
            assert parse_result['ast'] == expected_ast
            print("\n✅ Transpiled Output:")
            transpiled_code = my_transpiler.transpile(parse_result['ast'])
            print(transpiled_code)
            assert transpiled_code == expected_translation
        else:
            print(f"❌ Parse Error: {parse_result['message']}")
        print("-" * 25)