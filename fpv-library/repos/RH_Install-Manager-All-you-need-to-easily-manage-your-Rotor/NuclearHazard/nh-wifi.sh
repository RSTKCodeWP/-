#!/bin/bash

sudo rm /home/"$USER"/hotspot.sh >/dev/null 2>&1

echo
echo "if iwgetid -r | grep -q .; then
    echo "Wi-Fi network found. Not creating a hotspot."
else
    nmcli dev wifi hotspot ifname wlan0 ssid "NuclearHazard" password "nuclearhazard"
fi" | sudo tee -a /home/"$USER"/hotspot.sh
sudo chmod +x /home/"$USER"/hotspot.sh

sudo rm /etc/systemd/system/hotspot.service >/dev/null 2>&1

echo "

[Unit]
Description=Hotspot Service
After=NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=simple
ExecStartPre=/bin/sleep 10
ExecStart=sudo /home/$USER/hotspot.sh
WorkingDirectory=/home/$USER/

[Install]
WantedBy=multi-user.target" | sudo tee -a /etc/systemd/system/hotspot.service
sudo systemctl enable hotspot.service

echo "


--- Automatic NuclearHazard AccessPoint enabled ---

SSID: NuclearHazard
PSWD: nuclearhazard

"
