# NCShare cluster runbook (HADES P2.5 fine-tuning)

> Operational notes for running the YOLO11s fine-tune on the NCShare GPU cluster.
> Source of truth for the cluster facts; the design/plan own the *what*, this owns
> the *how to run it*. Verified 2026-06-24.

## Access (already working — no user setup needed)

Non-interactive key auth works. Run directly from the dev machine:

```bash
ssh ajain1@login.ncshare.org '<command>'      # ed25519 key, no 2FA, no bastion
rsync -rP <local> ajain1@login.ncshare.org:/work/ajain1/...
```

Verified: connects as `ajain1` on `login-01`; SLURM 24.11.5; `sbatch/srun/squeue/sinfo`
present. Login node has **no GPU** (GPUs are on compute nodes via SLURM).

If a session can't connect: the registered ed25519 key likely needs a passphrase-less
form or to be loaded into `ssh-agent` (a local-machine config fact, not a cluster one).
Public key is registered in the NCShare COmanage portal, not `~/.ssh/authorized_keys`.

## Account, partitions, hardware

- Account `ncssm`, QOS `normal`.
- GPU partitions: **`gpu`** (2-day walltime, **preemptible**), `interactive-gpu` (1 hr),
  `osg-gpu` (4-day). Request: `-p gpu --gres=gpu:h200:1`.
- H200 SXM, **141 GB VRAM**, 8/node × 4 nodes. Request **one** GPU for YOLO11s.
- **CUDA 12.8** on nodes → install **cu128** PyTorch wheels.
- `gpu` is **preemptible**: checkpoint often (Ultralytics saves per-epoch by default).

## Storage

| Path | Quota | Use |
|---|---|---|
| `/hpc/home/ajain1` | 50 GB | conda env + scripts only |
| `/work/ajain1` | 100 TB (shared) | datasets + checkpoints; **>75 days auto-purged** |

Work dir for this project: `/work/ajain1/hades/`. Pull checkpoints back to the Mac after
each run (75-day purge). No sensitive data on cluster storage (policy).

## Environment setup (Miniforge — run once)

No module system on this cluster (BYO-env). Internet works on login AND GPU nodes.

```bash
# On a login node:
cd ~
wget -O Miniforge3.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3.sh -b -p ~/miniforge3
~/miniforge3/bin/conda init bash
# new shell, then:
conda create -y -n hades-train python=3.12
conda activate hades-train
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
pip install ultralytics
```

## GPU smoke test (verify account can land an H200)

```bash
# /work/ajain1/hades/smoke.sbatch
#!/bin/bash
#SBATCH -J hades-smoke
#SBATCH -p gpu
#SBATCH --gres=gpu:h200:1
#SBATCH --mem=16G
#SBATCH -t 00:05:00
#SBATCH -o /work/ajain1/hades/smoke-%j.out
source ~/miniforge3/bin/activate hades-train
nvidia-smi
python -c "import torch; print('cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Submit + watch: `sbatch smoke.sbatch` · `squeue -u ajain1` · `cat smoke-<jobid>.out`.
A clean run confirms `normal` QOS may use `gpu` (otherwise the submit/queue will reject).

## Datasets (stage to /work/ajain1/hades/datasets)

**All three are Roboflow YOLO exports** (one parser; normalize to a single `person` class —
Task 2.5.1). **Stage inside an allocation, not on the shared login node** (ultraplan P1-2):
`srun -p interactive-gpu --account=ncssm --qos=normal -t 01:00:00 --cpus-per-task=4 --mem=16G --pty bash`.
Every download is integrity-checked (`curl --fail --location --retry 3` + sha256 →
`datasets/CHECKSUMS`) so a partial/expired pull fails loudly instead of training on a shrunk
HERIDAL and inflating held-out recall (ultraplan P0-3).

- **SARD** — `SARD.zip` (626 MB) `rsync`'d up from the Mac, then unzip. Roboflow YOLO,
  `nc:1 names:['human']`, 4041/1144/570 train/valid/test, already TILES_3x3 (640×640).
- **HERIDAL** — Roboflow: `curl --fail -L "$HERIDAL_ROBOFLOW_URL" -o heridal.zip` (the URL
  carries a SECRET `key=` token — keep it in an untracked `~/.hades-secrets`, never in the repo).
  **HERIDAL test split = the anchor evaluation domain** (held-out; leakage-guarded).
- **VisDrone** — Roboflow YOLO export (NOT Kaggle): `curl --fail -L "$VISDRONE_ROBOFLOW_URL" -o visdrone.zip`
  → `yolov11.zip` (~1.87 GB). Multi-class; `merge_datasets.py` maps `pedestrian`+`people` →
  person and DROPs every vehicle + ignore region (pretrain arm only).

Staging is scripted: `service/cluster/stage_datasets.sh` (fill the two Roboflow URLs in),
then `python -m hades.train.merge_datasets` builds TWO single-`person` trees —
`hades-finetune` {SARD+HERIDAL} and `visdrone-pretrain` {VisDrone} — each with `dataset.yaml`,
and runs the leakage/empty-split asserts. **HERIDAL is re-split by SCENE** (`scene_split.py`)
because the Roboflow export leaks scenes across train/test (see memory); the merge asserts
HERIDAL train∩test scene-codes == ∅ plus an exact content-hash backstop.

## Training run pattern

Develop + unit-test `service/src/hades/train/*` LOCALLY (fast TDD — 31 tests green). Then on
the cluster: rsync `service/` up, `pip install -e .` into `hades-train`. The committed sbatch
scripts (`service/cluster/`):
- `smoke.sbatch` — proves ncssm/normal lands an H200 + torch sees CUDA + `datasets_dir`
  pinned. Pre-flight the QOS cap: `sacctmgr show qos normal format=Name,MaxWall`.
- `resume_smoke.sbatch` — proves a `scontrol requeue` resumes the SAME per-arm dir at the
  next epoch (gate the real run on this; ultraplan P0-5).
- `train.sbatch` — per-arm (`--export=ALL,ARM=…,WEIGHTS=…`), `--requeue`, arm-scoped resume,
  `/work` config dirs, `-t 12:00:00`. The USR1 trap is intentionally CUT (no Ultralytics
  handler; per-epoch `last.pt` + `--requeue` already cover preemption).

Ablation (both arms, same `ablation.yaml`, only `weights` differs): Arm A `{HERIDAL+SARD}`,
Arm B `{VisDrone-pretrain → HERIDAL+SARD}`. Gate Arm B on a 30 s Arm-A sanity check
(recall non-degenerate, loss converged). Report HERIDAL-test recall per arm via `hades-eval`
center-distance (NOT Ultralytics `val()` mAP). rsync `best.pt + args.yaml + results.csv +
requirements.lock.txt` back per arm (75-day purge); the fairness diff = exactly the weights.

**Export env boundary (ultraplan):** export (Task 2.5.4) runs on the **Mac `bench` group
(numpy<2; coremltools 9 crashes on numpy 2), NOT the cluster** — pull `best.pt` back, run
`hades-export-coreml`/`hades-export-onnx` locally.
