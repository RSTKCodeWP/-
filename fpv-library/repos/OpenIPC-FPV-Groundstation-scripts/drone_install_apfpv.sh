#!/bin/sh
# Flash APFPV firmware onto the drone from the local cache.
# Run firmware_download_apfpv.sh first to download the latest firmware.

set -eu

FIRMWARE_FILE="ssc338q_apfpv_greg-generic-bu-eu-nor.tgz"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "${SCRIPT_DIR}/helpers/drone_helpers.sh"
CACHE_DIR="${SCRIPT_DIR}/firmware"
CACHED_TGZ="${CACHE_DIR}/${FIRMWARE_FILE}"
EXTRACT_DIR="${CACHE_DIR}/extracted"

# --------------------------------------------------------------------------
# Dependency checks
# --------------------------------------------------------------------------
for cmd in sshpass tar; do
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        echo "[gs] ERROR: '${cmd}' is not installed on the groundstation."
        exit 1
    fi
done

# --------------------------------------------------------------------------
# Check cached firmware exists
# --------------------------------------------------------------------------
if [ ! -f "${CACHED_TGZ}" ]; then
    echo "[gs] ERROR: No cached firmware found at:"
    echo "[gs]   ${CACHED_TGZ}"
    echo "[gs] Run firmware_download_apfpv.sh first."
    exit 1
fi

echo "[gs] Using cached firmware:"
echo "[gs]   $(ls -lh "${CACHED_TGZ}")"

# --------------------------------------------------------------------------
# Extract firmware
# --------------------------------------------------------------------------
echo "[gs] Extracting firmware ..."
rm -rf "${EXTRACT_DIR}"
mkdir -p "${EXTRACT_DIR}"
gunzip -c "${CACHED_TGZ}" | tar xf - -C "${EXTRACT_DIR}"

ROOTFS="$(find "${EXTRACT_DIR}" -name "rootfs.squashfs.ssc338q" | head -n 1)"
KERNEL="$(find "${EXTRACT_DIR}" -name "uImage.ssc338q"          | head -n 1)"

if [ -z "${ROOTFS}" ] || [ -z "${KERNEL}" ]; then
    echo "[gs] ERROR: Expected firmware files not found in the archive."
    echo "[gs]   rootfs.squashfs.ssc338q: ${ROOTFS:-NOT FOUND}"
    echo "[gs]   uImage.ssc338q:          ${KERNEL:-NOT FOUND}"
    exit 1
fi

echo "[gs] Found: ${ROOTFS}"
echo "[gs] Found: ${KERNEL}"

# --------------------------------------------------------------------------
# Drone IP detection
# --------------------------------------------------------------------------
detect_drone_ip
DRONE="${DRONE_USER}@${DRONE_IP}"

# --------------------------------------------------------------------------
# Stop majestic to free up link bandwidth before upload
# --------------------------------------------------------------------------
echo "[gs] Stopping majestic on drone to free up link bandwidth ..."
sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" 'killall -q majestic 2>/dev/null || true; killall -q waybeam 2>/dev/null || true'
echo "[gs] majestic or waybeam stopped."

# --------------------------------------------------------------------------
# Boost uplink MCS for faster upload
# --------------------------------------------------------------------------
trap '_wfb_restore' EXIT
_wfb_boost

# --------------------------------------------------------------------------
# Upload firmware files to drone /tmp
# --------------------------------------------------------------------------
echo "[gs] Uploading rootfs ($(du -h "${ROOTFS}" | cut -f1)) ..."
dd if="${ROOTFS}" bs=1M status=progress | sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" 'cat > /tmp/rootfs.squashfs.ssc338q'

echo "[gs] Uploading kernel ($(du -h "${KERNEL}" | cut -f1)) ..."
dd if="${KERNEL}" bs=1M status=progress | sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" 'cat > /tmp/uImage.ssc338q'

echo "[gs] Upload complete."

# --------------------------------------------------------------------------
# Restore uplink MCS
# --------------------------------------------------------------------------
_wfb_restore

# --------------------------------------------------------------------------
# Run sysupgrade on drone
# --------------------------------------------------------------------------
echo "[gs] Starting sysupgrade on drone. The drone will reboot when done."
echo "[gs] Do NOT power off the drone during the upgrade!"
echo ""

sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" \
    'sysupgrade -z -n --kernel=/tmp/uImage.ssc338q --rootfs=/tmp/rootfs.squashfs.ssc338q' || {
    rc=$?
    echo "[gs] SSH session ended with exit code ${rc}."
    echo "[gs] If the drone rebooted mid-session this is expected."
}

echo "[gs] Done. Wait for the drone to finish rebooting before connecting again."
