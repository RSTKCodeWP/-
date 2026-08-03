#!/usr/bin/env bash
# Analyze StabX SD image (RAR or raw .img) — run after download.
# Usage: bash scripts/analyze_stabx_image.sh /path/to/ZERO-16G-2025-11-01-JR.rar
set -euo pipefail

INPUT="${1:?Usage: $0 <file.rar|.img>}"
WORKDIR="${STABX_WORKDIR:-/tmp/stabx-analysis}"
mkdir -p "$WORKDIR"

echo "=== StabX image analyzer ==="
echo "Input: $INPUT"
echo "Workdir: $WORKDIR"

extract_image() {
  local f="$1"
  case "$f" in
    *.rar)
      command -v unrar-free >/dev/null || command -v unrar >/dev/null || { echo "Install unrar"; exit 1; }
      (unrar-free x -o+ "$f" "$WORKDIR/" 2>/dev/null || unrar x -o+ "$f" "$WORKDIR/")
      find "$WORKDIR" -name '*.img' -o -name '*.IMG' | head -1
      ;;
    *.img|*.IMG) echo "$f" ;;
    *) echo "Unknown format: $f"; exit 1 ;;
  esac
}

IMG="$(extract_image "$INPUT")"
[[ -n "$IMG" && -f "$IMG" ]] || { echo "No .img found after extract"; find "$WORKDIR" -type f | head -20; exit 1; }
echo "Image: $IMG ($(du -h "$IMG" | cut -f1))"

# Partition offset (Bookworm: boot ~256MB, root often at 512*122880)
for offset in $((512*8192)) $((512*122880)) $((512*526336)); do
  mkdir -p "$WORKDIR/mnt-$offset"
  if sudo mount -o loop,offset=$offset "$IMG" "$WORKDIR/mnt-$offset" 2>/dev/null; then
    echo "Mounted at offset $offset"
    ROOT="$WORKDIR/mnt-$offset"
    break
  fi
done

if [[ -z "${ROOT:-}" ]]; then
  echo "Could not mount — listing partitions:"
  fdisk -l "$IMG" 2>/dev/null || parted -s "$IMG" print
  exit 1
fi

REPORT="$WORKDIR/report.txt"
{
  echo "# StabX image analysis $(date -Iseconds)"
  echo "## OS"
  cat "$ROOT/etc/os-release" 2>/dev/null || true
  echo "## Hostname"
  cat "$ROOT/etc/hostname" 2>/dev/null || true
  echo "## Systemd services (stab/pilot/zero)"
  find "$ROOT/etc/systemd/system" "$ROOT/lib/systemd/system" -name '*.service' 2>/dev/null \
    | xargs -r grep -liE 'stab|pilot|zero|drone|vision' || true
  echo "## Binaries"
  find "$ROOT" -maxdepth 5 \( -iname '*stab*' -o -iname '*pilot*' -o -iname '*vision*' \) -type f 2>/dev/null | head -50
  echo "## Python packages"
  find "$ROOT" -path '*/site-packages/*' -maxdepth 6 2>/dev/null | head -30
  echo "## Config snippets"
  find "$ROOT/etc" "$ROOT/opt" "$ROOT/home" -name '*.yaml' -o -name '*.json' -o -name 'config*' 2>/dev/null | head -40
  echo "## Listening ports (if ss available in chroot)"
  echo "5050 8080 expected"
  echo "## Strings from main binary"
  MAIN=$(find "$ROOT/opt" "$ROOT/usr/local" "$ROOT/home" -type f -executable 2>/dev/null | head -5)
  for b in $MAIN; do
    echo "--- $b ---"
    strings "$b" 2>/dev/null | grep -iE 'mavlink|vision|stab|optical|5050|8080|pizero' | head -20
  done
} | tee "$REPORT"

# Boot partition
BOOT_OFFSET=$((512*2048))
mkdir -p "$WORKDIR/mnt-boot"
if sudo mount -o loop,offset=$BOOT_OFFSET "$IMG" "$WORKDIR/mnt-boot" 2>/dev/null; then
  echo "## Boot config.txt" >> "$REPORT"
  cat "$WORKDIR/mnt-boot/config.txt" 2>/dev/null >> "$REPORT" || \
    cat "$WORKDIR/mnt-boot/firmware/config.txt" 2>/dev/null >> "$REPORT"
  sudo umount "$WORKDIR/mnt-boot"
fi

sudo umount "$ROOT" 2>/dev/null || true
echo ""
echo "Report: $REPORT"
