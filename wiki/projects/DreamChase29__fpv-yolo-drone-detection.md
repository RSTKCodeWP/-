# Real-Time FPV / Drone Video Object Detection with YOLO + OpenCV

> Картка виставки. Зал: [Зір і алгоритми](../halls/ai.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [DreamChase29/fpv-yolo-drone-detection](https://github.com/DreamChase29/fpv-yolo-drone-detection) |
| Локальна тека | `fpv-library/repos/fpv-yolo-drone-detection-Real-time-FPV-drone-video-object-detecti` |
| У бібліотеці | keep |
| Категорії каталогу | `ai` |
| Зірки (каталог) | 0 |
| Оновлено upstream | 2026-05-16 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

A practical portfolio-ready computer vision project for **real-time FPV/drone video object detection** using Ultralytics YOLO, OpenCV, and deployment notes for NVIDIA Jetson devices.

This repository demonstrates:

_З README.md, без переказу._

## Для чого

Real-time FPV/drone video object detection using YOLO, OpenCV, and Jetson deployment notes.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Real-time FPV/drone video object detection using YOLO, OpenCV, and Jetson deployment notes.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `CODEX_PROMPT.md`
- `configs/`
- `data/`
- `docs/`
- `Makefile`
- `outputs/`
- `pyproject.toml`
- `QUICK_COMMANDS.md`
- `README.md`
- `requirements-dev.txt`
- `requirements.txt`
- `scripts/`
- `src/`
- `tests/`

Типи файлів за вибіркою (30 файлів, глибина до 3): Python (12), Markdown (8), (без суфікса) (5), .txt (2), TOML (1), JSON (1).


## Що треба

- Маніфести збірки: Python (requirements.txt), Python (pyproject.toml), Make.
- requirements.txt: `ultralytics>=8.3.0`, `opencv-python>=4.9.0`, `numpy>=1.24.0`, `PyYAML>=6.0.1`, `tqdm>=4.66.0`, `pandas>=2.0.0`.
- pyproject name: `fpv-yolo-drone-detection`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### 1. Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
pip install --upgrade pip
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

---
### 2. Quick Start: Run YOLO on a Video File

Put a sample drone/FPV video in:

```text
data/samples/sample_fpv.mp4
```

Then run:

```bash
python scripts/run_inference.py \
  --source data/samples/sample_fpv.mp4 \
  --model yolo11n.pt \
  --conf 0.35 \
  --imgsz 640 \
  --output outputs/videos/sample_fpv_detected.mp4 \
  --save-csv outputs/detections/sample_fpv_detections.csv \
  --save-json outputs/detections/sample_fpv_summary.json
```

For webcam or USB capture card:

```bash
python scripts/run_inference.py --source 0 --model yolo11n.pt --show
```

For RTSP FPV stream:

```bash
python scripts/run_inference.py \
  --source "rtsp://username:password@192.168.1.10:554/stream1" \
  --model yolo11n.pt \
  --show
```

---

## Супутні документи в теці

- [`docs/DRONE_USE_CASE.md`](../../fpv-library/repos/fpv-yolo-drone-detection-Real-time-FPV-drone-video-object-detecti/docs/DRONE_USE_CASE.md)
- [`docs/ETHICS_AND_SAFETY.md`](../../fpv-library/repos/fpv-yolo-drone-detection-Real-time-FPV-drone-video-object-detecti/docs/ETHICS_AND_SAFETY.md)
- [`docs/JETSON_DEPLOYMENT.md`](../../fpv-library/repos/fpv-yolo-drone-detection-Real-time-FPV-drone-video-object-detecti/docs/JETSON_DEPLOYMENT.md)
- [`docs/TROUBLESHOOTING.md`](../../fpv-library/repos/fpv-yolo-drone-detection-Real-time-FPV-drone-video-object-detecti/docs/TROUBLESHOOTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/fpv-yolo-drone-detection-Real-time-FPV-drone-video-object-detecti/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/DreamChase29__fpv-yolo-drone-detection.md`.
