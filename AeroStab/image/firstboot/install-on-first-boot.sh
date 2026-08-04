#!/usr/bin/env bash
# AeroStab first-boot installer — run once on fresh Pi OS after SD flash.
set -euo pipefail

MARKER="/var/lib/aerostab/firstboot.done"
LOG="/var/log/aerostab/firstboot.log"
INSTALL_DIR="/opt/aerostab"

mkdir -p "$(dirname "$LOG")" /var/lib/aerostab
exec > >(tee -a "$LOG") 2>&1

echo "=== AeroStab first-boot $(date -Iseconds) ==="

if [[ -f "$MARKER" ]]; then
  echo "Already installed, skipping."
  exit 0
fi

# Locate bundle (boot partition paths differ Bookworm vs legacy)
BUNDLE=""
for candidate in \
  /boot/firmware/aerostab \
  /boot/aerostab \
  /mnt/bootfs/aerostab; do
  if [[ -d "$candidate/project" ]]; then
    BUNDLE="$candidate"
    break
  fi
done

if [[ -z "$BUNDLE" ]]; then
  echo "ERROR: aerostab bundle not found on boot partition."
  echo "Copy dist/aerostab-sd-bundle.tar.gz to boot and extract."
  exit 1
fi

echo "Bundle: $BUNDLE"

# Enable unattended first-boot service (for next boots / cloud-init path)
if [[ -f "$BUNDLE/aerostab-firstboot.service" ]]; then
  cp "$BUNDLE/aerostab-firstboot.service" /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable aerostab-firstboot.service 2>/dev/null || true
fi

# Run production installer from bundled project
PROJECT="$BUNDLE/project"
if [[ ! -f "$PROJECT/deploy/install_pi.sh" ]]; then
  echo "ERROR: $PROJECT/deploy/install_pi.sh missing"
  exit 1
fi

rsync -a --exclude '.venv' "$PROJECT/" "$INSTALL_DIR/"
bash "$INSTALL_DIR/deploy/install_pi.sh"

touch "$MARKER"
echo "=== First-boot complete. Reboot recommended. ==="
systemctl reboot 2>/dev/null || true
