#!/bin/bash

# Simple script to enable monitor mode and set same frequency all together
# Intended to be used with executables/example_hello.cpp

if [ $# -eq 0 ]
  then
    echo "Please specify the card intended for wifibroadcast"
    exit -1
fi

# !! Need to pass card
MY_WIFI_CARD=$1


sh ./enable_monitor_mode.sh $MY_WIFI_CARD

# Should work on most card(s) - 5180Mhz at HT20 (20Mhz channel width)
sh ./set_freq.sh $MY_WIFI_CARD 5180 HT20


