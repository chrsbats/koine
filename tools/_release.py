"""Run release subprocesses with repository-owned caches and temporary files."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(command, *, env=None):
    environment = os.environ.copy()
    if env is not None:
        environment.update(env)
    # Override inherited locations: release commands must not populate home or
    # system temporary directories, including managed Python downloads by uv.
    for name, relative in {
        "UV_CACHE_DIR": "build/cache/uv",
        "PIP_CACHE_DIR": "build/cache/pip",
        "XDG_CACHE_HOME": "build/cache",
        "UV_PYTHON_INSTALL_DIR": "build/toolchain/python",
        "TMPDIR": "build/tmp",
        "TMP": "build/tmp",
        "TEMP": "build/tmp",
    }.items():
        path = ROOT / relative
        path.mkdir(parents=True, exist_ok=True)
        environment[name] = str(path)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    print("+", " ".join(map(str, command)), flush=True)
    subprocess.run(command, cwd=ROOT, env=environment, check=True)
