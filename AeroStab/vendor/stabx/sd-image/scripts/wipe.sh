#!/usr/bin/env bash

cd /home/pilot/

#
# wipe.sh
# Wipes user shell histories, clears system logs, removes Bluetooth pairings,
# and removes select dotfiles in user homes that are safe to delete.
# Usage: sudo ./wipe.sh

set -e  # Exit immediately if any command fails

echo "=== 1) Removing user shell histories and dotfiles ==="

# For each user's home directory
for user_home in /home/*; do
    if [[ -d "$user_home" ]]; then
        username=$(basename "$user_home")
        echo " - Clearing history and certain dotfiles for: $username"

        # Remove shell history files
        rm -f "$user_home/.bash_history" 2>/dev/null || true
        rm -f "$user_home/.zsh_history"  2>/dev/null || true
        rm -f "$user_home/.sh_history"   2>/dev/null || true

        # Remove certain dotfiles that are generally safe to wipe:
        rm -f "$user_home/.xsession-errors"      2>/dev/null || true
        rm -f "$user_home/.xsession-errors.old"  2>/dev/null || true
        rm -f "$user_home/.face"                 2>/dev/null || true
        rm -f "$user_home/.face.icon"            2>/dev/null || true
        rm -f "$user_home/.selected_editor"      2>/dev/null || true
        rm -f "$user_home/.wget-hsts"            2>/dev/null || true

        # If you want to remove caches/config:
        # rm -rf "$user_home/.cache/" 2>/dev/null || true
        # rm -rf "$user_home/.config/" 2>/dev/null || true
        # rm -rf "$user_home/.local/" 2>/dev/null || true
    fi
done

# Remove root’s shell history as well
echo " - Clearing root's shell history"
rm -f /root/.bash_history 2>/dev/null || true
rm -f /root/.zsh_history  2>/dev/null || true
rm -f /root/.sh_history   2>/dev/null || true

# If you want to remove certain root’s dotfiles too:
# rm -f /root/.xsession-errors* 2>/dev/null || true
# rm -f /root/.face*            2>/dev/null || true
# rm -f /root/.selected_editor  2>/dev/null || true
# rm -f /root/.wget-hsts        2>/dev/null || true

echo "=== 2) Clearing the current shell’s in-memory history (if running interactively) ==="
# This only clears *this* shell’s history. If run via a script (subshell), it won’t affect the parent shell.
history -c 2>/dev/null || true
history -w 2>/dev/null || true

echo "=== 3) Removing system logs ==="
rm -rf /var/log/*
mkdir -p /var/log

# If systemd journaling is used:
if command -v journalctl &>/dev/null; then
    journalctl --rotate
    journalctl --vacuum-time=1s
fi

echo "=== 4) Removing Bluetooth device history ==="
if [[ -d /var/lib/bluetooth ]]; then
    rm -rf /var/lib/bluetooth/*
    echo " - Removed all Bluetooth pairing data."
fi

echo "=== Done wiping histories, logs, and selected user dotfiles. ==="

