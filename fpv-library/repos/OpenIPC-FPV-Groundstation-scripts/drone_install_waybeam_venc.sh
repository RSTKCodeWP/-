#!/bin/sh
# Replace majestic with waybeam_venc on the drone.
# Run this from the groundstation or dev machine.

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "${SCRIPT_DIR}/helpers/drone_helpers.sh"

WAYBEAM_URL="https://github.com/snokvist/waybeam_venc/releases/download/latest/waybeam-star6e.tar.gz"
S99MOUNTSD_URL="https://raw.githubusercontent.com/snokvist/waybeam_venc/master/scripts/S99mountSD"
LIBS_BASE_URL="https://github.com/snokvist/waybeam_venc/raw/master/libs/star6e"
STAR6E_LIBS="libcam_os_wrapper.so libcus3a.so libispalgo.so libmi_ai.so libmi_iqserver.so libmi_isp.so libmi_ive.so libmi_rgn.so libmi_sensor.so libmi_sys.so libmi_venc.so libmi_vif.so libmi_vpe.so"

for cmd in sshpass curl tar; do
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        echo "[gs] ERROR: '${cmd}' is not installed on the groundstation."
        exit 1
    fi
done

# --- Detect drone IP ---
detect_drone_ip
DRONE="${DRONE_USER}@${DRONE_IP}"

# --- Derive firmware type from drone IP ---
case "${DRONE_IP}" in
    10.5.0.10)     OUTGOING_SERVER="unix://rtp_local" ;;
    192.168.0.10)  OUTGOING_SERVER="udp://192.168.0.10:5600" ;;
    *)             OUTGOING_SERVER="unix://rtp_local" ;;
esac
echo "[gs] Firmware type: ${OUTGOING_SERVER}"

# --- Download and extract archives locally ---
TMPDIR_LOCAL=$(mktemp -d)
trap '_wfb_restore; rm -rf "${TMPDIR_LOCAL}"' EXIT

echo "[gs] Downloading waybeam-star6e.tar.gz ..."
curl -fsSL -o "${TMPDIR_LOCAL}/waybeam-star6e.tar.gz" "${WAYBEAM_URL}"

echo "[gs] Downloading S99mountSD ..."
curl -fsSL -o "${TMPDIR_LOCAL}/S99mountSD" "${S99MOUNTSD_URL}"

echo "[gs] Downloading SoC libs ..."
mkdir -p "${TMPDIR_LOCAL}/star6e-libs"
for lib in ${STAR6E_LIBS}; do
    curl -fsSL -o "${TMPDIR_LOCAL}/star6e-libs/${lib}" "${LIBS_BASE_URL}/${lib}"
done

echo "[gs] Extracting waybeam ..."
gunzip -c "${TMPDIR_LOCAL}/waybeam-star6e.tar.gz" | tar xf - -C "${TMPDIR_LOCAL}"

# Upload a file via SSH to a temp path and atomically replace destination.
# This avoids 'Text file busy' when destination binaries are currently in use.
upload_atomic() {
    # upload_atomic <local_file> <remote_path> [mode]
    local_file="$1"
    remote_path="$2"
    mode="${3:-}"
    remote_tmp="/tmp/.upload.$(basename "${remote_path}").$$"

    if [ -n "${mode}" ]; then
        dd if="${local_file}" bs=1M status=progress | \
            sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" \
                "cat > '${remote_tmp}' && chmod ${mode} '${remote_tmp}' && mv -f '${remote_tmp}' '${remote_path}'"
    else
        dd if="${local_file}" bs=1M status=progress | \
            sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" \
                "cat > '${remote_tmp}' && mv -f '${remote_tmp}' '${remote_path}'"
    fi
}

# --- Stop majestic/waybeam to free up link bandwidth before upload ---
echo "[gs] Stopping majestic, waybeam and msposd on drone ..."
sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" '
[ -x /etc/init.d/S95waybeam ] && /etc/init.d/S95waybeam stop >/dev/null 2>&1 || true
[ -x /etc/init.d/S95majestic ] && /etc/init.d/S95majestic stop >/dev/null 2>&1 || true
for _ in 1 2 3; do
    killall -q majestic 2>/dev/null || true
    killall -q waybeam 2>/dev/null || true
    killall -q msposd 2>/dev/null || true
    sleep 1
done
'

# --- Boost uplink MCS for faster upload ---
_wfb_boost

# --- Upload individual files to drone ---
echo "[gs] Uploading waybeam files ..."
upload_atomic "${TMPDIR_LOCAL}/waybeam-star6e/waybeam" "/usr/bin/waybeam" "755"
upload_atomic "${TMPDIR_LOCAL}/waybeam-star6e/json_cli" "/usr/bin/json_cli" "755"
upload_atomic "${TMPDIR_LOCAL}/waybeam-star6e/regscan" "/usr/bin/regscan" "755"
upload_atomic "${TMPDIR_LOCAL}/waybeam-star6e/S95waybeam" "/etc/init.d/S95waybeam" "755"
upload_atomic "${TMPDIR_LOCAL}/S99mountSD" "/etc/init.d/S99mountSD" "755"

echo "[gs] Uploading SoC libs to /usr/lib ..."
for lib in ${STAR6E_LIBS}; do
    upload_atomic "${TMPDIR_LOCAL}/star6e-libs/${lib}" "/usr/lib/${lib}"
done

echo "[gs] Uploading waybeam.json ..."
upload_atomic "${TMPDIR_LOCAL}/waybeam-star6e/waybeam.json" "/etc/waybeam.json"
echo "[gs] Configuring outgoing: enabled=true, server=${OUTGOING_SERVER} ..."
sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" \
    "json_cli -s .outgoing.enabled true -i /etc/waybeam.json && \
     json_cli -s .outgoing.server '\"${OUTGOING_SERVER}\"' -i /etc/waybeam.json"

# --- Restore uplink MCS ---
_wfb_restore

# --- Finalise permissions and remove majestic ---
echo "[gs] Finalising installation on drone ..."
sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" '
set -e
rm -f /usr/bin/majestic /etc/init.d/S95majestic
chmod +x /etc/init.d/S95waybeam
chmod +x /etc/init.d/S99mountSD
chmod +x /usr/bin/waybeam /usr/bin/json_cli /usr/bin/regscan
echo "[drone] Installation complete."
'

echo "[gs] Rebooting drone ..."
sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" "reboot" >/dev/null 2>&1 || true

echo "[gs] Done. Wait for the drone to finish rebooting before connecting again."
