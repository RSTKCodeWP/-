#!/bin/bash

if [ -f "/etc/os-release" ]; then
  version=$(grep -oP 'VERSION_ID="\K[^"]+' /etc/os-release)
  echo "$version"
else
  echo "OS release file not found."
fi
