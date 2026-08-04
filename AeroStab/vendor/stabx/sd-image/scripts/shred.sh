#!/usr/bin/env bash
#
# shred_all_sensitive.sh
#
# Use with extreme caution. This script:
#   1) Stops journald and Bluetooth daemons.
#   2) Shreds all log files in /var/log (and /var/log/journal if present).
#   3) Shreds Bluetooth config data in /var/lib/bluetooth.
#   4) Shreds Bash history for all users.
#   5) Restarts journald and Bluetooth daemons.
#
# Note: Shredding is not fully effective on SSDs or with journaling file systems
# due to wear-leveling and copy-on-write.

# set -e  # stop on error

echo "===> Stopping Bluetooth and journald..."
systemctl stop bluetooth || true

echo "===> Shredding /var/lib/bluetooth..."
if [ -d /var/lib/bluetooth ]; then
  find /var/lib/bluetooth -type f -exec shred -u -z -v {} +
  rm -rf /var/lib/bluetooth/*
fi

echo "===> Shredding all logs in /var/log..."
if [ -d /var/log ]; then
  find /var/log -type f -exec shred -u -z -v {} +
  rm -rf /var/log/*
fi

echo "===> Shredding systemd journals (if persistent)..."
if [ -d /var/log/journal ]; then
  find /var/log/journal -type f -exec shred -u -z -v {} +
  rm -rf /var/log/journal
fi

# (Optional) Shred /run/log/journal if needed, though it's typically in RAM:
# if [ -d /run/log/journal ]; then
#   find /run/log/journal -type f -exec shred -u -z -v {} +
#   rm -rf /run/log/journal
# fi

echo "===> Shredding Bash history for all users..."
# For each home directory (including /root), shred .bash_history
for user_home in /home/* /root; do
    if [ -d "$user_home" ]; then
        hist_file="$user_home/.bash_history"
        if [ -f "$hist_file" ]; then
            echo "Shredding $hist_file"
            shred -u -z -v "$hist_file"
        fi
    fi
done

# Optionally, remove global bash history if your system uses it:
if [ -f /etc/.bash_history ]; then
  shred -u -z -v /etc/.bash_history
fi

echo "===> Restarting Bluetooth and journald..."
systemctl start systemd-journald || true
systemctl start bluetooth || true

echo "===> Done. All specified logs and history have been shredded."
