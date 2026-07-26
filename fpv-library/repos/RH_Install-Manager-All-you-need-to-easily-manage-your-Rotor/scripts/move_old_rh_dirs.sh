#!/bin/bash

if [ -d "/home/${1}/RotorHazard" ]; then
  # Control will enter here if $DIRECTORY exists.
  mv "/home/${1}/RotorHazard" "/home/${1}/RotorHazard_$(date +%Y%m%d%H%M)" || exit 1
fi

if [ -d "/home/${1}/RotorHazard-${2}" ]; then
  # Control will enter here if $DIRECTORY exists.
  mv "/home/${1}/RotorHazard-${2}" "/home/${1}/RotorHazard_${2}_$(date +%Y%m%d%H%M)" || exit 1
fi

  mv "/home/${1}/RotorHazard" "/home/${1}/RotorHazard_${2}_$(date +%Y%m%d%H%M)" > /dev/null 2>&1

  mv "/home/${1}/RotorHazard-*" "/home/${1}/RotorHazard_${2}_$(date +%Y%m%d%H%M)" > /dev/null 2>&1
