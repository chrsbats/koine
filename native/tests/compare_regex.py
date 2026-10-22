"""Compare real grammar regex terminals through the native API with Python regex.

Requires the Python reference's safer-yaml and regex dependencies. Pass grammar
filenames explicitly so a missing corpus cannot silently turn into a passing test.
"""

import argparse
from pathlib import Path

import regex
from safer_yaml import load

from koine import Parser


def patterns(node):
    if isinstance(node, dict):
        if "regex" in node:
            yield node["regex"]
        for value in node.values():
            yield from patterns(value)
    elif isinstance(node, list):
        for value in node:
            yield from patterns(value)


SAMPLES = [
    "", "a", "abc", "on", "off", "123", "-2.5", "1e3", "true", "none",
    "a.b", "../a", "|../a.b[i1:i2](key1)/c[>i3]#(m)",
    "http://example.org/a-b?q=2", "file://./a", "def f(x):\n    return x",
    "a: 1\nb: 2", " \t\r\n", "\n", "x\n", "café", "é\nb", "١٢",
    "\u2003x", "\u00a0", "'raw'", '"a\\\"b"', "[x]", "#[1,2]", "#{a:1}",
    "{-- nested {--comment--} --}", "(x)", "#(m)", "rest...", "a->b", "x]", "\x00",
]


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("grammars", nargs="+", type=Path)
    paths = args.parse_args().grammars
    corpus = sorted({pattern for path in paths for pattern in patterns(load(path))})
    if not corpus:
        raise AssertionError("No regex terminals found in the supplied grammars")
    checks = 0
    for pattern in corpus:
        reference = regex.compile(pattern)
        for prefix in ("", ">", "é\n"):
            parser = Parser({"start_rule": "start", "rules": {
                "start": {"sequence": [
                    {"literal": prefix, "ast": {"discard": True}},
                    {"rule": "value"},
                    {"regex": r"[\s\S]*", "ast": {"discard": True}},
                ]},
                "value": {"regex": pattern, "ast": {"leaf": True}},
            }})
            for sample in SAMPLES:
                subject = prefix + sample
                expected = reference.match(subject, len(prefix))
                actual = parser.parse(subject)
                context = (pattern, repr(prefix), repr(sample), actual)
                assert (actual["status"] == "success") == (expected is not None), context
                if expected is not None:
                    leaf = actual["ast"]["children"][0]
                    assert leaf["text"] == expected.group(), context
                    assert leaf["line"] == prefix.count("\n") + 1, context
                    assert leaf["col"] == len(prefix.rsplit("\n", 1)[-1]) + 1, context
                checks += 1
    print(f"{checks} comparisons passed: {len(corpus)} distinct regexes from {len(paths)} grammar files")


if __name__ == "__main__":
    main()
