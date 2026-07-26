#!/bin/sh
# Download the latest WFB-NG firmware from OpenIPC nightly builds.
# Overwrites any previously cached firmware with the newest version.

set -eu

FIRMWARE_URL="https://github.com/OpenIPC/builder/releases/download/nightly/ssc338q_fpv_runcam-wifilink-nor.tgz"
FIRMWARE_FILE="ssc338q_fpv_runcam-wifilink-nor.tgz"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CACHE_DIR="${SCRIPT_DIR}/firmware"
CACHED_TGZ="${CACHE_DIR}/${FIRMWARE_FILE}"

mkdir -p "${CACHE_DIR}"

if [ -f "${CACHED_TGZ}" ]; then
    echo "[gs] Existing cached firmware: $(ls -lh "${CACHED_TGZ}")"
fi

echo "[gs] Downloading latest WFB-NG firmware ..."

if command -v curl >/dev/null 2>&1; then
    curl -L --progress-bar -o "${CACHED_TGZ}" "${FIRMWARE_URL}" || \
        curl -L --progress-bar --insecure -o "${CACHED_TGZ}" "${FIRMWARE_URL}" && \
        echo "[gs] WARNING: Downloaded with SSL verification disabled. Verify firmware integrity."
elif command -v wget >/dev/null 2>&1; then
    wget -O "${CACHED_TGZ}" "${FIRMWARE_URL}" || \
        wget --no-check-certificate -O "${CACHED_TGZ}" "${FIRMWARE_URL}" && \
        echo "[gs] WARNING: Downloaded with SSL verification disabled. Verify firmware integrity."
else
    echo "[gs] ERROR: Neither curl nor wget is installed on the groundstation."
    exit 1
fi

echo "[gs] Done. Firmware saved to: ${CACHED_TGZ}"
echo "[gs] $(ls -lh "${CACHED_TGZ}")"
