#!/bin/sh

	# Decide MCS, guard interval, FEC, bit-rate, gop size and power based on the range [1000,2000] from radio
	# Need > wfb_tx v24 (with -C 8000 added to /usr/bin/wifibroadcast) and wfb_tx_cmd v24
	# Need msposd (tipoman9) to update local OSD

if [ -e /etc/txprofile ]; then
	. /etc/txprofile
fi

oldProfile=$vidRadioProfile
newTimeStamp=$(date +%s)
oldTimeStamp=$prevTimeStamp
secondsSinceLastChange=$((newTimeStamp-oldTimeStamp))
	
			
	elif [ $2 -eq 999 ] ;then
				
		setGI=long
		setMCS=0
		setFecK=12
		setFecN=15
		setBitrate=3332
		setGop=5
		wfbPower=61
		ROIqp="0,0,0,0"		
		newProfile=0

	elif [ $2 -eq 1000 ] ;then
				
		setGI=long
		setMCS=0
		setFecK=12
		setFecN=15
		setBitrate=3333
		setGop=5
		wfbPower=61
		ROIqp="0,0,0,0"		
		newProfile=1
		
	elif [ $2 -lt 1300 ];then
		
		setGI=long
		setMCS=1
		setFecK=12
		setFecN=15
		setBitrate=6667
		setGop=5
		wfbPower=59
		ROIqp="12,6,6,12"
		newProfile=2

	elif [ $2 -lt 1700 ];then

		setGI=long
		setMCS=2
		setFecK=12
		setFecN=15
		setBitrate=10000
		setGop=5
		wfbPower=58
		ROIqp="12,6,6,12"
		newProfile=3


	elif [ $2 -lt 2000 ];then
						
		setGI=long
		setMCS=3
		setFecK=12
		setFecN=15
		setBitrate=12500
		setGop=5
		wfbPower=56
		ROIqp="8,3,3,8"
		newProfile=4

	elif [ $2 -eq 2000 ];then

		setGI=short
		setMCS=3
		setFecK=12
		setFecN=15
		setBitrate=14000
		setGop=5
		wfbPower=56
		ROIqp="3,2,3,2"
		newProfile=5
	fi

#Decide if it is worth changing or not
profileDifference=$((newProfile - oldProfile))

#if in fallback mode, always hold there a couple of seconds
if [ $oldProfile -eq 0 ] && [ $secondsSinceLastChange -le 3 ] ; then
	exit 1
elif [ $profileDifference -eq 1 ] && [ $secondsSinceLastChange -le 2 ] ; then
	exit 1
elif [ $newProfile -eq $oldProfile ] ;then
	exit 1
fi


# Calculate driver power
setPower=$((wfbPower * 50))


#Decide what order to exectute commands
if [ $newProfile -gt $oldProfile ]; then
###########################################################################	
	# Lower power first
	if [ $prevSetPower -ne $setPower ]; then
		iw dev wlan0 set txpower fixed $setPower
		sleep 0.075
	fi
	
	# Set gopSize
	if [[ "$prevGop" != "$setGop" ]]; then
		curl localhost/api/v1/set?video0.gopSize=$setGop
		sleep 0.075
	fi
	
	# Raise MCS
	if [ $prevMCS -ne $setMCS ]; then
		wfb_tx_cmd 8000 set_radio -B 20 -G $setGI -S 1 -L 1 -M $setMCS
		sleep 0.075
	fi
	
	# Change FEC
	if [ $prevFecK -ne $setFecK ] || [ $prevFecN -ne $setFecN ]; then
		wfb_tx_cmd 8000 set_fec -k $setFecK -n $setFecN
		sleep 0.075
	fi	
	# Increase bit-rate
	if [ $prevBitrate -ne $setBitrate ]; then
		curl -s "http://localhost/api/v1/set?video0.bitrate=$setBitrate"
		
	fi
	
	# Change ROIqp
	if [[ "$prevROIqp" != "$ROIqp" ]]; then
		
		curl localhost/api/v1/set?fpv.roiQp=$ROIqp
		sleep 0.075
	fi
	
elif [ $newProfile -lt $oldProfile ]; then
###############################################################################	
	# Decrease bit-rate first
	if [ $prevBitrate -ne $setBitrate ]; then
		curl -s "http://localhost/api/v1/set?video0.bitrate=$setBitrate"
	fi
	
# Set gopSize
	if [[ "$prevGop" != "$setGop" ]]; then
		curl localhost/api/v1/set?video0.gopSize=$setGop
		sleep 0.075
	fi
	
	# Lower MCS
	if [ $prevMCS -ne $setMCS ]; then
		wfb_tx_cmd 8000 set_radio -B 20 -G $setGI -S 1 -L 1 -M $setMCS
		sleep 0.075
	fi

	#change FEC
	if [ $prevFecK -ne $setFecK ] || [ $prevFecN -ne $setFecN ]; then
		wfb_tx_cmd 8000 set_fec -k $setFecK -n $setFecN
		sleep 0.075
	fi
	
	# Increase power
	if [ $prevSetPower -ne $setPower ]; then
		iw dev wlan0 set txpower fixed $setPower
		sleep 0.075
	fi
	
	# Change ROIqp
	if [[ "$prevROIqp" != "$ROIqp" ]]; then
		curl localhost/api/v1/set?fpv.roiQp=$ROIqp
		sleep 0.075
	fi
fi
#############################################################################

# Display stats on msposd
echo "$2 $secondsSinceLastChange s $setBitrate M:$setMCS $setGI F:$setFecK/$setFecN P:$wfbPower G:$setGop&L30&F28 CPU:&C &Tc" >/tmp/MSPOSD.msg

#Update all profile variables in file
echo -e "vidRadioProfile=$newProfile\nprevGI=$setGI\nprevMCS=$setMCS\nprevFecK=$setFecK\nprevFecN=$setFecN\nprevBitrate=$setBitrate\nprevGop=$setGop\nprevSetPower=$setPower\nprevROIqp=$ROIqp\nprevTimeStamp=$newTimeStamp" >/etc/txprofile

exit 1