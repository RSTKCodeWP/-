#!/bin/bash
# HADES P2.5 — preemption/resume smoke (ultraplan P0-5). Proves a SLURM requeue resumes the
# SAME per-arm run dir at the next epoch instead of silently restarting from epoch 0 (which
# would waste GPU days on the real 12h run). Uses a tiny 3-epoch train on the real merged
# data. Drive with:
#   JID=$(sbatch --parsable resume_smoke.sbatch)
#   # wait until the log shows 'Epoch 1/3' completed, then:
#   scontrol requeue $JID
#   # then assert the -%j.out shows 'Resuming training' and NO 'smoke_resume2' dir appears.
#SBATCH -J hades-resume-smoke
#SBATCH -p gpu
#SBATCH --account=ncssm
#SBATCH --qos=normal
#SBATCH --gres=gpu:h200:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH -t 00:20:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH -o /work/ajain1/hades/runs/resume-smoke-%j.out

set -euo pipefail
source ~/miniforge3/etc/profile.d/conda.sh
conda activate hades-train
export YOLO_CONFIG_DIR=/work/ajain1/hades/ultra-cfg
export MPLCONFIGDIR=/work/ajain1/hades/mpl-cfg
export TORCH_HOME=/work/ajain1/hades/torch-home
export CUBLAS_WORKSPACE_CONFIG=:4096:8

echo "=== resume-smoke job=$SLURM_JOB_ID restarts=${SLURM_RESTART_COUNT:-0} $(date -u) ==="
# 3-epoch config so a requeue after epoch 1 visibly resumes at epoch 2.
SMOKE_CONFIG=/work/ajain1/hades/configs/resume_smoke.yaml
python - <<'PY'
import yaml, copy
base = yaml.safe_load(open("/work/ajain1/hades/configs/ablation.yaml"))
base = copy.deepcopy(base)
base.update(epochs=3, imgsz=640, batch=16)
yaml.safe_dump(base, open("/work/ajain1/hades/configs/resume_smoke.yaml", "w"), sort_keys=False)
print("wrote resume_smoke.yaml (3 epochs)")
PY

srun python -m hades.train.train --arm smoke_resume --config "$SMOKE_CONFIG" --project /work/ajain1/hades/runs
echo "=== resume-smoke DONE $(date -u) ==="
