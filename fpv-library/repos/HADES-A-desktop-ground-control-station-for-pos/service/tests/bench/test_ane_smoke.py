"""ANE smoke tests — MANUAL, run on the target Mac (MacBook Air M4 floor).

Marked `@pytest.mark.ane` so CI (CPU-only) skips them. They require the `bench`
dependency-group installed and download stock `yolo11s` weights on first run:

    uv sync --group bench
    uv run pytest -m ane tests/bench/test_ane_smoke.py

These prove the *real* path works end to end (export -> load -> infer -> summarize)
on one resolution. The full sweep + the recorded numbers come from the CLI:

    uv run --group bench hades-export-coreml --res 640
    uv run --group bench hades-bench-latency --res 640 --frames 60
"""

import pytest

pytestmark = pytest.mark.ane


def test_export_then_benchmark_640(tmp_path):
    from hades.bench.bench_latency import benchmark_resolution
    from hades.bench.export_coreml import artifact_path, export_one

    dest = export_one(640, tmp_path)
    assert dest == artifact_path(tmp_path, 640)
    assert dest.exists()

    # Short window — this is a correctness smoke test, not the recorded measurement.
    decision = benchmark_resolution(640, tmp_path, warmup_frames=3, measure_frames=10)
    assert decision.resolution == 640
    assert len(decision.latencies_ms) == 10
    assert decision.median_ms > 0
    # We do NOT assert meets_gate here: the recorded pass/fail decision is the
    # sustained CLI run, not this 10-frame smoke test.
