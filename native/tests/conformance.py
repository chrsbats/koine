"""Run unchanged Koine parser and transpiler cases through native entry points."""

from pathlib import Path

import pytest

import koine
import koine.parser


ROOT = Path(__file__).resolve().parents[2]


def backend_only(*args, **kwargs):
    raise AssertionError("Parsimonious grammar-string helpers are not native behavioral tests")


# Required only to import the mixed test_edges module. Any accidental call fails.
koine.parser.transpile_grammar = backend_only

if __name__ == "__main__":
    args = ["-q", "--capture=no", "-p", "no:cacheprovider", "--import-mode=importlib", str(ROOT / "tests")]
    for name in ("disallows_literal_when_lexer_defined", "subgrammar_placeholder_injection",
                 "sequence_of_one_injects_noop", "rule_ref_with_ast_is_wrapped"):
        args += ["--deselect", f"tests/test_edges.py::test_transpile_grammar_{name}"]
    raise SystemExit(pytest.main(args))
