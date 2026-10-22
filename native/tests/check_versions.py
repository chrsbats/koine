"""Verify every distribution/project config declares the same Koine version."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def version(path, pattern):
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, path
    return match.group(1)


def main():
    versions = {
        "pyproject.toml": version(ROOT / "pyproject.toml", r'^version\s*=\s*"([^"]+)"'),
        "native/pyproject.toml": version(ROOT / "native/pyproject.toml", r'^version\s*=\s*"([^"]+)"'),
        "koine.nimble": version(ROOT / "koine.nimble", r'^version\s*=\s*"([^"]+)"'),
    }
    assert len(set(versions.values())) == 1, versions
    print(f"All project configs declare version {next(iter(versions.values()))}")


if __name__ == "__main__":
    main()
