#!/bin/bash
# HADES P2.5 — fine-tune ONE ablation arm on an H200. Preemption-safe.
#
# Submit per arm, overriding the run name + (for Arm B) the pretrain weights:
#   sbatch -J hades-train-armA --export=ALL,ARM=armA_heridal_sard,WEIGHTS=yolo11s.pt train.sbatch
#   sbatch -J hades-train-armB --export=ALL,ARM=armB_visdrone_ft,WEIGHTS=/work/.../runs/visdrone_pretrain/weights/best.pt train.sbatch
#
# Preemption survival (ultraplan): --requeue is non-negotiable on the preemptible `gpu`
# partition (without it a preempted job never comes back). Each arm gets its OWN run dir
# (ARM), so a requeue resumes THIS arm's last.pt (resolved in hades.train.train.resume_arg)
# and never the other arm's. Per-epoch last.pt + exist_ok=True land the requeue in the same
# dir at the next epoch. The USR1 signal-trap is deliberately omitted — Ultralytics has no
# USR1 handler and writes last.pt only at epoch boundaries, so a trap can't flush an
# in-flight epoch; per-epoch checkpointing already bounds the loss to one repeated epoch.
#SBATCH -p gpu
#SBATCH --account=ncssm
#SBATCH --qos=normal
#SBATCH --gres=gpu:h200:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH -t 12:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH -o /work/ajain1/hades/runs/%x-%j.out

set -euo pipefail
source ~/miniforge3/etc/profile.d/conda.sh
conda activate hades-train

# Keep all Ultralytics/torch/matplotlib state on /work, not the 50 GB HOME quota, and make
# the resume last.pt path deterministic + rsync-covered.
export YOLO_CONFIG_DIR=/work/ajain1/hades/ultra-cfg
export MPLCONFIGDIR=/work/ajain1/hades/mpl-cfg
export TORCH_HOME=/work/ajain1/hades/torch-home
# Required for torch deterministic CUDA algorithms (deterministic=True raises without it).
export CUBLAS_WORKSPACE_CONFIG=:4096:8

ARM="${ARM:?set ARM to the per-arm run name}"
WEIGHTS="${WEIGHTS:-yolo11s.pt}"
CONFIG="${CONFIG:-/work/ajain1/hades/configs/ablation.yaml}"

echo "=== arm=$ARM weights=$WEIGHTS data=${DATA:-<ablation>} job=$SLURM_JOB_ID $(date -u) ==="
# The weights (and optional data) override is written into a per-arm config copy so
# args.yaml records it (the fairness diff reads args.yaml). DATA override is ONLY used by
# the VisDrone-pretrain run; both ablation ARMS leave it unset -> identical hades-finetune.
PERARM_CONFIG="/work/ajain1/hades/configs/${ARM}.yaml"
DATA_OVERRIDE="${DATA:-}"
python - "$CONFIG" "$WEIGHTS" "$PERARM_CONFIG" "$DATA_OVERRIDE" <<'PY'
import sys, yaml
cfg = yaml.safe_load(open(sys.argv[1]))
cfg["weights"] = sys.argv[2]
if sys.argv[4]:
    cfg["data"] = sys.argv[4]
yaml.safe_dump(cfg, open(sys.argv[3], "w"), sort_keys=False)
print("wrote per-arm config", sys.argv[3], "weights=", cfg["weights"], "data=", cfg["data"])
PY

srun python -m hades.train.train --arm "$ARM" --config "$PERARM_CONFIG" --project /work/ajain1/hades/runs
echo "=== arm=$ARM DONE $(date -u) ==="
