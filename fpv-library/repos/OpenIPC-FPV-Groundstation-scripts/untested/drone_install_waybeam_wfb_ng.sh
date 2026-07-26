#!/bin/sh
# Install waybeam_wfb_ng on both drone and groundstation.
#
# Phase order is intentional:
#   1) Upload and run a self-contained installer script on the drone.
#   2) Switch the groundstation to gs_supervisor after drone-side work is done.
#
# Required artifacts (local files or URLs via env vars):
#   - link_controller (armv7l vehicle binary)
#   - gs_supervisor (groundstation binary)
#
# Optional env vars:
#   WAYBEAM_LINK_CONTROLLER=/path/to/link_controller
#   WAYBEAM_GS_SUPERVISOR=/path/to/gs_supervisor
#   WAYBEAM_LINK_CONTROLLER_URL=https://...
#   WAYBEAM_GS_SUPERVISOR_URL=https://...

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "${SCRIPT_DIR}/helpers/drone_helpers.sh"

WAYBEAM_RAW_BASE="https://raw.githubusercontent.com/snokvist/waybeam_wfb_ng/main"
S99WFB_URL="${WAYBEAM_RAW_BASE}/vehicle/init/S99wfb"

LINK_CONTROLLER_LOCAL="${WAYBEAM_LINK_CONTROLLER:-}"
GS_SUPERVISOR_LOCAL="${WAYBEAM_GS_SUPERVISOR:-}"
LINK_CONTROLLER_URL="${WAYBEAM_LINK_CONTROLLER_URL:-}"
GS_SUPERVISOR_URL="${WAYBEAM_GS_SUPERVISOR_URL:-}"

for cmd in sshpass curl dd sed awk grep mktemp chmod; do
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        echo "[gs] ERROR: '${cmd}' is not installed on the groundstation."
        exit 1
    fi
done

TMPDIR_LOCAL=$(mktemp -d)
trap '_wfb_restore; rm -rf "${TMPDIR_LOCAL}"' EXIT

copy_or_download_artifact() {
    name="$1"
    local_path="$2"
    url="$3"
    dest="$4"

    if [ -n "${local_path}" ]; then
        if [ ! -f "${local_path}" ]; then
            echo "[gs] ERROR: ${name} not found at ${local_path}"
            exit 1
        fi
        cp "${local_path}" "${dest}"
        echo "[gs] Using local ${name}: ${local_path}"
        return 0
    fi

    if [ -n "${url}" ]; then
        echo "[gs] Downloading ${name} from ${url} ..."
        curl -fsSL -o "${dest}" "${url}"
        return 0
    fi

    echo "[gs] ERROR: No ${name} provided."
    echo "[gs] Set one of:"
    echo "[gs]   WAYBEAM_${name}=<local path>"
    echo "[gs]   WAYBEAM_${name}_URL=<download url>"
    exit 1
}

echo "[gs] Preparing installation assets ..."
copy_or_download_artifact "LINK_CONTROLLER" "${LINK_CONTROLLER_LOCAL}" "${LINK_CONTROLLER_URL}" "${TMPDIR_LOCAL}/link_controller"
copy_or_download_artifact "GS_SUPERVISOR" "${GS_SUPERVISOR_LOCAL}" "${GS_SUPERVISOR_URL}" "${TMPDIR_LOCAL}/gs_supervisor"

echo "[gs] Downloading upstream init/config templates ..."
curl -fsSL -o "${TMPDIR_LOCAL}/S99wfb" "${S99WFB_URL}"

chmod +x "${TMPDIR_LOCAL}/link_controller" "${TMPDIR_LOCAL}/gs_supervisor" "${TMPDIR_LOCAL}/S99wfb"

# --- Detect drone IP and create SSH target ---
detect_drone_ip
DRONE="${DRONE_USER}@${DRONE_IP}"

echo "[gs] Stopping camera daemons on drone before transfer ..."
sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" 'killall -q majestic 2>/dev/null || true; killall -q waybeam 2>/dev/null || true; killall -q msposd 2>/dev/null || true'

echo "[gs] Boosting uplink MCS/FEC for faster uploads ..."
_wfb_boost

echo "[gs] Uploading drone-side artifacts ..."
dd if="${TMPDIR_LOCAL}/link_controller" bs=1M status=progress | sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" 'cat > /tmp/link_controller.waybeam'
dd if="${TMPDIR_LOCAL}/S99wfb" bs=1M status=progress | sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" 'cat > /tmp/S99wfb.waybeam'

cat > "${TMPDIR_LOCAL}/install_waybeam_wfb_drone.sh" <<'EOF_DRONE'
#!/bin/sh
set -eu

log() { echo "[drone] $*"; }

for cmd in wfb_tx wfb_rx; do
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        log "ERROR: required command '${cmd}' is missing on drone"
        exit 1
    fi
done
if [ ! -f /etc/drone.key ]; then
    log "ERROR: missing /etc/drone.key on drone"
    exit 1
fi

log "Installing waybeam_wfb_ng vehicle components ..."
cp /tmp/link_controller.waybeam /usr/bin/link_controller
cp /tmp/S99wfb.waybeam /etc/init.d/S99wfb
chmod +x /usr/bin/link_controller /etc/init.d/S99wfb

# Stop legacy/previous processes before switching mode.
killall -q link_controller wfb_rx wfb_tx wifibroadcast 2>/dev/null || true
/etc/init.d/S98wifibroadcast stop >/dev/null 2>&1 || true
/etc/init.d/S99wfb stop >/dev/null 2>&1 || true

