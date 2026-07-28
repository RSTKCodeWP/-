# Jetson Deployment Notes

This document gives a practical deployment path for NVIDIA Jetson Nano / Xavier / Orin class devices.

## Recommended Jetson Strategy

1. Start with a small model such as `yolo11n.pt` or `yolo11s.pt`.
2. Test normal PyTorch inference first.
3. Export on the Jetson target device to TensorRT `.engine`.
4. Benchmark the `.engine` file using the same video source and image size.
5. Reduce `imgsz`, increase confidence threshold, or use a smaller model if latency is too high.

## Environment

For Jetson, dependency compatibility depends heavily on JetPack, CUDA, TensorRT, and Python versions. Prefer an official or well-maintained Jetson container when possible.

Typical approach:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install ultralytics opencv-python numpy pyyaml tqdm pandas
```

If `opencv-python` gives problems on Jetson, use the OpenCV build already installed with JetPack or install a Jetson-compatible OpenCV package.

## Export to TensorRT

Export on the target Jetson device:

```bash
python scripts/export_model.py \
  --model yolo11n.pt \
  --format engine \
  --imgsz 640 \
  --half \
  --device 0
```

Run inference:

```bash
python scripts/run_inference.py \
  --source data/samples/sample_fpv.mp4 \
  --model yolo11n.engine \
  --imgsz 640 \
  --output outputs/videos/jetson_trt_detected.mp4 \
  --save-json outputs/benchmarks/jetson_trt_run.json
```

## Jetson Performance Checklist

- Use TensorRT `.engine` for production-like benchmark.
- Use FP16 (`--half`) if supported.
- Keep input resolution realistic: `640` is a good starting point; `416` or `512` may be needed for weaker devices.
- Use `yolo11n` first, then move to `yolo11s` only if FPS is acceptable.
- Disable GUI display during benchmarking because `cv2.imshow()` can reduce measured FPS.
- Use a local video file for repeatable benchmarks, then test RTSP/UDP feed separately.
- Record CPU/GPU temperature and power mode during serious benchmarking.

## Jetson Power Mode

On many Jetson devices, performance depends on power mode and clocks.

```bash
sudo nvpmodel -q
sudo jetson_clocks
```

Use these responsibly because higher clocks increase heat and power consumption.

## Camera / FPV Input Options

USB webcam or HDMI-to-USB capture card:

```bash
python scripts/run_inference.py --source 0 --model yolo11n.engine --show
```

RTSP stream from IP camera / digital FPV receiver:

```bash
python scripts/run_inference.py --source "rtsp://user:pass@192.168.1.10:554/stream1" --model yolo11n.engine
```

GStreamer pipeline:

OpenCV can accept GStreamer strings if OpenCV was built with GStreamer support. This is platform-specific. Test your pipeline with `gst-launch-1.0` first before passing it into OpenCV.

## What to Put in Your GitHub Results Section

| Device | Model | Format | Input Size | Source | Avg FPS | Mean Latency | Notes |
|---|---:|---:|---:|---|---:|---:|---|
| Laptop RTX GPU | yolo11n | PyTorch | 640 | MP4 | TBD | TBD | Baseline |
| Jetson Orin Nano | yolo11n | TensorRT FP16 | 640 | MP4 | TBD | TBD | Edge inference |
| Jetson Orin Nano | yolo11s | TensorRT FP16 | 640 | MP4 | TBD | TBD | Accuracy/speed comparison |

For drone use, FPS alone is not enough. Report average FPS, P50/P95 latency, input resolution, confidence threshold, source type, and inference backend.
