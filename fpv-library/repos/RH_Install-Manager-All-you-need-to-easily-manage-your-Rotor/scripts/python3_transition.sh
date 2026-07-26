#!/bin/bash

### python 3 transition handling ###

PYTHON3_CONVERSION_FLAG_FILE=/home/"${1}"/.rhim_markers/python3_support_was_added

if ! test -f "$PYTHON3_CONVERSION_FLAG_FILE"; then

  SERVICE_FILE=/lib/systemd/system/rotorhazard.service
  old_python_service_statement="ExecStart=/usr/bin/python server.py"

  if test -f "$SERVICE_FILE"; then

    if grep -Fxq "$old_python_service_statement" "$SERVICE_FILE"; then
      printf "\n"
      echo "old python based RotorHazard autostart service found"
      sudo sed -i 's/python/python3/g' "$SERVICE_FILE"
      echo "changed to python3 based service"
    else
      echo "RotorHazard autostart service is up to date"
    fi
  else
    echo "no RotorHazard autostart service found - no changes"
  fi

  printf "\n"

  if grep -Fq "python server.py" "/home/"${1}"/.bashrc"; then
    echo "old python based server-start alias found"
    sed -i 's/python server.py/python3 server.py/g' ~/.bashrc
    echo "'rh' alias changed to python3 version"
  fi

  ### sensors transition to python3 handling ###

  INA_SENSOR_FILES=/home/"${1}"/pi_ina219

  if test -d "$INA_SENSOR_FILES"; then
    printf "\n\n Converting INA sensor library to python3 version "
    cd /home/"${1}" || exit
    sudo rm -r "$INA_SENSOR_FILES" || exit
    sudo git clone https://github.com/chrisb2/pi_ina219.git
    cd /home/"${1}"/pi_ina219 || exit
    printf "\n\n  INA sensor library will be updated to python3 \n\n"
    sudo python3 setup.py install
    echo "\n done"

  fi

  BME_SENSOR_FILES=/home/"${1}"/bme280

  if test -d "$BME_SENSOR_FILES"; then
    printf "\n\n Converting existing BME sensor library to python3 version "
    cd /home/"${1}" || exit
    sudo rm -r "$BME_SENSOR_FILES" || exit
    sudo git clone https://github.com/rm-hull/bme280.git
    cd /home/"${1}"/bme280 || exit
    printf "\n\n  BME sensor library will be updated to python3 \n\n"
    sudo python3 setup.py install
    echo "\n done"
  fi

  touch "$PYTHON3_CONVERSION_FLAG_FILE"

fi

# added because of the broken Adafruit_GPIO compatibility on Raspbian 11 Bullseye and newer Pis

ADAFRUIT_FILE=/usr/local/lib/python3*/dist-packages/Adafruit_GPIO/Platform.py

if test -d "$ADAFRUIT_FILE"; then
  (sudo sed -i 's/UNKNOWN          = 0/UNKNOWN          = 1/' "$ADAFRUIT_FILE" &&
    printf "\n $green Adafruit_GPIO library is now compatible $endc \n\n") ||
    (printf "$endc \nAdafruit_GPIO compatibility file not found - skipping \n\n $endc" && sleep 2)
fi
