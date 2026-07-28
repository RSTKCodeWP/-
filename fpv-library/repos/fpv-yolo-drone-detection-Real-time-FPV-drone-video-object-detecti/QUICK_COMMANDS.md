# Quick Commands

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run Inference

```bash
python scripts/run_inference.py --source data/samples/sample_fpv.mp4 --model yolo11n.pt --output outputs/videos/sample_fpv_detected.mp4 --save-csv outputs/detections/sample.csv --save-json outputs/detections/summary.json
```

## Webcam / Capture Card

```bash
python scripts/run_inference.py --source 0 --model yolo11n.pt --show
```

## Benchmark

```bash
python scripts/benchmark_fps.py --source data/samples/sample_fpv.mp4 --model yolo11n.pt --frames 300 --output outputs/benchmarks/benchmark.json
```

## Export to ONNX

```bash
python scripts/export_model.py --model yolo11n.pt --format onnx --imgsz 640
```

## Export to TensorRT on Jetson

```bash
python scripts/export_model.py --model yolo11n.pt --format engine --imgsz 640 --half --device 0
```
