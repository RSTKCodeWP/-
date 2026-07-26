#!/bin/bash
# HADES P2.5 — stage the three Roboflow YOLO datasets to /work and merge to one person class.
# RUN INSIDE AN ALLOCATION, not the login node (ultraplan P1-2):
#   srun -p interactive-gpu --account=ncssm --qos=normal -t 01:00:00 --cpus-per-task=4 --mem=16G --pty bash
#   bash /work/ajain1/hades/stage_datasets.sh
# Idempotent: skips a dataset whose marker exists. Integrity-checked curls (ultraplan P0-3).
#
# Roboflow download keys are SECRETS — they are NOT hard-coded here (a committed key leaks into
# git history and is reusable by anyone with repo access). Supply them via the environment, e.g.
#   export HERIDAL_ROBOFLOW_URL='https://app.roboflow.com/ds/wpGNCCuBCT?key=YOUR_KEY'
#   export VISDRONE_ROBOFLOW_URL='https://app.roboflow.com/ds/YzvUGtXuNU?key=YOUR_KEY'
# (put these in an untracked ~/.hades-secrets and `source` it), then run this script.
set -euo pipefail

require_env () {  # name
  local var="$1"
  if [ -z "${!var:-}" ]; then
    echo "ERROR: \$$var is unset. Roboflow download keys are secrets and must come from the" >&2
    echo "       environment, not this script. See the header comment for how to set them." >&2
    exit 1
  fi
}
require_env HERIDAL_ROBOFLOW_URL
require_env VISDRONE_ROBOFLOW_URL

DS=/work/ajain1/hades/datasets
mkdir -p "$DS"
cd "$DS"
CHECKSUMS="$DS/CHECKSUMS"
: > "$CHECKSUMS.new"

source ~/miniforge3/etc/profile.d/conda.sh
conda activate hades-train

fetch_zip () {  # name url
  local name="$1" url="$2"
  # Idempotency keys on the EXTRACTED marker (a data.yaml under the dir), not just the dir —
  # a failed run can leave a partial dir that must be re-extracted.
  if find "$DS/$name" -name data.yaml 2>/dev/null | grep -q .; then
    echo "[$name] already extracted (data.yaml present), skipping"; return
  fi
  if [ ! -f "$name.zip" ]; then
    echo "[$name] downloading..."
    curl --fail --location --retry 3 "$url" -o "$name.zip"
  else
    echo "[$name] reusing already-downloaded $name.zip"
  fi
  sha256sum "$name.zip" | tee -a "$CHECKSUMS.new"
  echo "[$name] unzipping..."
  mkdir -p "$name"
  # -o = overwrite without prompting (a batch job has no stdin); </dev/null belt-and-suspenders.
  unzip -q -o "$name.zip" -d "$name" </dev/null
  rm -f "$name.zip"
  echo "[$name] data.yaml:"; find "$name" -name data.yaml -exec cat {} \; | sed 's/^/    /'
}

# SARD.zip is rsync'd up separately (it's local on the Mac); just unzip if present.
if [ -f "$DS/SARD.zip" ] && ! find "$DS/sard" -name data.yaml 2>/dev/null | grep -q .; then
  echo "[sard] unzipping rsync'd SARD.zip"
  mkdir -p sard && unzip -q -o SARD.zip -d sard </dev/null && rm -f SARD.zip
  sha256sum "$DS/sard"/*/data.yaml 2>/dev/null || true
fi

fetch_zip heridal  "$HERIDAL_ROBOFLOW_URL"
fetch_zip visdrone "$VISDRONE_ROBOFLOW_URL"

mv -f "$CHECKSUMS.new" "$CHECKSUMS" 2>/dev/null || true
echo "=== staged datasets ==="
ls -la "$DS"
echo "=== per-dataset data.yaml class names (build the merge map from these) ==="
find "$DS" -name data.yaml -maxdepth 3 | while read -r y; do echo "--- $y ---"; grep -E "^(nc|names)" "$y"; done
echo "=== STAGE DONE — next: run merge_datasets.py to build the single-person tree ==="
