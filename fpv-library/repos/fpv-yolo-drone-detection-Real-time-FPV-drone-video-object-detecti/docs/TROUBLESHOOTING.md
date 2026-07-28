# Troubleshooting

## `Could not open video source`

Check file path, webcam index, RTSP credentials/IP address, and codec support.

Try:

```bash
python scripts/run_inference.py --source 0 --model yolo11n.pt --show
```

## PowerShell blocks virtual environment activation

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

## Low FPS

Try:

```bash
python scripts/run_inference.py --source data/samples/sample_fpv.mp4 --model yolo11n.pt --imgsz 512
```

Other improvements:

- Use a smaller model.
- Use TensorRT `.engine` on NVIDIA devices.
- Disable `--show` while benchmarking.
- Lower camera resolution.
- Use local video to isolate inference speed from network latency.

## RTSP lag

RTSP latency can come from network buffering, camera encoding, or OpenCV backend behavior. For serious work, test GStreamer pipelines and compare latency against direct display tools.

## CUDA not detected

Check PyTorch CUDA availability:

```bash
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')"
```

On Jetson, make sure your PyTorch build matches JetPack/CUDA.

## TensorRT export fails

- Export on the same Jetson device where you will run inference.
- Confirm JetPack, CUDA, TensorRT, Python, and Ultralytics compatibility.
- Try smaller model and fixed image size first.
- Try ONNX export first to isolate the issue.
