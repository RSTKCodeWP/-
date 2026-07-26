#!/usr/bin/env bash
#
# install.sh — install the ardufleetcheck skill bundle into Claude Code.
#
# What it does:
#   1. Copies every skill in ./skills/ into ~/.claude/skills/
#   2. Copies ./data/ (clone_scripts + OSD layout files) to a data dir
#      (default: ~/Documents/ttfleet — override with TTFLEET_ROOT)
#   3. Prints the one line you need to add to your shell profile.
#
# Re-running is safe; it overwrites the installed copies.
#
# Usage:
#   ./install.sh                       # data dir -> ~/Documents/ttfleet
#   TTFLEET_ROOT=~/drones ./install.sh # data dir -> ~/drones
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DST="$HOME/.claude/skills"
DATA_DST="${TTFLEET_ROOT:-$HOME/Documents/ttfleet}"

echo "==> ardufleetcheck installer"
echo "    source package : $HERE"
echo "    skills    -> $SKILLS_DST"
echo "    data      -> $DATA_DST"
echo

# --- 1. skills -------------------------------------------------------------
mkdir -p "$SKILLS_DST"
for d in "$HERE"/skills/*/; do
    name="$(basename "$d")"
    rm -rf "${SKILLS_DST:?}/$name"
    cp -R "$d" "$SKILLS_DST/$name"
    echo "    [skill] $name"
done

# --- 2. data ---------------------------------------------------------------
mkdir -p "$DATA_DST"
# cp -R of the contents (not the dir) so files land directly under DATA_DST,
# matching the paths the skills expect ($TTFLEET_ROOT/clone_scripts, etc.)
cp -R "$HERE"/data/. "$DATA_DST"/
chmod +x "$DATA_DST"/clone_scripts/*.py 2>/dev/null || true
echo "    [data]  clone_scripts/, OSD layout files, firmware/ -> $DATA_DST"

# --- 3. dependency check ---------------------------------------------------
echo
PYBIN="${TTFLEET_PYTHON:-/usr/bin/python3}"
echo "==> Checking Python deps with $PYBIN"
missing=""
for mod in pymavlink serial; do
    if "$PYBIN" -c "import $mod" 2>/dev/null; then
        echo "    [ok]   $mod"
    else
        echo "    [MISS] $mod"
        missing="$missing $mod"
    fi
done
if [ -n "$missing" ]; then
    # map module name -> pip package name
    pkgs="$(echo "$missing" | sed 's/serial/pyserial/')"
    echo
    echo "    Install missing deps with:"
    echo "        $PYBIN -m pip install$pkgs"
fi

# --- 4. final instructions -------------------------------------------------
echo
echo "==> Done. One more step:"
if [ "$DATA_DST" != "$HOME/Documents/ttfleet" ]; then
    echo "    You installed data outside the default location, so export TTFLEET_ROOT"
    echo "    in your shell profile (~/.zshrc):"
    echo
    echo "        export TTFLEET_ROOT=\"$DATA_DST\""
    echo
    echo "    (Restart your terminal or 'source ~/.zshrc' after adding it.)"
else
    echo "    Data is in the default location; no TTFLEET_ROOT export needed."
fi
echo
echo "    Drop your firmware .apj files into:  $DATA_DST/firmware/"
echo "    then point the picker at them with:  export TTFLEET_FIRMWARE_DIR=\"$DATA_DST/firmware\""
echo
echo "    In Claude Code, run:  /ardufleetcheck"
