#!/bin/bash

# Simple script to set a default wifi frequency on a card in monitor mode
#

# wifi card is first param
MY_WIFI_CARD=$1

# frequency is second param
MY_WIFI_FREQ_MHZ=$2

# channel width is third param
MY_WIFI_CHANNEL_WIDTH=$3

echo "Setting $MY_WIFI_CARD to $MY_WIFI_FREQ_MHZ at $MY_WIFI_CHANNEL_WIDTH"

sudo iw dev $MY_WIFI_CARD set freq $MY_WIFI_FREQ_MHZ $MY_WIFI_CHANNEL_WIDTH