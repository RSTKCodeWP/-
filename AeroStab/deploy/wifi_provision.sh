#!/usr/bin/env bash
# WiFi provisioning — StabX-style wifi.txt (line1=SSID, line2=password).
# Usage:
#   aerostab-wifi                          # /etc/aerostab/wifi.txt or USB
#   aerostab-wifi "MySSID" "password"
set -euo pipefail

WIFI_FILE="${AEROSTAB_WIFI_FILE:-/etc/aerostab/wifi.txt}"
LOG_FILE="${AEROSTAB_WIFI_LOG:-/var/log/aerostab/wifi.log}"

log() { echo "$(date '+%F %T') $*" | tee -a "$LOG_FILE"; }

connect_wifi() {
  local ssid="$1" pass="$2"
  [[ -n "$ssid" ]] || { log "SSID empty — skip"; return 1; }
  log "Connecting to SSID=$ssid"
  if command -v nmcli >/dev/null 2>&1; then
    nmcli radio wifi on 2>/dev/null || true
    nmcli dev wifi connect "$ssid" password "$pass" 2>&1 | tee -a "$LOG_FILE" && return 0
  fi
  if command -v wpa_passphrase >/dev/null 2>&1 && [[ -f /etc/wpa_supplicant/wpa_supplicant.conf ]]; then
    wpa_passphrase "$ssid" "$pass" >> /etc/wpa_supplicant/wpa_supplicant.conf
    wpa_cli -i wlan0 reconfigure 2>/dev/null || true
    return 0
  fi
  log "No nmcli/wpa_supplicant — cannot connect"
  return 1
}

read_wifi_file() {
  local f="$1"
  [[ -f "$f" ]] || return 1
  {
    IFS= read -r SSID
    IFS= read -r PASSWORD
  } < <(tr -d '\r' < "$f")
  SSID="${SSID//$'\n'/}"
  PASSWORD="${PASSWORD//$'\n'/}"
  connect_wifi "$SSID" "$PASSWORD"
}

# CLI args
if [[ $# -ge 1 ]]; then
  mkdir -p "$(dirname "$LOG_FILE")"
  connect_wifi "$1" "${2:-}"
  exit $?
fi

mkdir -p "$(dirname "$LOG_FILE")"

# Config file (StabX: data/wifi.txt)
if read_wifi_file "$WIFI_FILE"; then
  exit 0
fi

# USB mounts (StabX run_usb.sh pattern)
for mount in /media/*/* /media/*; do
  [[ -d "$mount" ]] || continue
  if [[ -f "$mount/wifi.txt" ]]; then
    log "Found $mount/wifi.txt"
    cp -f "$mount/wifi.txt" "$WIFI_FILE" 2>/dev/null || true
    read_wifi_file "$mount/wifi.txt" && exit 0
  fi
done

log "No wifi.txt found — using NetworkManager profiles if any"
exit 0
