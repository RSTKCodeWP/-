#!/bin/bash
# Ruben-FPV Common Configuration
# This file is sourced by both air and ground units

# WiFi adapter interface (check with: iwconfig)
# Use wlan1 for T2U Plus, wlan0 for onboard as fallback
WIFI_INTERFACE="${WIFI_INTERFACE:-wlan1}"

# 5GHz channel (36, 40, 44, 48 are common DFS-free channels)
WIFI_CHANNEL="${WIFI_CHANNEL:-36}"

# Internal UDP port for video pipeline
VIDEO_PORT="${VIDEO_PORT:-5000}"

# Packet settings
MTU_SIZE="${MTU_SIZE:-1400}"

# Broadcast address for 802.11
BROADCAST_ADDR="ff:ff:ff:ff:ff:ff"
