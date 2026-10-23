#!/usr/bin/env python3
"""Validate and publish saved Koine distributions.

The script only publishes artifacts for the version declared in pyproject.toml.
It never uploads older wheels left in the distribution directory. Without
--upload it performs validation and prints the upload command only. Credentials
come from the matching section in ~/.pypirc when present; otherwise the script
falls back to TWINE_USERNAME/TWINE_PASSWORD.
"""
import argparse
import configparser
import hashlib
import os
import re
import sys
from pathlib import Path

from _release import ROOT, run
REPOSITORY_URLS = {
    "testpypi": "https://test.pypi.org/legacy/",
    "pypi": "https://upload.pypi.org/legacy/",
}


def pypirc():
    parser = configparser.RawConfigParser()
    parser.read(Path.home() / ".pypirc", encoding="utf-8")
    return parser


def project_version():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("Could not read the version from pyproject.toml")
    return match.group(1)


def only_one(paths, description):
    paths = list(paths)
    if len(paths) != 1:
        raise SystemExit(
            f"Expected one {description}, found {len(paths)}: "
            + ", ".join(map(str, paths))
        )
    return paths[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dist",
        type=Path,
        default=ROOT / "dist",
        help="directory containing the saved distributions (default: dist)",
    )
    parser.add_argument(
        "--repository",
        choices=("testpypi", "pypi"),
        default="testpypi",
        help="upload target (default: testpypi)",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="upload after validation; otherwise only check",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="let twine skip files that already exist on the repository",
    )
    parser.add_argument(
        "--allow-missing-windows",
        action="store_true",
        help="validate without a Windows wheel",
    )
    options = parser.parse_args()

    version = project_version()
    run([sys.executable, str(ROOT / "native" / "tests" / "check_versions.py")])
    directory = options.dist.resolve()
    sdist = only_one(
        directory.glob(f"koine-{version}.tar.gz"), "source distribution"
    )
    pure_wheel = only_one(
        directory.glob(f"koine-{version}-py3-none-any.whl"), "pure wheel"
    )
    native_wheel = only_one(
        directory.glob(f"koine-{version}-py3-none-manylinux*.whl"),
        "portable Linux wheel",
    )
    windows = list(
        directory.glob(f"koine-{version}-py3-none-win_amd64.whl")
    )
    if len(windows) > 1:
        raise SystemExit(f"Found multiple Windows wheels: {windows}")
    if not windows and not options.allow_missing_windows:
        raise SystemExit(
            "Windows wheel is missing. Build it on Windows, pass its directory "
            "with --dist, or use --allow-missing-windows."
        )

    command = [
        sys.executable,
        str(ROOT / "native" / "tests" / "check_distribution.py"),
        str(sdist),
        str(pure_wheel),
        str(native_wheel),
    ]
    artifacts = [sdist, pure_wheel, native_wheel]
    if windows:
        artifacts.append(windows[0])
        command.extend(["--windows-wheel", str(windows[0])])
    run(command)

    run(
        [
            "uv",
            "run",
            "--no-project",
            "--with",
            "twine",
            "python",
            "-m",
            "twine",
            "check",
            "--strict",
            *map(str, artifacts),
        ]
    )

    print(f"Koine {version} artifacts:")
    for artifact in artifacts:
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        print(f"  {digest}  {artifact.name}")

    if not options.upload:
        print("Not uploading; pass --upload to publish.")
        return

    config = pypirc()
    upload = [
        "uv",
        "run",
        "--no-project",
        "--with",
        "twine",
        "python",
        "-m",
        "twine",
        "upload",
    ]
    environment = None
    if config.has_section(options.repository):
        upload.extend(["--repository", options.repository])
        if config.get(options.repository, "password", fallback=None):
            upload.append("--non-interactive")
    else:
        if not os.environ.get("TWINE_PASSWORD"):
            raise SystemExit(
                f"No [{options.repository}] section in ~/.pypirc. Add one, or "
                "set TWINE_USERNAME=__token__ and TWINE_PASSWORD before uploading."
            )
        environment = os.environ.copy()
        environment.setdefault("TWINE_USERNAME", "__token__")
        upload.extend(
            [
                "--repository-url",
                REPOSITORY_URLS[options.repository],
                "--non-interactive",
            ]
        )
    if options.skip_existing:
        upload.append("--skip-existing")
    upload.extend(map(str, artifacts))
    run(upload, env=environment)


if __name__ == "__main__":
    main()
