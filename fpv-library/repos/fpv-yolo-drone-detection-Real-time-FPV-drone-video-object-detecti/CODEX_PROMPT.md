# Codex Prompt for Building / Extending This Repository

Use this prompt in Codex or your coding agent.

---

## Role

You are a senior computer vision engineer helping me build a portfolio-ready GitHub repository named `fpv-yolo-drone-detection`.

## Goal

Build a complete Python project for real-time FPV/drone video object detection using YOLO + OpenCV, with benchmark outputs and Jetson deployment notes.

## Requirements

Create or improve the following:

1. `scripts/run_inference.py`
   - Accept video file, webcam index, RTSP URL, or OpenCV-compatible stream.
   - Load Ultralytics YOLO model from `.pt` or `.engine`.
   - Run frame-by-frame inference.
   - Draw detections and an FPS HUD.
   - Save annotated output video.
   - Save detection records to CSV.
   - Save run summary to JSON.
   - Support `--model`, `--source`, `--imgsz`, `--conf`, `--iou`, `--device`, `--half`, `--classes`, `--show`, `--output`, `--save-csv`, `--save-json`, and `--max-frames`.

2. `scripts/benchmark_fps.py`
   - Measure average FPS, mean latency, P50 latency, and P95 latency.
   - Include warmup frames.
   - Save benchmark JSON.

3. `scripts/export_model.py`
   - Export YOLO model to ONNX or TensorRT engine.
   - Include options for image size, FP16, INT8, device, dynamic shape, and simplify.

4. Documentation
   - README with setup, usage, benchmark commands, portfolio explanation.
   - Jetson deployment notes.
   - Drone-use explanation.
   - Ethics and safety note.
   - Troubleshooting guide.

5. Code quality
   - Clear argparse CLI.
   - Avoid hardcoded absolute paths.
   - Use functions/classes for maintainability.
   - Add basic tests for utility functions.
   - Keep code readable for recruiters and technical reviewers.

## Acceptance Criteria

The repository should run with:

```bash
pip install -r requirements.txt
python scripts/run_inference.py --source data/samples/sample_fpv.mp4 --model yolo11n.pt --output outputs/videos/sample_fpv_detected.mp4 --save-csv outputs/detections/sample.csv --save-json outputs/detections/summary.json
python scripts/benchmark_fps.py --source data/samples/sample_fpv.mp4 --model yolo11n.pt --frames 300 --output outputs/benchmarks/benchmark.json
python scripts/export_model.py --model yolo11n.pt --format onnx --imgsz 640
```

## Stretch Goals

After the base repo works, add:

- ByteTrack / BoT-SORT tracking mode.
- MAVLink telemetry overlay.
- ROS 2 node wrapper.
- Streamlit dashboard for benchmark results.
- Drone-specific fine-tuning notebook.
- Jetson-specific Dockerfile.
- GitHub Actions check.

## Important Constraints

- Keep the project safe and lawful.
- Do not implement weapon targeting or autonomous engagement behavior.
- Keep the repo focused on perception, inspection, search-and-rescue support, field robotics, and aerospace portfolio use.
