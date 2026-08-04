cd /home/pilot/start/
pkill -f ua-pilot
killall ua-pilot
pkill -f lserv
killall lserv
rm -rf ./binary
rm -rf ./downloads
rm -rf ./images
rm -rf ./data/settings
rm -f ./data/*
rm -f ./*.txt
rm -f ./*.log
rm -f ./*.zip
rm -rf /data/records/*

# rm -f ./start/*.sh
rm -rf /data/records/*
./wipe.sh