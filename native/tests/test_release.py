"""Release command boundaries, exercised with real child processes."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from _release import run


class ReleaseTests(unittest.TestCase):
    def test_children_use_repo_local_scratch_and_keep_build_settings(self):
        run([sys.executable, "-B", "-c", """
import os
from pathlib import Path
import tempfile

root = Path.cwd()
for name in ('UV_CACHE_DIR', 'PIP_CACHE_DIR', 'XDG_CACHE_HOME',
             'UV_PYTHON_INSTALL_DIR', 'TMPDIR', 'TMP', 'TEMP'):
    location = Path(os.environ[name]).resolve()
    assert root / 'build' in location.parents, (name, location)
    assert location.is_dir(), (name, location)
assert Path(tempfile.gettempdir()) == root / 'build/tmp'
with tempfile.TemporaryFile() as stream:
    stream.write(b'repository-owned scratch')
assert os.environ['KOINE_SDK_ROOT'] == 'selected-sdk'
assert os.environ['CMAKE_TOOLCHAIN_FILE'] == 'selected-toolchain'
"""], env={
            **{name: str(ROOT.parent / "must-not-be-used") for name in (
                "UV_CACHE_DIR", "PIP_CACHE_DIR", "XDG_CACHE_HOME",
                "UV_PYTHON_INSTALL_DIR", "TMPDIR", "TMP", "TEMP",
            )},
            "KOINE_SDK_ROOT": "selected-sdk",
            "CMAKE_TOOLCHAIN_FILE": "selected-toolchain",
        })

    def test_failed_child_is_an_error(self):
        with self.assertRaises(subprocess.CalledProcessError) as failure:
            run([sys.executable, "-B", "-c", "raise SystemExit(7)"])
        self.assertEqual(failure.exception.returncode, 7)


if __name__ == "__main__":
    unittest.main()
