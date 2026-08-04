#!/bin/sh
# inet.sh — Pick a working interface, set default route, and fix DNS if needed.

TARGET_IP="${TARGET_IP:-8.8.8.8}"           # Connectivity check target (IP)
DNS_TEST_HOST="${DNS_TEST_HOST:-google.com}" # DNS check target (hostname)
DNS_SERVERS_DEFAULT="${DNS_SERVERS_DEFAULT:-8.8.8.8 1.1.1.1}"  # Fallback DNS list
PING_TIMEOUT=1
MAX_RETRIES=3

say() { printf "%s\n" "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

# Resolve a host; returns 0 on success
check_dns() {
  # Prefer getent (glibc NSS), fallback to busybox nslookup if present
  if have getent; then
    timeout 3 getent hosts "$1" >/dev/null 2>&1
    return $?
  elif have nslookup; then
    timeout 3 nslookup "$1" >/dev/null 2>&1
    return $?
  else
    # last resort: wget header request (no download)
    timeout 4 wget -qO- --spider "http://$1" >/dev/null 2>&1
    return $?
  fi
}

# Try to set DNS for a specific interface using nmcli (preferred)
set_dns_nmcli() {
  IF="$1"; DNS_LIST="$2"
  have nmcli || return 1
  # find the connection bound to IF
  CONN=$(nmcli -t -f NAME,DEVICE con show --active 2>/dev/null | awk -F: -v if="$IF" '$2==if {print $1; exit}')
  [ -n "$CONN" ] || return 2
  say "[*] Setting DNS via nmcli on connection '$CONN' -> $DNS_LIST"
  nmcli con modify "$CONN" ipv4.dns "$DNS_LIST" >/dev/null 2>&1 || return 3
  nmcli con modify "$CONN" ipv4.ignore-auto-dns yes >/dev/null 2>&1 || return 4
  nmcli con down "$CONN" >/dev/null 2>&1
  nmcli con up   "$CONN" >/dev/null 2>&1
  return 0
}

# Fallback: write /etc/resolv.conf (may be overwritten later by dhcpcd/systemd)
set_dns_resolvconf() {
  DNS_LIST="$1"
  say "[*] Writing /etc/resolv.conf with: $DNS_LIST"
  {
    for d in $DNS_LIST; do echo "nameserver $d"; done
  } | sudo tee /etc/resolv.conf >/dev/null
}

# Bring interfaces down/up to refresh DHCP/NM
refresh_interfaces() {
  say "[*] Refreshing interfaces..."
  for IF in $(ip -o -4 addr show | awk '{print $2}' | sort -u); do
    [ "$IF" = "lo" ] && continue
    say "    -> reset $IF"
    if have nmcli; then
      nmcli dev disconnect "$IF" >/dev/null 2>&1
      nmcli dev connect    "$IF" >/dev/null 2>&1
    fi
    ip link set "$IF" down >/dev/null 2>&1
    sleep 1
    ip link set "$IF" up   >/dev/null 2>&1
  done
  sleep 3
}

try_once() {
  IFACES=$(ip -o -4 addr show | awk '{print $2}' | sort -u)
  FOUND=1  # assume fail

  for IF in $IFACES; do
    [ "$IF" = "lo" ] && continue
    # ensure link up
    ip link show "$IF" | grep -q "UP" || continue

    say "[..] Testing $IF -> $TARGET_IP"
    if ping -I "$IF" -c1 -W"$PING_TIMEOUT" "$TARGET_IP" >/dev/null 2>&1; then
      # find gateway for this IF
      GW="$(ip route get "$TARGET_IP" oif "$IF" 2>/dev/null | awk '/ via / {for(i=1;i<=NF;i++) if($i=="via"){print $(i+1); exit}}')"
      [ -z "$GW" ] && GW="$(ip route show dev "$IF" | awk '/^default / {print $3; exit}')"
      if [ -n "$GW" ]; then
        say "[OK] $IF has raw Internet; gateway $GW"
        sudo ip route replace default via "$GW" dev "$IF" metric 100 || {
          say "[ERR] Failed to set default route via $GW dev $IF"
          return 1
        }
        ip route | sed -n '1,3p'

        # DNS check
        if check_dns "$DNS_TEST_HOST"; then
          say "[✓] DNS works: $DNS_TEST_HOST resolves."
          return 0
        fi

        say "[!] DNS broken. Attempting repair..."
        if set_dns_nmcli "$IF" "$DNS_SERVERS_DEFAULT"; then
          sleep 1
          if check_dns "$DNS_TEST_HOST"; then
            say "[✓] DNS fixed via nmcli."
            return 0
          fi
        fi

        # Fallback to resolv.conf
        set_dns_resolvconf "$DNS_SERVERS_DEFAULT"
        sleep 1
        if check_dns "$DNS_TEST_HOST"; then
          say "[✓] DNS fixed by /etc/resolv.conf."
          return 0
        else
          say "[X] DNS still failing after fixes; continuing to next IF…"
        fi
      fi
    fi
  done

  return $FOUND
}

# ---------------- Main ----------------
for TRY in $(seq 1 "$MAX_RETRIES"); do
  say "=== Attempt $TRY/$MAX_RETRIES ==="
  if try_once; then
    say "[✓] Internet available and DNS OK."
    exit 0
  fi
  say "[!] No fully working interface — refreshing and retrying…"
  refresh_interfaces
done

say "[✗] Gave up after $MAX_RETRIES attempts."
exit 1
