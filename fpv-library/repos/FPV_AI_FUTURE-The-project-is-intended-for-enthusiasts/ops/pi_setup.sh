#!/usr/bin/env bash
# Install the 03-fpv runtime dependencies on the Raspberry Pi 5 (runs ON THE PI, inside 03-fpv/).
# Bench/flight software only -- no motors are driven by this code, only the 2 gimbal servos.
set -euo pipefail

echo ">> apt: opencv / numpy / scipy / i2c tools (system packages -- fast, ARM-native wheels)"
sudo apt-get update -qq
sudo apt-get install -y python3-opencv python3-numpy python3-scipy i2c-tools python3-pip

echo ">> pip: crypto + serial + i2c (the bits apt does not carry)"
# --break-system-packages: RPi OS marks the system python externally-managed; these are small pure/thin pkgs.
pip3 install --break-system-packages pynacl cryptography pyserial smbus2 pytest

echo ">> enable I2C if not already (needed for the head IMU 0x68 + PCA9685 0x40)"
if command -v raspi-config >/dev/null 2>&1; then
  sudo raspi-config nonint do_i2c 0 || true
fi

echo ">> sanity: imports"
PYTHONPATH=.:fpv python3 - <<'PY'
import numpy, scipy, cv2, nacl, cryptography, serial
print("core deps OK:", "numpy", numpy.__version__, "| cv2", cv2.__version__)
import fpv.fpv_ai.flight_gimbal, fpv.fpv_ai.flight_head, fpv.guidance.march
print("flight modules import OK")
PY

echo ">> i2c bus (expect 0x68 IMU + 0x40 PCA9685 once wired):"
i2cdetect -y 1 || echo "   (i2cdetect needs the bus wired + I2C enabled + a reboot)"

echo ">> done. Verify the full component gate on the Pi:"
echo "   PYTHONPATH=.:fpv python3 -m pytest fpv/ -q -m 'not slow'"
