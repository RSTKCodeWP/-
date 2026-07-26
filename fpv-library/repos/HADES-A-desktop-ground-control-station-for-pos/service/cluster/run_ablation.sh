#!/bin/bash
# HADES P2.5 — drive the full ablation on the cluster. Run from a login shell (it only
# submits sbatch + polls squeue; the heavy work is in the GPU jobs). Three training runs:
#   1. visdrone_pretrain : YOLO(yolo11s.pt).train(visdrone-pretrain)         -> Arm B's prior
#   2. armA_heridal_sard : YOLO(yolo11s.pt).train(hades-finetune)            -> Arm A
#   3. armB_visdrone_ft  : YOLO(visdrone_pretrain/best.pt).train(hades-finetune) -> Arm B
# Arm B's finetune is GATED on Arm A being healthy (check_arm.py) so a pipeline bug doesn't
# burn a second 12 h slot. Each run is preemption-safe (--requeue, arm-scoped resume).
set -euo pipefail
RUNS=/work/ajain1/hades/runs
SB=/work/ajain1/hades/service/cluster/train.sbatch
FT=/work/ajain1/hades/datasets/hades-finetune/dataset.yaml

submit () {  # arm weights [data_override]
  local arm="$1" weights="$2" data="${3:-}"
  sbatch --parsable -J "hades-$arm" \
    --export=ALL,ARM="$arm",WEIGHTS="$weights",DATA="$data",CONFIG=/work/ajain1/hades/configs/ablation.yaml \
    "$SB"
}

wait_done () {  # jobid label
  local jid="$1" label="$2"
  echo "[$label] job $jid submitted; polling..."
  while squeue -j "$jid" -h 2>/dev/null | grep -q .; do sleep 60; done
  local state; state=$(sacct -j "$jid" --format=State -n 2>/dev/null | head -1 | tr -d '[:space:]')
  echo "[$label] job $jid finished: $state"
  [ "$state" = "COMPLETED" ]
}

echo "=== 1/3 VisDrone pretrain ==="
JID=$(submit visdrone_pretrain yolo11s.pt /work/ajain1/hades/datasets/visdrone-pretrain/dataset.yaml)
wait_done "$JID" "visdrone_pretrain" || { echo "pretrain failed"; exit 1; }

echo "=== 2/3 Arm A {HERIDAL+SARD} ==="
JIDA=$(submit armA_heridal_sard yolo11s.pt)
wait_done "$JIDA" "armA" || { echo "Arm A failed"; exit 1; }

echo "=== Arm-A sanity gate (before spending Arm B's slot) ==="
source ~/miniforge3/etc/profile.d/conda.sh; conda activate hades-train
if ! python /work/ajain1/hades/service/cluster/check_arm.py --run-dir "$RUNS/armA_heridal_sard"; then
  echo "Arm A unhealthy — NOT submitting Arm B. Investigate first."; exit 1
fi

echo "=== 3/3 Arm B {VisDrone-pretrain -> HERIDAL+SARD} ==="
JIDB=$(submit armB_visdrone_ft "$RUNS/visdrone_pretrain/weights/best.pt")
wait_done "$JIDB" "armB" || { echo "Arm B failed"; exit 1; }

echo "=== ABLATION COMPLETE — pull weights back + eval both arms ==="
