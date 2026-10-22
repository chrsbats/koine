"""Unpack a released GCC 15 toolset and glibc 2.28 sysroot without installing RPMs.

Usage: uv run --with libarchive-c python native/tools/prepare_linux_sdk.py build/sdk-alma8-gcc15
"""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import urllib.parse
import urllib.request

PACKAGES = {
    "AppStream": [
        "gcc-toolset-15-gcc-15.2.1-7.1.el8_10.x86_64.rpm",
        "gcc-toolset-15-gcc-c++-15.2.1-7.1.el8_10.x86_64.rpm",
        "gcc-toolset-15-libstdc++-devel-15.2.1-7.1.el8_10.x86_64.rpm",
        "gcc-toolset-15-runtime-15.0-9.el8_10.x86_64.rpm",
        "gcc-toolset-15-binutils-2.44-3.el8_10.x86_64.rpm",
        "libmpc-1.1.0-9.1.el8.x86_64.rpm",
    ],
    "BaseOS": [
        "glibc-2.28-251.el8_10.48.x86_64.rpm",
        "glibc-devel-2.28-251.el8_10.48.x86_64.rpm",
        "glibc-headers-2.28-251.el8_10.48.x86_64.rpm",
        "kernel-headers-4.18.0-553.el8_10.x86_64.rpm",
        "libstdc++-8.5.0-29.el8_10.alma.1.x86_64.rpm",
        "libgcc-8.5.0-29.el8_10.alma.1.x86_64.rpm",
        "mpfr-3.1.6-1.el8.x86_64.rpm",
        "gmp-6.1.2-11.el8.x86_64.rpm",
        "jansson-2.14-1.el8.x86_64.rpm",
    ],
}
RUNTIME_PREFIXES = ("libmpc-", "mpfr-", "gmp-", "jansson-")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    options = parser.parse_args()
    import libarchive

    directory = options.directory.resolve()
    downloads = directory / "downloads"
    root = directory / "sysroot"
    runtime = directory / "compiler-runtime"
    downloads.mkdir(parents=True, exist_ok=True)
    root.mkdir(exist_ok=True)
    runtime.mkdir(exist_ok=True)

    def download(item):
        repo, name = item
        path = downloads / name
        url = f"https://repo.almalinux.org/almalinux/8/{repo}/x86_64/os/Packages/{urllib.parse.quote(name)}"
        if not path.exists():
            with urllib.request.urlopen(url, timeout=120) as response, path.open("wb") as output:
                shutil.copyfileobj(response, output)
        return path

    with ThreadPoolExecutor(max_workers=4) as workers:
        archives = list(workers.map(download, ((repo, name) for repo, names in PACKAGES.items() for name in names)))
    for archive in archives:
        os.chdir(runtime if archive.name.startswith(RUNTIME_PREFIXES) else root)
        print(hashlib.sha256(archive.read_bytes()).hexdigest(), archive.name, flush=True)
        libarchive.extract_file(str(archive))
    for name in ("lib", "lib64"):
        path = root / name
        destination = root / "usr" / name
        destination.mkdir(exist_ok=True)
        if path.is_dir() and not path.is_symlink():
            for entry in path.iterdir():
                shutil.move(entry, destination / entry.name)
            path.rmdir()
        if not path.is_symlink():
            path.symlink_to("usr/" + name)
    print("Released GCC 15 / glibc 2.28 SDK extracted:", root)


if __name__ == "__main__":
    main()
