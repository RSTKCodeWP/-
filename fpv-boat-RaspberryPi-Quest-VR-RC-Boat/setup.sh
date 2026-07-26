#!/usr/bin/env bash
# One-shot provisioning for a fresh Raspberry Pi OS (Bookworm) install.
#
# Run from the repo root on the Pi:
#     bash setup.sh
#
# Idempotent — safe to re-run. It enables I2C, installs the system + Python
# dependencies, generates the self-signed TLS cert WebXR needs, and adds the
# passwordless-shutdown sudoers rule. Everything the project needs to run after
# a fresh image / SD reflash.
set -uo pipefail

echo "[setup] FPV boat — provisioning this Pi"

# --- 1. Interfaces -----------------------------------------------------------
# I2C drives the PCA9685 (pan/tilt) and the INA219 (battery). The camera works
# through libcamera by default on Bookworm, so no legacy-camera toggle is needed.
echo "[setup] enabling I2C…"
sudo raspi-config nonint do_i2c 0 \
  || echo "[setup] (couldn't toggle I2C via raspi-config — enable it manually if i2cdetect fails)"

# --- 2. System packages ------------------------------------------------------
# python3-picamera2 comes from apt (it's tied to libcamera; don't pip it).
# The libav*/opus/vpx dev libs let aiortc + PyAV build cleanly if no wheel exists.
echo "[setup] apt packages…"
sudo apt-get update
sudo apt-get install -y \
  python3-picamera2 python3-pip i2c-tools git \
  libopus-dev libvpx-dev pkg-config \
  libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev

# --- 3. Python packages ------------------------------------------------------
# Bookworm's pip refuses system-wide installs without --break-system-packages.
# gpiozero uses the lgpio pin factory by default here (pigpio is no longer
# packaged and isn't needed). servokit = pan/tilt, pi-ina219 = battery.
echo "[setup] pip packages…"
pip3 install --break-system-packages \
  aiohttp aiortc gpiozero lgpio adafruit-circuitpython-servokit pi-ina219

# --- 4. TLS cert (WebXR requires HTTPS) --------------------------------------
if [ ! -f "$HOME/cert.pem" ] || [ ! -f "$HOME/key.pem" ]; then
  echo "[setup] generating self-signed cert…"
  openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
    -keyout "$HOME/key.pem" -out "$HOME/cert.pem" -subj "/CN=fpv-boat"
else
  echo "[setup] cert already present — skipping"
fi

# --- 5. Passwordless shutdown ------------------------------------------------
# Needed by the thermal auto-shutdown and the in-VR shutdown combo.
if [ ! -f /etc/sudoers.d/thermal-shutdown ]; then
  echo "[setup] adding passwordless-shutdown sudoers rule…"
  echo "$USER ALL=(ALL) NOPASSWD: /sbin/shutdown" | sudo tee /etc/sudoers.d/thermal-shutdown >/dev/null
  sudo chmod 440 /etc/sudoers.d/thermal-shutdown
else
  echo "[setup] shutdown sudoers rule already present — skipping"
fi

echo
echo "[setup] done. Sanity checks:"
echo "  i2cdetect -y 1               # expect 40 (PCA9685); 41 too if you moved the INA219"
echo "  python3 pan_tilt_control.py  # servo sweep (hardware: True once wired)"
echo "  python3 webrtc_stream.py     # start the server — HTTPS on :5000"
echo
echo "Then open  https://<pi-ip>:5000/viewer  in the Quest browser."
