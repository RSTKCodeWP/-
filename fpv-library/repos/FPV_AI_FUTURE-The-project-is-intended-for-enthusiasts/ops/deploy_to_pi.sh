#!/usr/bin/env bash
# Deploy the 03-fpv project to the Raspberry Pi 5 (runs ON THE MAC).
#
#   ops/deploy_to_pi.sh [user@host] [remote_dir]
#
# Defaults: admin@admin.local:~/03-fpv . Needs key auth to the Pi first:
#   ssh-copy-id admin@admin.local        # one-time, enter the Pi password once
#
# Ships the CODE the flight loop needs (fpv/, seeker_core/, contracts/, firmware/, docs/, ops/) and skips
# what the Pi does not: the git history, python caches, thermal datasets, demo videos, and the 3D-print STLs.
set -euo pipefail

DEST="${1:-admin@admin.local}"
REMOTE_DIR="${2:-~/03-fpv}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

echo ">> deploying $HERE  ->  $DEST:$REMOTE_DIR"

# macOS ships openrsync / old rsync (no --info); -v --stats is portable to both it and the Pi's rsync 3.x.
rsync -az --delete -v --stats \
  --exclude '.git/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache/' \
  --exclude 'y16_dataset/' \
  --exclude 'demo/' \
  --exclude '*.mp4' \
  --exclude '*.npz' \
  --exclude 'hardware/**/*.STL' \
  --exclude '*.stl' \
  "$HERE/" "$DEST:$REMOTE_DIR/"

echo ">> done. Next on the Pi:"
echo "   ssh $DEST"
echo "   cd 03-fpv && ops/pi_setup.sh          # install deps"
echo "   PYTHONPATH=.:fpv python3 -m pytest fpv/ -q -m 'not slow'   # verify on the Pi"
