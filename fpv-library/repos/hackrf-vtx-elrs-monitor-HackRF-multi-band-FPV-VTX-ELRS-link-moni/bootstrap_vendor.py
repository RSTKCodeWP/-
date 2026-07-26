#!/usr/bin/env python3
"""
bootstrap_vendor.py — fetch the HackRF host tools + runtime DLLs locally.

This pulls prebuilt Windows binaries from conda-forge (no system install, no
admin rights) and lays them out under ./vendor/bin so the hackrf_api library
can drive the device via the official command-line tools.

It is self-contained: re-running is idempotent and only re-downloads missing
packages. Requires the `zstandard` pip package (conda's .conda payloads are
zstd-compressed tarballs that the stock Windows `tar` cannot read).

Usage:
    python bootstrap_vendor.py            # download + extract everything
    python bootstrap_vendor.py --verify   # just check vendor/bin is complete
"""
from __future__ import annotations
import io
import json
import os
import shutil
import sys
import tarfile
import urllib.request
import zipfile

CONDA = "https://conda.anaconda.org/conda-forge/win-64"
API = "https://api.anaconda.org/package/conda-forge"

# conda-forge packages that, together, provide the HackRF host tools and every
# runtime DLL they import: hackrf-0.dll, fftw3f.dll, libusb-1.0.dll, plus the
# MSVC runtime (vcruntime140*.dll / msvcp140.dll) the tools are built against —
# this machine has UCRT but not the VC++ redistributable, so we vendor it too.
PACKAGES = ["hackrf", "libhackrf0", "libusb", "fftw", "vc14_runtime", "libwinpthread"]

# Files we actually need at runtime (everything else in the packages is headers,
# import libs and cmake config we can ignore).
WANTED_SUFFIXES = (".exe", ".dll")

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, "vendor")
DL = os.path.join(VENDOR, "_download")
BIN = os.path.join(VENDOR, "bin")

REQUIRED = [
    "hackrf_info.exe", "hackrf_sweep.exe", "hackrf_transfer.exe",
    "hackrf-0.dll", "fftw3f.dll", "libusb-1.0.dll",
    "vcruntime140.dll", "msvcp140.dll", "libwinpthread-1.dll",
]


def _latest_basename(pkg: str) -> str:
    data = json.load(urllib.request.urlopen(f"{API}/{pkg}", timeout=60))
    wins = [f for f in data["files"] if f["attrs"].get("subdir") == "win-64"]
    wins.sort(key=lambda f: f["attrs"].get("timestamp", 0), reverse=True)
    if not wins:
        raise RuntimeError(f"no win-64 build found for {pkg}")
    return wins[0]["basename"].split("/")[-1]


def _download(basename: str) -> str:
    os.makedirs(DL, exist_ok=True)
    dest = os.path.join(DL, basename)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    url = f"{CONDA}/{basename}"
    print(f"  downloading {basename} ...")
    urllib.request.urlretrieve(url, dest)
    return dest


def _extract_conda(path: str, out_dir: str) -> None:
    """A .conda file is a zip holding pkg-*.tar.zst (payload) + info-*.tar.zst."""
    import zstandard  # imported here so --verify works without the dep

    with zipfile.ZipFile(path) as z:
        pkg = next(n for n in z.namelist() if n.startswith("pkg-"))
        raw = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(z.read(pkg))).read()
    with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
        for m in tf.getmembers():
            if m.isfile() and m.name.endswith(WANTED_SUFFIXES):
                name = os.path.basename(m.name)
                with tf.extractfile(m) as src, open(os.path.join(out_dir, name), "wb") as dst:
                    shutil.copyfileobj(src, dst)
                print(f"    + {name}")


def verify() -> bool:
    missing = [f for f in REQUIRED if not os.path.exists(os.path.join(BIN, f))]
    if missing:
        print("MISSING:", ", ".join(missing))
        return False
    print(f"OK — vendor/bin complete: {', '.join(sorted(os.listdir(BIN)))}")
    return True


def main() -> int:
    if "--verify" in sys.argv:
        return 0 if verify() else 1

    os.makedirs(BIN, exist_ok=True)
    for pkg in PACKAGES:
        print(f"[{pkg}]")
        basename = _latest_basename(pkg)
        path = _download(basename)
        _extract_conda(path, BIN)

    print()
    return 0 if verify() else 1


if __name__ == "__main__":
    raise SystemExit(main())
