#!/bin/sh
# Common configuration and helper functions for drone scripts.
# Source this file: . "${SCRIPT_DIR}/helpers/drone_helpers.sh"

DRONE_USER="root"
DRONE_PASS="12345"
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o LogLevel=ERROR"
SCP_OPTS="-O -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o LogLevel=ERROR"

# detect_drone_ip: Probes known addresses and sets DRONE_IP to the first
# reachable one. Exits the calling script with an error if none respond.
detect_drone_ip() {
    echo "[gs] Detecting drone IP address ..."
    DRONE_IP=""
    for candidate in "10.5.0.10" "192.168.0.10"; do
        if ping -c 1 -W 2 "${candidate}" >/dev/null 2>&1; then
            DRONE_IP="${candidate}"
            echo "[gs] Drone found at ${candidate}"
            return 0
        else
            echo "[gs] No response from ${candidate}"
        fi
    done
    echo "[gs] ERROR: Drone not reachable on any known IP (10.5.0.10 / 192.168.0.10)."
    echo "[gs] Check that the drone is powered on and connected."
    exit 1
}

# --- wfb-ng MCS/FEC helpers ---
# Temporarily boost the uplink MCS and FEC on the GS for faster uploads, then restore.
WFB_RESTORE=""
WFB_RESTORE_FEC=""

_wfb_ensure_control_port() {
    # If no wfb_tx is running with a non-zero control port, patch the config and restart.
    local cfg="/etc/wifibroadcast.cfg"
    local control_port="9000"

    # Check if already active
    for pid in $(ps w | awk '/\/wfb_tx /{print $1}'); do
        port=$({ tr '\0' '\n' < /proc/"$pid"/cmdline | awk '/^-C$/{getline; print}'; } 2>/dev/null)
        [ -n "${port}" ] && [ "${port}" != "0" ] && return 0
    done

    echo "[gs] No wfb_tx control port active — patching ${cfg} and restarting wifibroadcast ..."

    if ! grep -q '^\[gs_tunnel\]' "${cfg}" 2>/dev/null; then
        echo "[gs] ERROR: [gs_tunnel] section not found in ${cfg}, cannot auto-configure."
        return 1
    fi

    # Add control_port after [gs_tunnel] if not already present
    if ! grep -q '^control_port' "${cfg}"; then
        sed -i 's/^\[gs_tunnel\]/[gs_tunnel]\ncontrol_port = '"${control_port}"'/' "${cfg}"
    else
        sed -i 's/^control_port\s*=.*/control_port = '"${control_port}"'/' "${cfg}"
    fi

    /etc/init.d/S98wifibroadcast restart >/dev/null 2>&1 || true

    # Wait for wfb_tx to re-spawn with the new port (up to 10s)
    local waited=0
    while [ "${waited}" -lt 10 ]; do
        sleep 1
        waited=$((waited + 1))
        for pid in $(ps w | awk '/\/wfb_tx /{print $1}'); do
            port=$({ tr '\0' '\n' < /proc/"$pid"/cmdline | awk '/^-C$/{getline; print}'; } 2>/dev/null)
            [ "${port}" = "${control_port}" ] && echo "[gs] wifibroadcast restarted with control_port ${control_port}" && return 0
        done
    done

    echo "[gs] Warning: wfb_tx did not come up with control port after restart"
    return 1
}

_wfb_boost() {
    if ! command -v wfb_tx_cmd >/dev/null 2>&1; then
        echo "[gs] wfb_tx_cmd not available, skipping MCS/FEC boost"
        return 0
    fi

    _wfb_ensure_control_port || true

    ports=""
    for pid in $(ps w | awk '/\/wfb_tx /{print $1}'); do
        port=$({ tr '\0' '\n' < /proc/"$pid"/cmdline | awk '/^-C$/{getline; print}'; } 2>/dev/null)
        [ -n "${port}" ] && [ "${port}" != "0" ] && ports="${ports}${ports:+ }${port}"
    done
    if [ -z "${ports}" ]; then
        echo "[gs] No wfb_tx processes with control port configured, skipping MCS/FEC boost"
        return 0
    fi
    for port in ${ports}; do
        old_mcs=$(wfb_tx_cmd "${port}" get_radio 2>/dev/null | grep '^mcs_index=' | cut -d= -f2)
        old_mcs="${old_mcs:-1}"
        old_fec_k=$(wfb_tx_cmd "${port}" get_fec 2>/dev/null | grep '^k=' | cut -d= -f2)
        old_fec_n=$(wfb_tx_cmd "${port}" get_fec 2>/dev/null | grep '^n=' | cut -d= -f2)
        old_fec_k="${old_fec_k:-1}"
        old_fec_n="${old_fec_n:-2}"
        echo "[gs] Boosting wfb_tx (port ${port}): MCS ${old_mcs} -> 3, FEC ${old_fec_k}/${old_fec_n} -> 2/3"
        wfb_tx_cmd "${port}" set_radio -M 3 2>/dev/null || echo "[gs] Warning: failed to set MCS on port ${port}"
        wfb_tx_cmd "${port}" set_fec -k 2 -n 3 2>/dev/null || echo "[gs] Warning: failed to set FEC on port ${port}"
        WFB_RESTORE="${WFB_RESTORE}${WFB_RESTORE:+ }${port}:${old_mcs}"
        WFB_RESTORE_FEC="${WFB_RESTORE_FEC}${WFB_RESTORE_FEC:+ }${port}:${old_fec_k}:${old_fec_n}"
    done
}

_wfb_restore() {
    if ! command -v wfb_tx_cmd >/dev/null 2>&1; then
        return 0
    fi
    for item in ${WFB_RESTORE}; do
        port=$(echo "${item}" | cut -d: -f1)
        old_mcs=$(echo "${item}" | cut -d: -f2)
        echo "[gs] Restoring wfb_tx (port ${port}): MCS -> ${old_mcs}"
        wfb_tx_cmd "${port}" set_radio -M "${old_mcs}" 2>/dev/null || true
    done
    for item in ${WFB_RESTORE_FEC}; do
        port=$(echo "${item}" | cut -d: -f1)
        old_k=$(echo "${item}" | cut -d: -f2)
        old_n=$(echo "${item}" | cut -d: -f3)
        echo "[gs] Restoring wfb_tx (port ${port}): FEC -> ${old_k}/${old_n}"
        wfb_tx_cmd "${port}" set_fec -k "${old_k}" -n "${old_n}" 2>/dev/null || true
    done
    WFB_RESTORE=""
    WFB_RESTORE_FEC=""
}