# Persist opt-in broadcaster mode for next boot.
if command -v fw_setenv >/dev/null 2>&1; then
    fw_setenv wfbmode 1 || true
fi

log "Starting /etc/init.d/S99wfb (link may switch immediately) ..."
/etc/init.d/S99wfb start >/tmp/waybeam_wfb_drone_start.log 2>&1 || true
log "Vehicle-side install finished."
EOF_DRONE

chmod +x "${TMPDIR_LOCAL}/install_waybeam_wfb_drone.sh"
dd if="${TMPDIR_LOCAL}/install_waybeam_wfb_drone.sh" bs=1M status=none | sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" 'cat > /tmp/install_waybeam_wfb_drone.sh && chmod +x /tmp/install_waybeam_wfb_drone.sh'

echo "[gs] Triggering autonomous drone-side installer ..."
sshpass -p "${DRONE_PASS}" ssh ${SSH_OPTS} "${DRONE}" \
    'nohup /tmp/install_waybeam_wfb_drone.sh >/tmp/waybeam_wfb_drone_install.log 2>&1 < /dev/null &' || true

echo "[gs] Drone-side installer launched. Restoring temporary upload MCS/FEC ..."
_wfb_restore

echo "[gs] Installing groundstation gs_supervisor ..."
for cmd in wfb_tx wfb_rx start-stop-daemon; do
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        echo "[gs] ERROR: required command '${cmd}' is missing on groundstation."
        exit 1
    fi
done
if [ ! -f /etc/drone.key ]; then
    echo "[gs] ERROR: missing /etc/drone.key on groundstation."
    exit 1
fi

mkdir -p /etc/waybeam
cp "${TMPDIR_LOCAL}/gs_supervisor" /usr/bin/gs_supervisor
chmod +x /usr/bin/gs_supervisor

# Generate a local GS config based on upstream example with safe defaults.
WFB_IFACE="wlan0"
if [ -r /etc/default/wifibroadcast ]; then
    # shellcheck disable=SC1091
    . /etc/default/wifibroadcast
    if [ "${WFB_NICS:-}" ]; then
        WFB_IFACE=$(echo "${WFB_NICS}" | awk '{print $1}')
    fi
fi

cat > /etc/waybeam/gs_supervisor.json <<EOF_GS
{
  "key_file": "/etc/drone.key",
  "http": { "bind": "0.0.0.0", "port": 9080 },
  "system": {
    "up": [],
    "down": []
  },
  "tunnels": [
    {
      "name": "video",
      "role": "rx",
      "interfaces": ["${WFB_IFACE}"],
      "link_id": 207,
      "radio_port": 0,
      "udp_out": "127.0.0.1:5600",
      "stats_out": "127.0.0.1:5801",
      "extra_args": ["-x", "-l", "100"],
      "autostart": true
    },
    {
      "name": "uplink",
      "role": "tx",
      "interfaces": ["${WFB_IFACE}"],
      "link_id": 208,
      "radio_port": 0,
      "udp_in_port": 5801,
      "control_port": 8000,
      "fec": { "k": 1, "n": 2 },
      "radio": { "bandwidth_mhz": 20, "mcs_index": 1, "stbc": 1, "ldpc": 1 },
      "extra_args": ["-Q", "-P", "1"],
      "autostart": true
    }
  ],
  "venc_cmd": {
    "enabled": true,
    "uplink_tunnel": "uplink",
    "rate_limit_ms": 50
  }
}
EOF_GS

cat > /etc/init.d/S99waybeam-wfb-ng <<'EOF_INIT'
#!/bin/sh

start() {
    echo "Starting gs_supervisor:"
    start-stop-daemon -S -b -q -m -p /var/run/gs_supervisor.pid --exec /usr/bin/gs_supervisor -- -c /etc/waybeam/gs_supervisor.json
    [ $? = 0 ] && echo "OK" || echo "FAIL"
}

stop() {
    echo "Stopping gs_supervisor:"
    start-stop-daemon -K -q -p /var/run/gs_supervisor.pid
    [ $? = 0 ] && echo "OK" || echo "FAIL"
}

restart() {
    stop
    start
}

case "$1" in
    start) start ;;
    stop) stop ;;
    restart|reload) restart ;;
    *) echo "Usage: $0 {start|stop|restart}"; exit 1 ;;
esac

exit 0
EOF_INIT

chmod +x /etc/init.d/S99waybeam-wfb-ng

echo "[gs] Disabling legacy GS wfb-ng services ..."
/etc/init.d/S98adaptive-link stop >/dev/null 2>&1 || true
/etc/init.d/S98wifibroadcast stop >/dev/null 2>&1 || true

if [ -w /etc/default/wifibroadcast ]; then
    sed -i 's/^WIFIBROADCAST_ENABLED=.*/WIFIBROADCAST_ENABLED=false/' /etc/default/wifibroadcast || true
fi
if [ -w /etc/default/adaptive-link ]; then
    sed -i 's/^ADAPTIVE_LINK_ENABLED=.*/ADAPTIVE_LINK_ENABLED=false/' /etc/default/adaptive-link || true
fi

echo "[gs] Starting gs_supervisor service ..."
/etc/init.d/S99waybeam-wfb-ng restart >/dev/null 2>&1 || {
    echo "[gs] ERROR: Failed to start gs_supervisor."
    echo "[gs] Inspect process/service state with: /etc/init.d/S99waybeam-wfb-ng restart"
    exit 1
}

echo "[gs] waybeam_wfb_ng install flow finished."
echo "[gs] Vehicle install log (if still reachable): /tmp/waybeam_wfb_drone_install.log"
echo "[gs] GS API should now be available at: http://<groundstation-ip>:9080"
