#!/usr/bin/env bash
# Analyze StabX SD image (RAR or raw .img).
# Usage: bash scripts/analyze_stabx_image.sh /path/to/ZERO-16G-2025-11-01-JR.rar
set -euo pipefail

INPUT="${1:?Usage: $0 <file.rar|.img>}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
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

# ZERO-16G-2025-11-01-JR.img partition offsets (sector * 512)
BOOT_OFFSET=$((512 * 8192))       # p1 FAT32
ROOT_OFFSET=$((512 * 1056768))   # p2 ext4
DATA_OFFSET=$((512 * 15155200))   # p3 ext4

mount_part() {
  local offset="$1" mnt="$2"
  mkdir -p "$mnt"
  sudo mount -o loop,offset="$offset" "$IMG" "$mnt" 2>/dev/null
}

sudo losetup -D 2>/dev/null || true
ROOT=""
for offset in "$ROOT_OFFSET" $((512*8192)) $((512*122880)); do
  MNT="$WORKDIR/mnt-root"
  if mount_part "$offset" "$MNT"; then
    if [[ -f "$MNT/etc/os-release" ]]; then
      ROOT="$MNT"
      echo "Mounted root at offset $offset"
      break
    fi
    sudo umount "$MNT" 2>/dev/null || true
  fi
done

if [[ -z "${ROOT:-}" ]]; then
  echo "Could not mount root — listing partitions:"
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
  echo "## Crontab @reboot"
  cat "$ROOT/var/spool/cron/crontabs/root" 2>/dev/null || true
  echo "## Main binaries"
  ls -la "$ROOT/home/pilot/start/"{lserv,creepy,update.sh} 2>/dev/null || true
  file "$ROOT/home/pilot/start/"{lserv,creepy} 2>/dev/null || true
  echo "## Systemd (custom)"
  ls -la "$ROOT/etc/systemd/system/"*.service 2>/dev/null || true
  echo "## lserv HTTP paths (sample)"
  strings "$ROOT/home/pilot/start/lserv" 2>/dev/null | grep -E '^/[a-z]' | sort -u | head -40
  echo "## creepy UART"
  strings "$ROOT/home/pilot/start/creepy" 2>/dev/null | grep -iE 'ttyAMA|uart|getty' | head -10
  echo "## WiFi default"
  grep -h ssid\|psk "$ROOT/etc/NetworkManager/system-connections/uapilot.nmconnection" 2>/dev/null || true
} | tee "$REPORT"

# Boot config via strings (FAT mount often blocked in containers)
echo "## Boot config.txt (from image strings)" >> "$REPORT"
python3 - "$IMG" <<'PY' >> "$REPORT" 2>/dev/null || true
import sys
img = open(sys.argv[1], 'rb')
img.seek(8192 * 512)
boot = img.read(100 * 1024 * 1024)
idx = boot.find(b'# For more options')
if idx >= 0:
    print(boot[idx:idx+1200].decode('latin-1', errors='replace').split('\x00')[0])
PY

# Data partition
DATA_MNT="$WORKDIR/mnt-data"
if mount_part "$DATA_OFFSET" "$DATA_MNT"; then
  echo "## /data partition" >> "$REPORT"
  ls -la "$DATA_MNT" >> "$REPORT" 2>/dev/null || true
  sudo umount "$DATA_MNT" 2>/dev/null || true
fi

sudo umount "$ROOT" 2>/dev/null || true
sudo losetup -D 2>/dev/null || true

echo ""
echo "Report: $REPORT"
echo "Full write-up: $ROOT_DIR/docs/STABX_IMAGE_ANALYSIS.md"
