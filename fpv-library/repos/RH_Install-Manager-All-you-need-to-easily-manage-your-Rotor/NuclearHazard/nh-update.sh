#!/bin/bash

export PYTHONPATH=/home/"$USER"/RH_Install-Manager:$PYTHONPATH

export RH_VERSION="$1"
python3 ~/RH_Install-Manager/NuclearHazard/nh-quick-update.py
