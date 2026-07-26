#!/bin/bash

white=""
green="\033[92m"
red="\033[91m"
yellow="\033[93m"
endc="\033[0m"

script() {
  printf "
$white

RotorHazard Install-Manager software will be downloaded automatically


$endc "
sleep 2

  (sudo apt update && sudo apt install curl wget zip unzip -y) || echo "no wget or curl download target"
  cd ~ || return 1
  mv RH_Install-Manager*/ RH_Install-Manager.old/ > /dev/null 2>&1
  mv temprhim.zip temprhim.zip.old > /dev/null 2>&1
  wget https://codeload.github.com/RotorHazard/Install-Manager/zip/stable -O temprhim.zip || return 1
  unzip temprhim.zip || return 1
  rm temprhim.zip || return 1
  mv RH_Install-Manager-* RH_Install-Manager || return 1

  printf "
-----------------------------------------------------------------
$green
Program downloaded successfully. To open the Installer now type:$endc
cd ~/RH_Install-Manager
./rhim.sh
$yellow

For the NuclearHazard quick install, enter:$endc
cd ~/RH_Install-Manager/NuclearHazard
./nh-install.sh 1 $yellow
! perform ONLY if you use NuclearHazard timer !
$endc
"

}

script || printf "
$red
errors encountered - try manual installation -> more info on GitHub
$endc

"