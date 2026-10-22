"""Check native YAML data against safer-yaml, including scalar types and order."""

import argparse
import json
from pathlib import Path
import subprocess

from safer_yaml import loads


def same(actual, expected):
    assert type(actual) is type(expected), (actual, expected)
    assert actual == expected, (actual, expected)
    if isinstance(expected, dict):
        assert list(actual) == list(expected)
        for key in expected:
            same(actual[key], expected[key])
    elif isinstance(expected, list):
        for left, right in zip(actual, expected):
            same(left, right)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("grammars", nargs="+", type=Path)
    args = parser.parse_args()
    scalars = ["yes", "no", "on", "off", "true", "false", "True", "FALSE", "null", "NULL", "~",
               "0", "-0", "+001", "001", "0o17", "0xFF", "1.25", "123.0", "1e3", ".5", "1.",
               "2026-01-01", "1_000", "1:20", "TrUe", "9007199254740993", "18446744073709551615"]
    cases = [f"value: {scalar}\n" for scalar in scalars]
    cases += [f"value: {json.dumps(scalar)}\n" for scalar in scalars]
    cases += ['value: "a\\u0000b"\n', 'value: "café\\n\\u263a"\n', 'value: "\\b\\f\\r\\t\\\\\\\""\n',
              "value: |\n  true\n  null\n", "value: >\n  yes\n  off\n", "value: \n",
              "first: &a {word: yes}\nsecond: *a\n", "a:\ttrue\n"]
    cases += ["value: !!str true\n", 'value: !!bool "true"\n', 'value: !!null "null"\n',
              'value: !!int "123"\n', "value: !!float 1\n"]
    cases += ['{"a":{}}', '{"a":"b{{c}}","d":[1,{},true,null]}', '[{"x":1},{"y":2}]']
    cases += [path.read_text(encoding="utf-8") for path in args.grammars]
    for source in cases:
        result = subprocess.run([args.executable], input=source, text=True, encoding="utf-8", capture_output=True)
        assert result.returncode == 0, (source, result.stdout, result.stderr)
        same(json.loads(result.stdout), loads(source))
    for source in ("{", "a: 1\na: 2\n", "---\na: 1\n---\nb: 2\n",
                   '{"a":1,"a":2}', '{"a":', '{"a":1}{"b":2}'):
        result = subprocess.run([args.executable], input=source, text=True, encoding="utf-8", capture_output=True)
        assert result.returncode == 1, (source, result)
    print(f"{len(cases)} document comparisons passed, including {len(args.grammars)} unchanged grammar files")


if __name__ == "__main__":
    main()
