#!/bin/bash
# Build Argus GCS desktop application.
#
# Prerequisites:
#   - Node.js, npm (frontend build)
#   - Rust toolchain + cargo (Tauri build)
#   - Python 3 + PyInstaller (backend sidecar)
#
# On Windows, run this from Git Bash or WSL.
set -e
cd "$(dirname "$0")/.."

# Detect host target triple for sidecar naming
TARGET_TRIPLE=$(rustc -vV 2>/dev/null | grep '^host:' | cut -d' ' -f2)
if [ -z "$TARGET_TRIPLE" ]; then
    echo "ERROR: Rust toolchain not found. Install from https://rustup.rs/"
    exit 1
fi
echo "Target: $TARGET_TRIPLE"

# Verify TARGET_TRIPLE matches the externalBin name declared in tauri.conf.json.
# tauri.conf.json must contain an entry like "binaries/python-backend" under
# bundle.externalBin; Tauri appends "-<triple>" automatically. If they diverge,
# Tauri silently skips embedding the sidecar and the desktop app crashes on launch.
TAURI_CONF="src-tauri/tauri.conf.json"
if command -v python3 &>/dev/null && [ -f "$TAURI_CONF" ]; then
    EXPECTED_SIDECAR=$(python3 -c "
import json, pathlib, sys
conf = json.loads(pathlib.Path('$TAURI_CONF').read_text())
bins = conf.get('bundle', {}).get('externalBin', [])
if not bins:
    sys.exit(0)
print(pathlib.Path(bins[0]).name)
" 2>/dev/null)
    if [ -n "$EXPECTED_SIDECAR" ] && [ "$EXPECTED_SIDECAR" != "python-backend" ]; then
        echo "ERROR: tauri.conf.json externalBin basename is '${EXPECTED_SIDECAR}',"
        echo "       but this script builds 'python-backend-${TARGET_TRIPLE}'."
        echo "       Update tauri.conf.json or the --name argument below to match."
        exit 1
    fi
fi

# --- Step 1: Build Python backend into a single executable via PyInstaller ---
echo ""
echo "=== [1/3] Building Python backend sidecar ==="
mkdir -p src-tauri/binaries

# PyInstaller creates a single-file executable from backend_server.py.
# The --name must match the externalBin entry in tauri.conf.json (minus
# the target triple suffix that Tauri appends automatically).
python3 -m PyInstaller \
    --onefile \
    --name "python-backend-${TARGET_TRIPLE}" \
    --distpath src-tauri/binaries \
    --specpath build \
    --workpath build/pyinstaller \
    --clean \
    --noconfirm \
    --collect-submodules backend \
    --collect-submodules uvicorn \
    backend/server.py

echo "Sidecar built: src-tauri/binaries/python-backend-${TARGET_TRIPLE}"

# --- Step 2: Build frontend ---
echo ""
echo "=== [2/3] Building frontend ==="
node node_modules/vite/bin/vite.js build

# --- Step 3: Build Tauri desktop app ---
echo ""
echo "=== [3/3] Building Tauri desktop app ==="
cd src-tauri
cargo build --release

echo ""
echo "=== Build complete ==="
echo "Executable: src-tauri/target/release/pllink-gcs (or .exe on Windows)"
echo ""
echo "To build MSI/NSIS installers, run:"
echo "  cargo tauri build"
