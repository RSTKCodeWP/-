"""Bench-runner tests (sim backend): the orchestrator + hardware seam work before any hardware."""
from __future__ import annotations

import math

import numpy as np

from fpv.gimbal.bench_runner import BenchRunner, SimBenchIO
from fpv.gimbal.controller import GimbalController
from fpv.gimbal.datalog import characterize


def test_static_capture_gives_clean_gyro_stats():
    io = SimBenchIO(target_fn=lambda t: (1.0, 1.0), base_fn=lambda t: (0.0, 0.0),  # still rig, target OOF
                    gyro_bias_rps=0.02, gyro_noise_rps=0.01)
    c = characterize(BenchRunner(io).capture_static(seconds=2.0).records)
    assert abs(c["gyro_bias_rps"][1] - 0.02) < 0.008 and 0.004 < c["gyro_noise_rps"][1] < 0.03, c


def test_servo_step_gives_servo_rate():
    io = SimBenchIO(base_fn=lambda t: (0.0, 0.0), servo_rate_max_dps=400.0)
    c = characterize(BenchRunner(io).capture_servo_step(seconds=1.0).records)
    assert 300.0 < c["servo_pan_rate_max_dps"] < 450.0, c


def test_closed_loop_holds_target_under_shake(tmp_path):
    shake = lambda t: (5.0 * math.sin(2 * math.pi * 0.8 * t), 3.0 * math.sin(2 * math.pi * 0.6 * t))
    target = lambda t: (math.radians(10.0) * math.sin(2 * math.pi * 0.5 * t), 0.0)
    io = SimBenchIO(target_fn=target, base_fn=shake, gyro_noise_rps=0.01, servo_rate_max_dps=400.0)
    log = BenchRunner(io, GimbalController()).run_closed_loop(seconds=3.0)
    infov = float(np.mean([1.0 if r.in_fov else 0.0 for r in log.records[300:]]))
    assert infov > 0.98, f"gimbal lost the target under shake: in_fov={infov}"
    log.save_csv(tmp_path / "closed_loop.csv")            # round-trips to the datalog format
    print(f"\n[bench] closed-loop under base shake: target held in FOV {infov*100:.0f}% ({len(log.records)} samples)")
