#!/bin/bash
# HADES P2.5 — finish env + stage 3 datasets + merge to one person class, ALL in one
# allocation (numpy can't import on the login node — KVM CPU; see memory). CPU-only work,
# so it runs on the `common` partition (no GPU needed for staging/merge).
#SBATCH -J hades-stage
#SBATCH -p common
#SBATCH --account=ncssm
#SBATCH --qos=normal
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH -t 04:00:00
#SBATCH -o /work/ajain1/hades/runs/stage-%j.out

set -euo pipefail
source ~/miniforge3/etc/profile.d/conda.sh
conda activate hades-train
export YOLO_CONFIG_DIR=/work/ajain1/hades/ultra-cfg
export MPLCONFIGDIR=/work/ajain1/hades/mpl-cfg

echo "=== node $(hostname) $(date -u) ==="
python -c "import numpy, ultralytics; print('numpy', numpy.__version__, 'ultralytics', ultralytics.__version__)"

echo "=== [A] finish env: editable install + datasets_dir pin + freeze ==="
pip install -e /work/ajain1/hades/service --quiet --no-deps
yolo settings datasets_dir=/work/ajain1/hades/datasets 2>&1 | tail -2 || true
python -c "from ultralytics.utils import SETTINGS; d=SETTINGS['datasets_dir']; print('datasets_dir =', d); assert d=='/work/ajain1/hades/datasets', d"
pip freeze > /work/ajain1/hades/requirements.lock.txt
echo "lock: $(wc -l < /work/ajain1/hades/requirements.lock.txt) lines"

echo "=== [B] stage datasets (integrity-checked) ==="
bash /work/ajain1/hades/service/cluster/stage_datasets.sh

echo "=== [C] merge to single-person tree + leakage/empty-split asserts ==="
cd /work/ajain1/hades/service
python -m hades.train.merge_datasets \
  --datasets-root /work/ajain1/hades/datasets \
  --out /work/ajain1/hades/datasets/hades-finetune

echo "=== STAGE+MERGE DONE $(date -u) ==="
