"""Measure equal ordinary API calls, including native JSON emission/conversion."""
import argparse
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

from safer_yaml import load
from koine import Parser, Transpiler


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("benchmark_reference", ROOT / "reference/koine/parser.py")
reference = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reference
spec.loader.exec_module(reference)


def measure(parser, source, start, transpiler, iterations):
    samples = []
    for _ in range(3):
        begin = time.perf_counter()
        for _ in range(iterations):
            parsed = parser.parse(source, start_rule=start)
            assert parsed["status"] == "success"
            if transpiler:
                transpiler.transpile(parsed["ast"])
        samples.append((time.perf_counter() - begin) / iterations)
    return statistics.median(samples)


def measure_combined(parser, transpiler, source, start, iterations):
    samples = []
    for _ in range(3):
        begin = time.perf_counter()
        for _ in range(iterations):
            result = parser.parse_transpile(source, transpiler, start_rule=start)
            assert result["status"] == "success"
        samples.append((time.perf_counter() - begin) / iterations)
    return statistics.median(samples)


def measure_decode(result, iterations):
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    samples = []
    for _ in range(3):
        begin = time.perf_counter()
        for _ in range(iterations):
            json.loads(encoded)
        samples.append((time.perf_counter() - begin) / iterations)
    return statistics.median(samples)


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--nim-executable", type=Path, required=True)
    args.add_argument("--slip-root", type=Path, required=True)
    options = args.parse_args()
    cases = [("math parse+transpile", ROOT / "tests/calculator_parser.yaml", "10 + 5 * 2", "expression",
              Path(__file__).with_name("math_to_slip.yaml"), 200),
             ("tokenized Python parse+transpile", ROOT / "tests/py_parser.yaml", "def f(x):\n    a = 0\n    return a", None,
              ROOT / "tests/py_to_js_transpiler.yaml", 100),
             ("complete SLIP root parse", options.slip_root / "grammar/slip_grammar.yaml",
              (options.slip_root / "slip/root.slip").read_text(encoding="utf-8"), None, None, 3)]
    report = []
    with tempfile.TemporaryDirectory() as directory:
        for name, grammar, source, start, output, iterations in cases:
            native = Parser.from_file(grammar)
            python = reference.Parser.from_file(grammar)
            expected = python.parse(source, start_rule=start)
            assert native.parse(source, start_rule=start) == expected, name
            native_output = Transpiler.from_file(output) if output else None
            python_output = reference.Transpiler(load(output)) if output else None
            expected_text = python_output.transpile(expected["ast"]) if python_output else ""
            if native_output:
                assert native_output.transpile(expected["ast"]) == expected_text
            source_path = Path(directory) / "input.txt"
            source_path.write_text(source, encoding="utf-8")
            nim_samples = []
            nim_combined_samples = []
            nim_decode_samples = []
            for _ in range(3):
                nim = json.loads(subprocess.check_output([
                    options.nim_executable, grammar, source_path, str(iterations), start or "", str(output) if output else ""
                ], text=True))
                assert nim["result"] == expected and nim["text"] == expected_text, name
                nim_samples.append(nim["seconds_per_call"])
                nim_combined_samples.append(nim["combined_seconds_per_call"])
                nim_decode_samples.append(nim["json_decode_seconds"])
            report.append({"case": name, "iterations_per_sample": iterations, "samples": 3,
                "python_reference_ms": measure(python, source, start, python_output, iterations) * 1000,
                "native_python_ms": measure(native, source, start, native_output, iterations) * 1000,
                "native_python_combined_ms":
                    measure_combined(native, native_output, source, start, iterations) * 1000
                    if native_output else None,
                "native_nim_ms": statistics.median(nim_samples) * 1000,
                "native_nim_combined_ms": statistics.median(nim_combined_samples) * 1000
                    if native_output else None,
                "python_json_decode_ms": measure_decode(expected, iterations) * 1000,
                "nim_json_decode_ms": statistics.median(nim_decode_samples) * 1000})
    print(json.dumps({"native_package": __import__("koine").__file__, "results": report}, indent=2))


if __name__ == "__main__":
    main()
