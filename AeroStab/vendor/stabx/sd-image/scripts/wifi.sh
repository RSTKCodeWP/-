#!/usr/bin/env bash

# Define the path to the wifi.txt file
WIFI_FILE="/home/pilot/start/data/wifi.txt"

# Check if wifi.txt exists
if [[ ! -f "$WIFI_FILE" ]]; then
    echo "wifi.txt not found at $WIFI_FILE. Continuing with the rest of the script..."
    # If file is not found, skip the Wi-Fi connection section and continue
else
    echo "wifi.txt found!"
    # Read the SSID and password, removing any trailing carriage returns
    {
      IFS= read -r SSID
      IFS= read -r PASSWORD
    } < <(tr -d '\r' < "$WIFI_FILE")
    echo "SSID=$SSID PASS=$PASSWORD"
    # break if the SSID is empty
    if [ -z "$SSID" ]; then
        echo "SSID is empty. Skipping connection attempt and continuing..."
        exit 1
    fi
    echo "WIFI.TXT found: SSID=$SSID, PASSWORD=$PASSWORD, attempting to connect..."
    nmcli dev wifi list
    nmcli device wifi connect "$SSID" password "$PASSWORD"
    nmcli dev wifi list
fi