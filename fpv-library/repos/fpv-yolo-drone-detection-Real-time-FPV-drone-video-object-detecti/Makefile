.PHONY: install dev lint format test infer benchmark clean

install:
	pip install -r requirements.txt

dev:
	pip install -r requirements-dev.txt

lint:
	ruff check src scripts tests

format:
	black src scripts tests
	ruff check --fix src scripts tests

test:
	pytest -q

infer:
	python scripts/run_inference.py --source data/samples/sample_fpv.mp4 --model yolo11n.pt --output outputs/videos/sample_fpv_detected.mp4

benchmark:
	python scripts/benchmark_fps.py --source data/samples/sample_fpv.mp4 --model yolo11n.pt --frames 300 --output outputs/benchmarks/benchmark_yolo11n.json

clean:
	rm -rf outputs/videos/*.mp4 outputs/detections/*.csv outputs/detections/*.json outputs/benchmarks/*.json
