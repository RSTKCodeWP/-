#!/bin/sh
# Replace the Runcam bootloader with the OpenIPC u-boot for ssc338q NOR flash.
# Downloads the binary from the OpenIPC firmware releases and flashes it.

set -eu

UBOOT_URL="https://github.com/OpenIPC/firmware/releases/download/latest/u-boot-ssc338q-nor.bin"
UBOOT_FILE="u-boot-ssc338q-nor.bin"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "${SCRIPT_DIR}/helpers/drone_helpers.sh"
DOWNLOAD_DIR="${SCRIPT_DIR}/firmware"
LOCAL_BIN="${DOWNLOAD_DIR}/${UBOOT_FILE}"

# --------------------------------------------------------------------------
# Dependency checks
# --------------------------------------------------------------------------
for cmd in curl sshpass scp ssh; do
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        echo "[gs] ERROR: '${cmd}' is not installed on the groundstation."
        exit 1
    fi
done

# --------------------------------------------------------------------------
# Internet connectivity check
# --------------------------------------------------------------------------
echo "[gs] Checking internet connectivity ..."
if ! curl -fsS --max-time 10 -o /dev/null "https://github.com"; then
    echo "[gs] ERROR: No internet connection. Cannot download the bootloader."
    exit 1
fi
echo "[gs] Internet connection OK."

# --------------------------------------------------------------------------
# Download bootloader
# --------------------------------------------------------------------------
mkdir -p "${DOWNLOAD_DIR}"
echo "[gs] Downloading OpenIPC bootloader ..."
echo "[gs]   ${UBOOT_URL}"
curl -L --max-time 120 --progress-bar -o "${LOCAL_BIN}" "${UBOOT_URL}"
echo "[gs] Download complete: $(ls -lh "${LOCAL_BIN}")"

# --------------------------------------------------------------------------
# Drone IP detection
# --------------------------------------------------------------------------
detect_drone_ip
DRONE="${DRONE_USER}@${DRONE_IP}"

# --------------------------------------------------------------------------
# Upload bootloader to drone /tmp
# --------------------------------------------------------------------------
echo "[gs] Uploading bootloader to drone /tmp ..."
sshpass -p "${DRONE_PASS}" scp ${SCP_OPTS} "${LOCAL_BIN}" "${DRONE}:/tmp/"
echo "[gs] Upload complete."

# --------------------------------------------------------------------------
# Flash bootloader on drone
# --------------------------------------------------------------------------
echo "[gs] !!! WARNING: Flashing the bootloader. Do NOT power off the drone !!!"
echo ""

echo "[gs] Step 1/2: Flashing u-boot to /dev/mtd0 ..."
sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" \
    "flashcp -v /tmp/${UBOOT_FILE} /dev/mtd0"

echo "[gs] Step 2/2: Erasing /dev/mtd1 ..."
sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" \
    "flash_eraseall /dev/mtd1"

echo ""
echo "[gs] Bootloader replacement complete."
echo "[gs] Reboot the drone to boot with the new OpenIPC u-boot."
