#!/bin/bash
set -e

echo "=== Steam Deck GCS Installer ==="
echo ""

# --- QGroundControl ---
echo "[1/7] Installing QGroundControl via Flatpak..."
if flatpak list --user | grep -q org.mavlink.qgroundcontrol; then
    echo "  QGroundControl already installed, updating..."
    flatpak update -y --user org.mavlink.qgroundcontrol
else
    flatpak install -y --user flathub org.mavlink.qgroundcontrol
fi
flatpak override --user --device=all org.mavlink.qgroundcontrol
echo "  Done."

# --- Nix ---
echo ""
echo "[2/7] Setting up Nix package manager..."
if command -v nix &>/dev/null; then
    echo "  Nix already installed."
elif [ -f "$HOME/.nix-profile/etc/profile.d/nix.sh" ]; then
    echo "  Nix installed but not in PATH. Sourcing..."
    . "$HOME/.nix-profile/etc/profile.d/nix.sh"
else
    echo "  /nix directory must be owned by your user."
    echo "  Run: sudo chown -R $USER /nix"
    echo "  Then re-run this script."

    if [ ! -w /nix ]; then
        echo ""
        echo "  ERROR: /nix is not writable. Please run:"
        echo "    sudo chown -R $USER /nix"
        echo "  Then re-run this script."
        exit 1
    fi

    curl -L https://nixos.org/nix/install -o /tmp/nix-install.sh
    bash /tmp/nix-install.sh --no-daemon
    . "$HOME/.nix-profile/etc/profile.d/nix.sh"
fi

# Ensure nix is in PATH for the rest of the script
. "$HOME/.nix-profile/etc/profile.d/nix.sh"
echo "  Nix $(nix --version)"

# --- Mono ---
echo ""
echo "[3/7] Installing Mono via Nix..."
if command -v mono &>/dev/null; then
    echo "  Mono already installed: $(mono --version | head -1)"
else
    nix-env -iA nixpkgs.mono
    echo "  Mono installed: $(mono --version | head -1)"
fi

# --- Mission Planner ---
echo ""
echo "[4/7] Setting up Mission Planner..."
MP_DIR="$HOME/.local/share/mission-planner"

if [ -f "$MP_DIR/MissionPlanner.exe" ]; then
    echo "  Mission Planner already installed at $MP_DIR"
else
    # Check for zip in common locations
    MP_ZIP=""
    for candidate in \
        "$HOME/Downloads/MissionPlanner-latest.zip" \
        "$HOME/Downloads/MissionPlanner*.zip" \
        "./MissionPlanner-latest.zip" \
        "./MissionPlanner*.zip"; do
        # shellcheck disable=SC2086
        found=$(ls $candidate 2>/dev/null | head -1)
        if [ -n "$found" ]; then
            MP_ZIP="$found"
            break
        fi
    done

    if [ -z "$MP_ZIP" ]; then
        echo "  Downloading Mission Planner..."
        MP_ZIP="/tmp/MissionPlanner-latest.zip"
        curl -L "https://firmware.ardupilot.org/Tools/MissionPlanner/MissionPlanner-latest.zip" -o "$MP_ZIP"
    fi

    echo "  Extracting to $MP_DIR..."
    mkdir -p "$MP_DIR"
    unzip -qo "$MP_ZIP" -d "$MP_DIR"
    echo "  Done."
fi

# --- Scripts and desktop entries ---
echo ""
echo "[5/7] Installing MAVProxy (CLI GCS with joystick support)..."
MAVPROXY_VENV="$HOME/.local/share/mavproxy-venv"
if [ -f "$MAVPROXY_VENV/bin/mavproxy.py" ]; then
    echo "  MAVProxy already installed."
else
    python3 -m venv "$MAVPROXY_VENV"
    "$MAVPROXY_VENV/bin/pip" install MAVProxy pygame setuptools
    echo "  MAVProxy installed."
fi

echo ""
echo "[6/7] Installing MAVProxy joystick config for Steam Deck..."
mkdir -p "$HOME/.mavproxy/joysticks"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SCRIPT_DIR/config/steam-deck.yml" "$HOME/.mavproxy/joysticks/"
echo "  Joystick config installed to ~/.mavproxy/joysticks/steam-deck.yml"

