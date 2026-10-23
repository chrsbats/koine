#!/usr/bin/env python3
"""Build Koine source and portable Linux distributions.

The pure sdist/universal wheel and the portable Linux native wheel are built into
a staging directory and verified before being copied to the output directory. A
Windows wheel cannot be cross-built on Linux; pass an existing one with
--windows-wheel when preparing a complete release.
"""
import argparse
import hashlib
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from _release import ROOT, run


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
        "--out",
        type=Path,
        default=ROOT / "dist",
        help="directory for the completed distributions (default: dist)",
    )
    parser.add_argument(
        "--windows-wheel",
        type=Path,
        help="existing Windows wheel to include in the release",
    )
    parser.add_argument(
        "--sdk",
        type=Path,
        default=Path(
            os.environ.get(
                "KOINE_SDK_ROOT", ROOT / "build" / "sdk-alma8-gcc15"
            )
        ),
        help="GCC 15/glibc 2.28 SDK (default: KOINE_SDK_ROOT or "
        "build/sdk-alma8-gcc15)",
    )
    options = parser.parse_args()

    version = project_version()
    run([sys.executable, str(ROOT / "native" / "tests" / "check_versions.py")])
    output = options.out.resolve()
    sdk = options.sdk.resolve()
    if not (sdk / "sysroot").is_dir():
        raise SystemExit(
            f"Release SDK not found at {sdk}. Create it with:\n"
            "  uv run --with libarchive-c python "
            "native/tools/prepare_linux_sdk.py build/sdk-alma8-gcc15"
        )
    output.mkdir(parents=True, exist_ok=True)

    build_root = ROOT / "build"
    build_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="koine-release-", dir=build_root
    ) as temporary:
        staging = Path(temporary)
        pure = staging / "pure"
        native = staging / "native"
        raw = staging / "raw"
        for directory in (pure, native, raw):
            directory.mkdir()

        run(
            [
                "uv",
                "build",
                "--sdist",
                "--wheel",
                "--out-dir",
                str(pure),
            ]
        )

        environment = os.environ.copy()
        environment["KOINE_SDK_ROOT"] = str(sdk)
        environment["CMAKE_TOOLCHAIN_FILE"] = str(
            ROOT / "native" / "tools" / "linux-gcc15.cmake"
        )
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(
            [
                str(sdk / "compiler-runtime" / "usr" / "lib64"),
                str(
                    sdk
                    / "sysroot"
                    / "opt"
                    / "rh"
                    / "gcc-toolset-15"
                    / "root"
                    / "usr"
                    / "lib64"
                ),
            ]
        )
        run(
            [
                "uv",
                "build",
                "native/",
                "--wheel",
                "--out-dir",
                str(raw),
            ],
            env=environment,
        )
        raw_wheel = only_one(raw.glob("koine-*.whl"), "raw Linux wheel")
        run(
            [
                "uv",
                "run",
                "--no-project",
                "--with",
                "auditwheel",
                "--with",
                "patchelf",
                "python",
                "-m",
                "auditwheel",
                "repair",
                "--plat",
                "manylinux_2_28_x86_64",
                "--wheel-dir",
                str(native),
                str(raw_wheel),
            ]
        )

        sdist = only_one(pure.glob(f"koine-{version}.tar.gz"), "sdist")
        pure_wheel = only_one(
            pure.glob(f"koine-{version}-py3-none-any.whl"), "pure wheel"
        )
        native_wheel = only_one(
            native.glob(f"koine-{version}-py3-none-manylinux*.whl"),
            "portable Linux wheel",
        )

        windows_wheel = None
        if options.windows_wheel is not None:
            source = options.windows_wheel.resolve()
            expected = f"koine-{version}-py3-none-win_amd64.whl"
            if source.name != expected:
                raise SystemExit(
                    f"Windows wheel must be named {expected}, got {source.name}"
                )
            if not source.is_file():
                raise SystemExit(f"Windows wheel not found: {source}")
            windows_wheel = native / expected
            shutil.copy2(source, windows_wheel)

        command = [
            sys.executable,
            str(ROOT / "native" / "tests" / "check_distribution.py"),
            str(sdist),
            str(pure_wheel),
            str(native_wheel),
        ]
        if windows_wheel is not None:
            command.extend(["--windows-wheel", str(windows_wheel)])
        run(command)

        artifacts = [sdist, pure_wheel, native_wheel]
        if windows_wheel is not None:
            artifacts.append(windows_wheel)
        patterns = [
            f"koine-{version}.tar.gz",
            f"koine-{version}-py3-none-any.whl",
            f"koine-{version}-py3-none-manylinux*.whl",
        ]
        if windows_wheel is not None:
            patterns.append(f"koine-{version}-py3-none-win_amd64.whl")
        for pattern in patterns:
            for existing in output.glob(pattern):
                existing.unlink()
        for artifact in artifacts:
            shutil.copy2(artifact, output / artifact.name)

    print(f"Built Koine {version} distributions in {output}")
    for artifact in sorted(output.glob(f"koine-{version}*")):
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        print(f"  {digest}  {artifact.name}")


if __name__ == "__main__":
    main()
