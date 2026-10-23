"""Inspect saved distributions for the pure and native package variants."""
import argparse
from email.parser import Parser
from pathlib import Path
import re
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
VERSION = re.search(
    r'^version\s*=\s*"([^"]+)"',
    (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
    re.MULTILINE,
).group(1)


def metadata(archive):
    name = next(item for item in archive.namelist() if item.endswith("/METADATA"))
    return Parser().parsestr(archive.read(name).decode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sdist", type=Path)
    parser.add_argument("pure_wheel", type=Path)
    parser.add_argument("native_wheel", type=Path)
    parser.add_argument("--windows-wheel", type=Path)
    args = parser.parse_args()
    with tarfile.open(args.sdist) as archive:
        names = archive.getnames()
        root = names[0].split("/")[0]
        relative = {name.removeprefix(root + "/") for name in names}
        for expected in ("pyproject.toml", "MANIFEST.in", "koine.nimble", "nim/koine.nim",
                         "native/pyproject.toml", "native/CMakeLists.txt", "native/src/koine.cpp",
                         "native/include/koine.h", "native/python/koine/parser.py",
                         "python/koine/parser.py", "tests/py_parser.yaml",
                         "tools/build.py", "tools/publish.py", "tools/_release.py"):
            assert expected in relative, expected
        for name in relative:
            assert not name.startswith("reference/"), name
            assert not name.startswith("nim/koine/"), name
            assert not any(part in (".git", "build", "dist", "__pycache__") for part in Path(name).parts), name
            assert not name.endswith((".so", ".a", ".dll", ".dylib", ".pyc")), name
        source = archive.extractfile(f"{root}/pyproject.toml").read().decode()
        assert "setuptools.build_meta" in source, "sdist must build the pure package by default"

    with zipfile.ZipFile(args.pure_wheel) as archive:
        names = archive.namelist()
        assert "koine/__init__.py" in names and "koine/parser.py" in names
        assert not any(name.endswith(("/libkoine.so", "/libkoine.dylib", "/koine.dll")) for name in names)
        assert not any(name.startswith(("python/", "reference/", "native/", "nim/")) for name in names)
        info = metadata(archive)
        assert info["Name"] == "koine" and info["Version"] == VERSION
        requirements = " ".join(info.get_all("Requires-Dist", []))
        assert "parsimonious" in requirements and "safer-yaml" in requirements, requirements
        wheel = archive.read(next(name for name in names if name.endswith("/WHEEL"))).decode()
        assert "Tag: py3-none-any" in wheel, wheel

    with zipfile.ZipFile(args.native_wheel) as archive:
        names = archive.namelist()
        assert "koine/__init__.py" in names and "koine/libkoine.so" in names
        assert not any(name.startswith(("python/", "reference/", "nim/")) for name in names)
        for library in ("koine", "pcre2", "cpp-peglib", "nlohmann-json", "rapidyaml-c4core", "fast_float"):
            assert f"koine/licenses/{library}.txt" in names, library
        info = metadata(archive)
        assert info["Name"] == "koine" and info["Version"] == VERSION
        assert not info.get_all("Requires-Dist", []), info.get_all("Requires-Dist")
        wheel = archive.read(next(name for name in names if name.endswith("/WHEEL"))).decode()
        assert "Root-Is-Purelib: false" in wheel
        assert "Tag: py3-none-manylinux" in wheel, wheel

    if args.windows_wheel:
        with zipfile.ZipFile(args.windows_wheel) as archive:
            names = archive.namelist()
            assert "koine/__init__.py" in names and "koine/koine.dll" in names
            assert not any(name.endswith((".dll.a", ".lib", ".pdb")) for name in names), names
            info = metadata(archive)
            assert info["Name"] == "koine" and info["Version"] == VERSION
            assert not info.get_all("Requires-Dist", []), info.get_all("Requires-Dist")
            wheel = archive.read(next(name for name in names if name.endswith("/WHEEL"))).decode()
            assert "Root-Is-Purelib: false" in wheel
            assert "Tag: py3-none-win_amd64" in wheel, wheel
    print("Saved sdist, pure wheel, native wheel and Windows wheel contents verified")


if __name__ == "__main__":
    main()
