#!/bin/sh
# Trigger OpenIPC firstboot on the drone, showing live output.

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "${SCRIPT_DIR}/helpers/drone_helpers.sh"

if ! command -v sshpass >/dev/null 2>&1; then
    echo "ERROR: sshpass not installed on groundstation"
    exit 1
fi

echo "[gs] Detecting drone IP address ..."

detect_drone_ip
DRONE="${DRONE_USER}@${DRONE_IP}"

echo "[gs] Connecting to drone at ${DRONE_IP} ..."

echo "[gs] Starting firstboot; live output follows:"
sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" 'firstboot' || {
    rc=$?
    echo "[gs] SSH session ended with exit code ${rc}."
    echo "[gs] If reboot happened mid-session, this is expected."
    exit 0
}

echo "[gs] firstboot finished."
