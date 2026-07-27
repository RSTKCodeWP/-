#!/usr/bin/env bash
set -euo pipefail

url="https://download.walksnail.app/75f68e37-e93a-4998-92db-62b52b9ef4e6/Ascent_G_Gnd_16_5_7.img?download"
output="Ascent_G_Gnd_16_5_7.img"

curl --fail --location --retry 3 --output "$output" "$url"
