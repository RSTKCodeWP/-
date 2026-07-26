#!/bin/bash

if [ "$1" == "arduino" ]; then
  sed -i '/dtoverlay=miniuart-bt/d' /boot/config.txt
else
  echo "
[miniuart - for non-Arduino PCBs - RH_Install-Manager]
dtoverlay=miniuart-bt
  " | sudo tee -a /boot/config.txt
fi
