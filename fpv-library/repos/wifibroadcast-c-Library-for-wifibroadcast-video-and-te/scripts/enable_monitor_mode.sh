#!/bin/bash

# Simple script to enable monitor mode on a wifi card
# Intended to be used with executables/example_hello.cpp

# Write your own card name here !!
MY_WIFI_CARD=$1

echo "Enabling monitor mode on card: $MY_WIFI_CARD";

# tell network manager to keep its hands from this card
# If OS doesn't use nm, you might have to find suitable replacement !!
sudo nmcli device set $MY_WIFI_CARD managed no

# might be needed / might not be needed
sudo rfkill unblock all

sleep 1s

sudo ifconfig $MY_WIFI_CARD down
sudo iw dev $MY_WIFI_CARD set monitor otherbss fcsfail
sudo ifconfig $MY_WIFI_CARD up





