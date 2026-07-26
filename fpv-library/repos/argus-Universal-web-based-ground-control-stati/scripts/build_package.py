#!/usr/bin/env python3
"""
Build self-contained Windows package for Argus GCS v3.
Downloads Python 3.10 embeddable, bundles all dependencies offline,
produces a zip that runs on any Windows 10/11 x64 with zero install.

Usage:
    python3 build_package.py              # x64 (default)
    python3 build_package.py --arch arm64 # ARM64 Windows (requires Python 3.11+)
"""

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = SCRIPT_DIR / "release"

_VERSION = re.search(r"VERSION = '([^']+)'", (SCRIPT_DIR / "backend" / "config.py").read_text()).group(1)

PY_VER = "3.10.11"
PY_BASE_URL = "https://www.python.org/ftp/python/{ver}/python-{ver}-embed-{arch}.zip"

PIP_DEPS = [
    "fastapi",
    "uvicorn",
    "pyserial",
    "httpx",
    "websockets",
    "python-multipart",
]


def download(url, desc):
    print("  Downloading %s ..." % desc)
    req = urllib.request.Request(url, headers={"User-Agent": "argus-builder/1.0"})
    resp = urllib.request.urlopen(req, timeout=120)
    data = resp.read()
    print("    Done (%.1f KB)" % (len(data) / 1024))
    return data


def build(arch: str = "amd64"):
    pip_platform = f"win_{arch}"
    py_url = PY_BASE_URL.format(ver=PY_VER, arch=arch)

    print(f"=== Argus GCS v3 Package Builder (arch={arch}) ===\n")

    build_dir = SCRIPT_DIR / "_build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()

    # ── 1. Build frontend ──
    print("[1/5] Building frontend")
    subprocess.run(
        ["node", "node_modules/vite/bin/vite.js", "build"],
        cwd=str(SCRIPT_DIR),
        check=True,
        capture_output=True,
    )
    dist_src = SCRIPT_DIR / "dist"
    if not dist_src.exists():
        print("  ERROR: dist/ not found after build")
        sys.exit(1)
    shutil.copytree(dist_src, build_dir / "dist")
    print("  Frontend built")

    # ── 2. Download Python embeddable ──
    print("[2/5] Python embeddable")
    cache = SCRIPT_DIR / (f"python-{PY_VER}-embed-{arch}.zip")
    if cache.exists():
        print("  Using cached %s" % cache.name)
        py_data = cache.read_bytes()
    else:
        py_data = download(py_url, f"Python {PY_VER} ({arch})")
        cache.write_bytes(py_data)

    py_dir = build_dir / "python"
    py_dir.mkdir()
    with zipfile.ZipFile(io.BytesIO(py_data)) as zf:
        zf.extractall(py_dir)

    ver_short = PY_VER.rsplit(".", 1)[0].replace(".", "")
    pth = py_dir / ("python%s._pth" % ver_short)
    if pth.exists():
        pth.write_text("python%s.zip\n.\n..\\backend\n..\\.\nLib\\site-packages\nimport site\n" % ver_short)

    # ── 3. Download pip wheels ──
    print("[3/5] Downloading dependencies")
    wheels_dir = build_dir / "_wheels"
    wheels_dir.mkdir()
    site_pkg = py_dir / "Lib" / "site-packages"
    site_pkg.mkdir(parents=True, exist_ok=True)

    for dep in PIP_DEPS:
        print("  %s" % dep)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "--only-binary=:all:",
                f"--platform={pip_platform}",
                "--python-version=%s" % PY_VER.rsplit(".", 1)[0],
                "-d",
                str(wheels_dir),
                dep,
            ],
            check=True,
            capture_output=True,
        )

    for whl in wheels_dir.glob("*.whl"):
        with zipfile.ZipFile(whl) as zf:
            zf.extractall(site_pkg)
    shutil.rmtree(wheels_dir)

    # ── 4. Copy backend + protocol ──
    print("[4/5] Copying application files")
    be_dst = build_dir / "backend"
    # Copy the entire backend tree so subpackages (e.g. backend/commands/)
    # are included. The previous `glob('*.py')` only matched top-level .py
    # files, which meant the packaged zip was missing the commands package
    # and the backend crashed at import time inside the .bat launcher.
    shutil.copytree(SCRIPT_DIR / "backend", be_dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    # sim_pllink.py lives under scripts/, not at the repo root. Without the
    # correct path the sim launcher .bat tried to run a file that wasn't in
    # the zip.
    sim_src = SCRIPT_DIR / "scripts" / "sim_pllink.py"
    if sim_src.exists():
        shutil.copy2(sim_src, build_dir / "sim_pllink.py")

    # Create launcher bat
    (build_dir / "Argus地面站.bat").write_text(
        "@echo off\r\n"
        'cd /d "%~dp0"\r\n'
        "chcp 65001 >nul\r\n"
        "title Argus 地面站 v3.0\r\n"
        "echo ============================================\r\n"
        "echo   Argus 地面站 v3.0\r\n"
        "echo ============================================\r\n"
        "echo.\r\n"
        "echo 正在启动，浏览器将自动打开...\r\n"
        "echo 按 Ctrl+C 停止\r\n"
        "echo.\r\n"
        "python\\python.exe backend\\server.py --port 8100 --host 0.0.0.0\r\n"
        "if errorlevel 1 pause\r\n",
        encoding="utf-8",
    )

    # Sim launcher
    (build_dir / "启动仿真器.bat").write_text(
        "@echo off\r\n"
        'cd /d "%~dp0"\r\n'
        "chcp 65001 >nul\r\n"
        "echo 仿真器运行中 (端口 5770)\r\n"
        "echo 在地面站中连接: tcp:localhost:5770\r\n"
        "python\\python.exe sim_pllink.py 5770\r\n"
        "pause\r\n",
        encoding="utf-8",
    )

    # ── 5. Package ──
    print("[5/5] Creating zip")
    OUTPUT_DIR.mkdir(exist_ok=True)
    zip_name = OUTPUT_DIR / f"Argus_GCS_v{_VERSION}_{arch}.zip"
    if zip_name.exists():
        zip_name.unlink()

    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(build_dir):
            for f in files:
                filepath = Path(root) / f
                arcname = f"Argus_GCS_v{_VERSION}/" + str(filepath.relative_to(build_dir))
                zf.write(filepath, arcname)

    shutil.rmtree(build_dir)

    size_mb = zip_name.stat().st_size / 1024 / 1024
    print("\n=== Done! ===")
    print("Output: %s (%.1f MB)" % (zip_name, size_mb))
    print('Usage: Extract zip, double-click "Argus地面站.bat"')


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build Argus GCS Windows package")
    ap.add_argument(
        "--arch",
        choices=["amd64", "arm64"],
        default="amd64",
        help="Target architecture (default: amd64). arm64 Windows embeddable Python requires PY_VER >= 3.11.",
    )
    args = ap.parse_args()
    build(arch=args.arch)
