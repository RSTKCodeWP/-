#!/bin/bash
# HADES P2.5 — GPU smoke test. Proves the ncssm/normal association can actually land an
# H200 on the preemptible `gpu` partition (the one UNCONFIRMED cluster fact), that torch
# sees CUDA, and that Ultralytics' datasets_dir is pinned to /work. ~2 min on an H200.
#SBATCH -J hades-smoke
#SBATCH -p gpu
#SBATCH --account=ncssm
#SBATCH --qos=normal
#SBATCH --gres=gpu:h200:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH -t 00:05:00
#SBATCH -o /work/ajain1/hades/runs/smoke-%j.out

set -euo pipefail
source ~/miniforge3/etc/profile.d/conda.sh
conda activate hades-train
export YOLO_CONFIG_DIR=/work/ajain1/hades/ultra-cfg

echo "=== node + GPU ==="
hostname
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

echo "=== torch sees CUDA ==="
python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0))"

echo "=== Ultralytics datasets_dir pinned to /work ==="
python -c "from ultralytics.utils import SETTINGS; d=SETTINGS['datasets_dir']; print('datasets_dir =', d); assert d == '/work/ajain1/hades/datasets', f'datasets_dir not pinned: {d}'"

echo "=== SMOKE OK ==="
