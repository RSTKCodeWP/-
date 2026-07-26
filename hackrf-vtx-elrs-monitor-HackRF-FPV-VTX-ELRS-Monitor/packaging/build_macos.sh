#!/usr/bin/env bash
# Build a standalone, self-contained macOS executable of the HackRF monitor.
#
# Bundles hackrf_info/hackrf_sweep/hackrf_transfer AND their full native-library
# closure (libhackrf, libusb, fftw, libomp, …), rewriting every dependency to
# @loader_path so the result needs NOTHING installed (no Homebrew) on the target.
#
#   bash packaging/build_macos.sh        ->  dist/hackrf-monitor-macos
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
command -v brew >/dev/null 2>&1 && eval "$(brew shellenv)"

HACKRF_PREFIX="$(brew --prefix hackrf)"
STAGE="$HERE/packaging/hackrf_tools_macos"
TOOLS=(hackrf_info hackrf_sweep hackrf_transfer)

echo "==> Staging SDK tools from $HACKRF_PREFIX"
rm -rf "$STAGE"; mkdir -p "$STAGE"
for t in "${TOOLS[@]}"; do cp "$HACKRF_PREFIX/bin/$t" "$STAGE/"; chmod u+w "$STAGE/$t"; done

# Recursively copy every non-system dylib dependency, flattened by leaf name.
gather() {
  local f="$1"
  while read -r dep; do
    case "$dep" in /usr/lib/*|/System/*|"") continue;; esac
    local leaf="${dep##*/}" src="$dep"
    if [[ "$dep" == @* ]]; then
      local searchdirs=()
      for d in /opt/homebrew/Cellar /opt/homebrew/opt /usr/local/Cellar /usr/local/opt; do
        [ -d "$d" ] && searchdirs+=("$d")
      done
      src="$( { find "${searchdirs[@]}" -name "$leaf" 2>/dev/null || true; } | head -1)"
    fi
    [ -f "$src" ] || continue
    if [ ! -f "$STAGE/$leaf" ]; then
      cp "$src" "$STAGE/$leaf"; chmod u+w "$STAGE/$leaf"
      gather "$STAGE/$leaf"
    fi
  done < <(otool -L "$f" | tail -n +2 | awk '{print $1}')
}
echo "==> Gathering dylib closure"
for t in "${TOOLS[@]}"; do gather "$STAGE/$t"; done

echo "==> Rewriting load paths to @loader_path + ad-hoc signing"
for f in "$STAGE"/*; do
  [ -f "$f" ] || continue
  base="$(basename "$f")"
  case "$base" in *.dylib) install_name_tool -id "@loader_path/$base" "$f" 2>/dev/null || true;; esac
  while read -r dep; do
    case "$dep" in /usr/lib/*|/System/*|"") continue;; esac
    leaf="${dep##*/}"
    [ -f "$STAGE/$leaf" ] && install_name_tool -change "$dep" "@loader_path/$leaf" "$f" 2>/dev/null || true
  done < <(otool -L "$f" | tail -n +2 | awk '{print $1}')
  codesign -f -s - "$f" 2>/dev/null || true
done

echo "==> Verifying nothing still references Homebrew"
if otool -L "$STAGE"/hackrf_sweep | tail -n +2 | grep -qE '/opt/homebrew|/usr/local/Cellar'; then
  echo "WARNING: hackrf_sweep still references a Homebrew path:"; otool -L "$STAGE"/hackrf_sweep
fi

echo "==> Running PyInstaller"
PY="${PYTHON:-$HERE/.venv/bin/python}"
"$PY" -m pip install -q --upgrade pyinstaller
"$PY" -m PyInstaller --noconfirm --onefile --name hackrf-monitor-macos \
  --add-data "$STAGE:hackrf_tools" \
  --exclude-module matplotlib --exclude-module tkinter --exclude-module PyQt5 \
  --exclude-module PySide6 --exclude-module IPython \
  monitor_app.py

echo ""
echo "==> Built: $HERE/dist/hackrf-monitor-macos"
ls -lh "$HERE/dist/hackrf-monitor-macos"