echo ""
echo "[7/7] Installing launcher scripts and desktop entries..."
mkdir -p "$HOME/.local/bin"

# Mission Planner launcher
cat > "$HOME/.local/bin/mission-planner" << 'LAUNCHER'
#!/bin/bash
. "$HOME/.nix-profile/etc/profile.d/nix.sh"
exec systemd-inhibit --what=idle --who="Mission Planner" --why="GCS active" \
    mono "$HOME/.local/share/mission-planner/MissionPlanner.exe" "$@"
LAUNCHER
chmod +x "$HOME/.local/bin/mission-planner"

# Post-update recovery script
cat > "$HOME/.local/bin/gcs-post-update" << 'RECOVERY'
#!/bin/bash
echo "Restoring GCS udev rules..."
sudo ln -sf "$HOME/.config/udev-rules/99-serial-gcs.rules" /etc/udev/rules.d/99-serial-gcs.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
echo "Done. Nix, Mission Planner, and QGroundControl should still be working."
echo "If mono is missing, run: . ~/.nix-profile/etc/profile.d/nix.sh && mono --version"
RECOVERY
chmod +x "$HOME/.local/bin/gcs-post-update"

# MAVProxy launcher
cat > "$HOME/.local/bin/mavproxy-gcs" << 'MAVLAUNCHER'
#!/bin/bash
. "$HOME/.nix-profile/etc/profile.d/nix.sh"
source "$HOME/.local/share/mavproxy-venv/bin/activate"
PORT="/dev/ttyACM0"
BAUD="460800"
if [ "$#" -gt 0 ]; then
    PORT="$1"
    shift
fi
if [ "$#" -gt 0 ]; then
    BAUD="$1"
    shift
fi
echo "=== Steam Deck MAVProxy GCS ==="
echo "Port: $PORT  Baud: $BAUD"
echo ""
exec systemd-inhibit --what=idle --who="MAVProxy" --why="GCS active" \
    mavproxy.py --master="$PORT" --baudrate="$BAUD" --load-module joystick --aircraft=SteamDeckGCS "$@"
MAVLAUNCHER
chmod +x "$HOME/.local/bin/mavproxy-gcs"

# Desktop entry for Mission Planner
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/mission-planner.desktop" << 'DESKTOP'
[Desktop Entry]
Name=Mission Planner
Comment=Mission Planner Ground Control Station
GenericName=Ground Control Station
Exec=bash -c '. $HOME/.nix-profile/etc/profile.d/nix.sh && systemd-inhibit --what=idle --who="Mission Planner" --why="GCS active" mono $HOME/.local/share/mission-planner/MissionPlanner.exe'
Icon=$HOME/.local/share/mission-planner/mpdesktop150.png
Type=Application
StartupNotify=false
Categories=Utility;
Keywords=ardupilot;mission;planner;uav;drone
DESKTOP

# Udev rules for serial devices
mkdir -p "$HOME/.config/udev-rules"
cat > "$HOME/.config/udev-rules/99-serial-gcs.rules" << 'UDEV'
# Give user access to USB serial devices (ELRS TX modules, flight controllers)
# ESP32-based ELRS devices (RadioMaster Nomad)
SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", MODE="0660", TAG+="uaccess"
# Silicon Labs CP210x
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", MODE="0660", TAG+="uaccess"
# WCH CH340
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", MODE="0660", TAG+="uaccess"
# FTDI
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", MODE="0660", TAG+="uaccess"
# STM virtual COM ports
SUBSYSTEM=="tty", ATTRS{idVendor}=="0483", MODE="0660", TAG+="uaccess"
UDEV

echo "  Launcher scripts installed."
echo ""

# --- Udev activation ---
echo "=== Setup Complete ==="
echo ""
echo "To activate serial port access (requires sudo):"
echo "  sudo ln -sf $HOME/.config/udev-rules/99-serial-gcs.rules /etc/udev/rules.d/99-serial-gcs.rules"
echo "  sudo udevadm control --reload-rules"
echo ""
echo "Launch commands:"
echo "  QGroundControl:  flatpak run org.mavlink.qgroundcontrol"
echo "  Mission Planner: mission-planner"
echo "  MAVProxy:        mavproxy-gcs [port] [baud]"
echo ""
echo "After SteamOS updates, run: gcs-post-update"
