"""Run deployed Nim consumers with the bundled library beside the executable."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("library", type=Path)
    args.add_argument("fixtures", type=Path)
    args.add_argument("executables", type=Path, nargs="+")
    options = args.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        library = root / "libkoine.so"
        shutil.copy2(options.library, library)
        env = dict(os.environ, LD_DEBUG="libs", KOINE_FIXTURES=str(options.fixtures))
        env.pop("LD_LIBRARY_PATH", None)
        env.pop("NIMBLE_DIR", None)
        for source in options.executables:
            executable = root / source.name
            shutil.copy2(source, executable)
            result = subprocess.run([executable], cwd=root, env=env, capture_output=True, text=True, check=True)
            assert result.stdout.count("[OK]") == 8, result.stdout
            assert f"calling init: {library}" in result.stderr, result.stderr
    print(f"{len(options.executables)} deployed Nim consumers passed eight cases each; $ORIGIN loaded the adjacent library")


if __name__ == "__main__":
    main()
