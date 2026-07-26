#!/bin/bash

get_host_info() {
  if uname -a | grep rpi >>/dev/null 2>&1; then
    return 1
  else
    return 0
  fi
}

get_host_info
