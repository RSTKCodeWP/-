#!/bin/bash
sleep 1
killall lserv
pkill -f lserv
killall ua-pilot
pkill -f creepy
killall creepy
pkill -f ua-pilot
mv -f ./images/unzip/ua-pilot.enc ./binary/fad1aef552e42899bad1ab015d92a96f/ua-pilot.enc
find ./data/ -mindepth 1 -maxdepth 1 -not -name records -exec rm -rf {} +
mv -f ./images/unzip/* ./data/
chmod -R 777 ./data/*
sudo chown -R pilot:common ./data/
sleep 2
rm -f ./lserv.zip
mv -f ./data/lserv.zip ./
unzip -o ./lserv.zip -d ./
chmod +x ./lserv
chmod +x ./creepy
rm -f ./lserv.zip
sleep 1
sudo reboot now
