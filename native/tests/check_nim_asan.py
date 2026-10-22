"""Exercise automatic Nim resource cleanup with an ASan/UBSan native build."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nim", type=Path)
    parser.add_argument("asan_build", type=Path)
    options = parser.parse_args()
    project = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        subprocess.run(["cmake", "--install", options.asan_build, "--prefix", root, "--component", "nim"], check=True)
        shutil.copy2(project / "nim/koine.nim", root / "koine.nim")
        for backend in ("c", "cpp"):
            executable = root / f"consumer-{backend}"
            compiler = os.environ.get("CXX", "g++") if backend == "cpp" else os.environ.get("CC", "gcc")
            key = "gcc.cpp" if backend == "cpp" else "gcc"
            subprocess.run([options.nim, backend, "-d:useMalloc", f"--path:{root}",
                f"--nimcache:{root / ('cache-' + backend)}", f"--out:{executable}",
                f"--{key}.exe:{compiler}", f"--{key}.linkerexe:{compiler}",
                "--passC:-fsanitize=address,undefined -fno-omit-frame-pointer",
                "--passL:-fsanitize=address,undefined", project / "native/tests/test_nim.nim"], check=True)
            env = dict(os.environ, KOINE_FIXTURES=str(project / "tests"),
                       ASAN_OPTIONS="detect_leaks=1", UBSAN_OPTIONS="halt_on_error=1")
            result = subprocess.run([executable], env=env, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
            assert result.stdout.count("[OK]") == 8, result.stdout
            print(result.stdout, end="")
    print("Both Nim backends passed automatic ownership/cleanup checks under ASan/UBSan with leak detection")


if __name__ == "__main__":
    main()
