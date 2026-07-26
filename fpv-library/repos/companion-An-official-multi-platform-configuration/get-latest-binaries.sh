#!/usr/bin/env bash

MSP_OSD_URL="https://github.com/OpenIPC/msposd/releases/download/latest/msposd_star6e"
BIN_FOLDER="OpenIPC_Config/binaries"
FONTS_FOLDER="${BIN_FOLDER}/fonts"

echo "Downloading latest binaries..."
 
curl -L "$MSP_OSD_URL" -o $BIN_FOLDER/msposd
chmod +x OpenIPC/binaries/msposd

## Fonts 

## INav

echo "Downloading INav font..."

curl -k -L -o $FONTS_FOLDER/inav/font.png https://raw.githubusercontent.com/openipc/msposd/main/fonts/font_inav.png
curl -k -L -o $FONTS_FOLDER/inav/font_hd.png https://raw.githubusercontent.com/openipc/msposd/main/fonts/font_inav_hd.png

## Betaflight

echo "Downloading Betaflight font..."

curl -k -L -o $FONTS_FOLDER/bf/font.png https://raw.githubusercontent.com/openipc/msposd/main/fonts/font_btfl.png
curl -k -L -o $FONTS_FOLDER/bf/font_hd.png https://raw.githubusercontent.com/openipc/msposd/main/fonts/font_btfl_hd.png
