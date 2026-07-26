#!/usr/bin/env bash
# Installs "HackRF Monitor.app" on the Desktop (macOS only): a double-clickable
# icon that (re)starts the multi-band monitor via monitor_launcher.sh and opens
# the dashboard. Safe to re-run; replaces any existing copy.
#
#   ./packaging/install_desktop_icon.sh
#
# Notes:
#  - Built as an AppleScript applet: plain shell-script .app bundles are
#    silently denied Documents access by macOS TCC; applets prompt properly.
#    First click asks to allow access to the project folder — click Allow once.
#  - Custom icon needs Pillow (pip install pillow); otherwise the app still
#    installs with the generic AppleScript icon.
set -euo pipefail

if [ "$(uname)" != "Darwin" ]; then
  echo "macOS only. On Windows, make a shortcut to start_monitor.ps1 instead." >&2
  exit 1
fi

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$HOME/Desktop/HackRF Monitor.app"

rm -rf "$APP"
osacompile -o "$APP" -e "try
	do shell script \"/bin/bash '$PROJ/monitor_launcher.sh'\"
on error errMsg
	display alert \"HackRF Monitor failed to start\" message errMsg
end try"

# Custom icon (optional): render with Pillow, compile with iconutil, and strip
# the default applet icon assets so ours wins.
if [ -x "$PROJ/.venv/bin/python" ]; then PY="$PROJ/.venv/bin/python"; else PY="$(command -v python3)"; fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
if "$PY" "$PROJ/packaging/make_icon.py" "$TMP" >/dev/null 2>&1; then
  iconutil -c icns "$TMP/AppIcon.iconset" -o "$APP/Contents/Resources/applet.icns"
  rm -f "$APP/Contents/Resources/Assets.car"
  /usr/libexec/PlistBuddy -c "Delete :CFBundleIconName" "$APP/Contents/Info.plist" 2>/dev/null || true
else
  echo "note: Pillow not available — installed with the generic icon (pip install pillow to fix)"
fi
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string com.hackrf-monitor.launcher" "$APP/Contents/Info.plist" 2>/dev/null || true

codesign --force -s - "$APP" 2>/dev/null
touch "$APP"
echo "Installed: $APP"
