# Real-Time FPV / Drone Video Object Detection with YOLO + OpenCV

A practical portfolio-ready computer vision project for **real-time FPV/drone video object detection** using Ultralytics YOLO, OpenCV, and deployment notes for NVIDIA Jetson devices.

This repository demonstrates:

- Real-time video inference from webcam, video file, RTSP/UDP FPV feed, or capture card
- YOLO-based object detection with annotated video output
- FPS and latency benchmarking
- Detection logging to CSV/JSON
- Sample detections for GitHub portfolio presentation
- Jetson deployment path using ONNX / TensorRT export
- Drone-use explanation for UAV, aerospace, inspection, and field robotics applications

---

## Repository Structure

```text
fpv-yolo-drone-detection/
├── README.md
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── Makefile
├── configs/default.yaml
├── data/samples/README.md
├── docs/
│   ├── DRONE_USE_CASE.md
│   ├── JETSON_DEPLOYMENT.md
│   ├── ETHICS_AND_SAFETY.md
│   └── TROUBLESHOOTING.md
├── outputs/
│   ├── detections/
│   ├── benchmarks/
│   └── videos/
├── scripts/
│   ├── run_inference.py
│   ├── benchmark_fps.py
│   ├── export_model.py
│   ├── capture_sample_frames.py
│   └── make_demo_clip.py
├── src/drone_yolo_fpv/
│   ├── __init__.py
│   ├── config.py
│   ├── drawing.py
│   ├── io.py
│   ├── metrics.py
│   └── yolo_engine.py
└── tests/test_metrics.py
```

---

## 1. Setup

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

## 2. Quick Start: Run YOLO on a Video File

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

## 3. Benchmark FPS

```bash
python scripts/benchmark_fps.py \
  --source data/samples/sample_fpv.mp4 \
  --model yolo11n.pt \
  --imgsz 640 \
  --frames 300 \
  --output outputs/benchmarks/benchmark_yolo11n.json
```

Example output:

```json
{
  "model": "yolo11n.pt",
  "source": "data/samples/sample_fpv.mp4",
  "frames_measured": 300,
  "average_fps": 42.7,
  "mean_latency_ms": 23.4,
  "p50_latency_ms": 21.8,
  "p95_latency_ms": 32.5
}
```

---

## 4. Export for Jetson / TensorRT

Export on the target Jetson device when possible:

```bash
python scripts/export_model.py \
  --model yolo11n.pt \
  --format engine \
  --imgsz 640 \
  --half \
  --device 0
```

Then run inference using the exported engine:

```bash
python scripts/run_inference.py \
  --source data/samples/sample_fpv.mp4 \
  --model yolo11n.engine \
  --imgsz 640 \
  --output outputs/videos/jetson_trt_detected.mp4
```

See `docs/JETSON_DEPLOYMENT.md` for Jetson-specific notes.

---

## 5. Create a Short Demo Video

```bash
python scripts/make_demo_clip.py \
  --input outputs/videos/sample_fpv_detected.mp4 \
  --output outputs/videos/demo_15s.mp4 \
  --start-sec 5 \
  --duration-sec 15
```

Recommended GitHub README demo assets:

```text
outputs/videos/demo_15s.mp4
outputs/detections/sample_fpv_detections.csv
outputs/benchmarks/benchmark_yolo11n.json
outputs/detections/sample_frame_001.jpg
```

---

## 6. Suggested Portfolio Claim

> Built a real-time FPV/drone video object detection pipeline using YOLO and OpenCV, including annotated video output, detection logging, FPS benchmarking, and Jetson deployment notes for edge inference using ONNX/TensorRT.

---

## 7. Responsible Use

This project is for lawful research, education, inspection, robotics, and aerospace portfolio use. Do not use it to identify, track, or target private individuals without consent or legal authority. Follow local aviation, privacy, and safety regulations.
