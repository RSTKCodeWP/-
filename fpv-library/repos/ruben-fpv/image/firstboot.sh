#!/bin/bash
#
# Ruben-FPV First Boot Configuration
# Reads /boot/firmware/ruben.txt and configures the system accordingly
#

set -e

LOG="/var/log/ruben-firstboot.log"
exec > >(tee -a "$LOG") 2>&1

echo "=========================================="
echo "RUBEN-FPV FIRST BOOT SETUP"
echo "$(date)"
echo "=========================================="

# Find config file (different locations on different Pi OS versions)
CONFIG=""
for path in /boot/firmware/ruben.txt /boot/ruben.txt; do
    if [ -f "$path" ]; then
        CONFIG="$path"
        break
    fi
done

if [ -z "$CONFIG" ]; then
    echo "[!] No ruben.txt found, defaulting to AIR unit"
    ROLE="air"
else
    echo "[*] Reading config from $CONFIG"
    source "$CONFIG"
    ROLE="${ROLE:-air}"
fi

echo "[*] Configuring as: ${ROLE^^} UNIT"

# Common setup
echo "[*] Installing dependencies..."
apt-get update
apt-get install -y ffmpeg python3-scapy wireless-tools iw

# Install pre-compiled driver if present
DRIVER_PATH="/opt/ruben-fpv/drivers/rtl8812au/88XXau.ko.xz"
if [ -f "$DRIVER_PATH" ]; then
    KERNEL=$(uname -r)
    echo "[*] Installing RTL8812AU driver for kernel $KERNEL"

    mkdir -p "/lib/modules/$KERNEL/updates/dkms"
    cp "$DRIVER_PATH" "/lib/modules/$KERNEL/updates/dkms/"
    depmod -a

    # Load on boot
    echo "88XXau" >> /etc/modules-load.d/ruben-fpv.conf
    echo "[+] Driver installed"
else
    echo "[!] Pre-compiled driver not found at $DRIVER_PATH"
fi

# Role-specific setup
case "$ROLE" in
    air)
        echo "[*] Configuring AIR UNIT (headless, auto-start TX)"

        # Disable desktop if present
        systemctl set-default multi-user.target 2>/dev/null || true
        systemctl disable lightdm 2>/dev/null || true
        systemctl disable gdm 2>/dev/null || true

        # Copy air unit files
        cp /opt/ruben-fpv/repo/air/* /opt/ruben-fpv/ 2>/dev/null || true
        cp -r /opt/ruben-fpv/repo/common /opt/ruben-fpv/ 2>/dev/null || true

        # Enable service
        systemctl enable ruben-fpv.service

        echo "[+] Air unit configured - will auto-start on next boot"
        ;;

    ground)
        echo "[*] Configuring GROUND STATION (desktop, display)"

        # Install desktop and video player
        apt-get install -y --no-install-recommends xserver-xorg xinit openbox mpv

        # Enable desktop
        systemctl set-default graphical.target 2>/dev/null || true

        # Copy ground station files
        cp /opt/ruben-fpv/repo/ground/* /opt/ruben-fpv/ 2>/dev/null || true
        cp -r /opt/ruben-fpv/repo/common /opt/ruben-fpv/ 2>/dev/null || true

        # Enable service
        systemctl enable ruben-fpv.service

        # Auto-login and start X (optional)
        mkdir -p /etc/systemd/system/getty@tty1.service.d
        cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf << 'AUTOLOGIN'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin pi --noclear %I $TERM
AUTOLOGIN

        echo "[+] Ground station configured"
        ;;

    *)
        echo "[-] Unknown role: $ROLE"
        exit 1
        ;;
esac

# Set permissions
chmod +x /opt/ruben-fpv/*.sh 2>/dev/null || true
chmod +x /opt/ruben-fpv/*.py 2>/dev/null || true

# Detect WiFi interface
echo "[*] Detecting WiFi interface..."
sleep 2  # Wait for USB devices
IFACE=$(iw dev | grep Interface | grep -v wlan0 | awk '{print $2}' | head -1)
IFACE=${IFACE:-wlan1}
echo "[*] Using interface: $IFACE"
sed -i "s/WIFI_INTERFACE=.*/WIFI_INTERFACE=\"$IFACE\"/" /opt/ruben-fpv/config.sh 2>/dev/null || true

# Disable this firstboot service
systemctl disable ruben-firstboot.service

# Mark setup complete
touch /opt/ruben-fpv/.setup-complete
echo ""
echo "=========================================="
echo "SETUP COMPLETE - Rebooting in 5 seconds"
echo "=========================================="
sleep 5
reboot
