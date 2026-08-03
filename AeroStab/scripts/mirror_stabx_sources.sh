#!/usr/bin/env bash
# Mirror StabX sources into AeroStab/vendor/stabx/ (scripts, configs, UI HTML, docs).
# Does NOT copy encrypted ua-pilot.enc or full SD image — see MANIFEST.md.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/vendor/stabx"
IMG="${STABX_IMG:-$ROOT/image/extracted/ZERO-16G-2025-11-01-JR.img}"
ROOT_OFF=$((1056768 * 512))
MNT="${STABX_MNT:-/tmp/stabx-root-mirror}"

mkdir -p "$VENDOR"/{sd-image/{scripts,systemd,binaries-refs},drive-manifest,drive-docs,ardupilot-fw}

echo "=== StabX mirror → $VENDOR ==="

# --- Google Drive local cache (image/stabx-drive/) ---
if [[ -d "$ROOT/image/stabx-drive" ]]; then
  echo "Indexing image/stabx-drive ..."
  find "$ROOT/image/stabx-drive" -type f -printf '%P\t%s\n' | sort > "$VENDOR/drive-manifest/files.tsv"
  for pdf in "$ROOT/image/stabx-drive"/*.pdf "$ROOT/image/stabx-drive"/*ENG*.pdf; do
    [[ -f "$pdf" ]] || continue
    cp -f "$pdf" "$VENDOR/drive-docs/"
  done
fi

# --- SD image rootfs ---
if [[ ! -f "$IMG" ]]; then
  echo "WARN: no $IMG — skip SD extract (run: unrar x image/ZERO-16G-....rar image/extracted/)"
else
  sudo mkdir -p "$MNT"
  if ! mountpoint -q "$MNT"; then
    sudo mount -o loop,offset=$ROOT_OFF "$IMG" "$MNT"
    UMOUNT=1
  else
    UMOUNT=0
  fi

  STAB="$MNT/home/pilot/start"
  if [[ -d "$STAB" ]]; then
  cp -a "$STAB/data/scripts/"* "$VENDOR/sd-image/scripts/" 2>/dev/null || true
  cp -a "$STAB/data/tools/"* "$VENDOR/sd-image/scripts/" 2>/dev/null || true
  cp -a "$STAB/data/res/" "$VENDOR/sd-image/ui-res/"
  cp -f "$MNT/usr/bin/autorun.sh" "$MNT/usr/bin/firmware.sh" "$MNT/usr/bin/wifi.sh" \
        "$MNT/usr/bin/run_usb.sh" "$MNT/usr/bin/expand.sh" "$MNT/usr/bin/shred.sh" \
        "$STAB/update.sh" "$STAB/clean.sh" "$STAB/wipe.sh" \
        "$VENDOR/sd-image/scripts/" 2>/dev/null || true
  cp -a "$MNT/etc/systemd/system/"*.service "$VENDOR/sd-image/systemd/" 2>/dev/null || true
  for b in lserv creepy; do
    if [[ -f "$STAB/$b" ]]; then
      sha256sum "$STAB/$b" > "$VENDOR/sd-image/binaries-refs/${b}.sha256"
      file "$STAB/$b" > "$VENDOR/sd-image/binaries-refs/${b}.file.txt"
      strings "$STAB/$b" | head -500 > "$VENDOR/sd-image/binaries-refs/${b}.strings-head.txt"
    fi
  done
  find "$STAB/data/settings" -type f 2>/dev/null | head -50 | while read -r f; do
    rel="${f#$STAB/}"
    mkdir -p "$VENDOR/sd-image/$(dirname "$rel")"
    cp -f "$f" "$VENDOR/sd-image/$rel"
  done
  fi

  [[ "$UMOUNT" -eq 1 ]] && sudo umount "$MNT"
fi

# --- ArduPlane STABX FW already in deploy/stabx-reference ---
cp -f "$ROOT/deploy/stabx-reference/"* "$VENDOR/ardupilot-fw/" 2>/dev/null || true

# --- Generate manifest ---
python3 - <<'PY'
import hashlib, json, os
from pathlib import Path
root = Path(os.environ.get("VENDOR", "."))
entries = []
for p in sorted(root.rglob("*")):
    if not p.is_file() or p.name == "MANIFEST.json":
        continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    entries.append({"path": str(p.relative_to(root)), "bytes": p.stat().st_size, "sha256": h})
(root / "MANIFEST.json").write_text(json.dumps(entries, indent=2) + "\n")
print(f"Manifest: {len(entries)} files")
PY

echo "Done. See vendor/stabx/MANIFEST.md"
