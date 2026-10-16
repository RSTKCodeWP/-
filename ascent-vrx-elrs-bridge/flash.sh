#!/usr/bin/env bash
# Прошивка ESP32-S3 DevKit (Linux/macOS). Порт: ESP_PORT або перший ttyACM/ttyUSB.
set -euo pipefail
cd "$(dirname "$0")"

if [[ -z "${IDF_PATH:-}" ]]; then
  if [[ -f "$HOME/esp/esp-idf/export.sh" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/esp/esp-idf/export.sh"
  else
    echo "Спочатку: source ~/esp/esp-idf/export.sh"
    exit 1
  fi
fi

PORT="${ESP_PORT:-}"
if [[ -z "$PORT" ]]; then
  for p in /dev/ttyACM0 /dev/ttyUSB0 /dev/cu.usbmodem*; do
    if [[ -e "$p" ]]; then
      PORT="$p"
      break
    fi
  done
fi
if [[ -z "$PORT" ]]; then
  echo "Підключіть ESP32 і вкажіть порт: ESP_PORT=/dev/ttyACM0 $0"
  exit 1
fi

echo "Target port: $PORT"
idf.py set-target esp32s3
idf.py build
idf.py -p "$PORT" flash monitor
