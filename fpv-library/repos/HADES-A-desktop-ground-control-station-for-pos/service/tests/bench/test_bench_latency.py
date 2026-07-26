"""Tests for the Phase 1.5 latency benchmark logic (offline, no ANE).

These exercise the *decision* core — stats + the ≥10fps gate + the timing loop —
without CoreML or hardware, so a wrong threshold or off-by-one window can't slip
through only on a machine with an ANE. The actual ANE measurement is a separate
`@pytest.mark.ane` smoke test (manual run on the target Mac).
"""

import itertools

import pytest

from hades.bench.bench_latency import (
    ANE_SPEEDUP_FLOOR,
    FPS_GATE,
    Decision,
    _percentile,
    assess_ane_placement,
    format_table,
    summarize,
    time_inference,
)


def test_summarize_passes_gate_when_fast():
    # 50 ms/frame -> 20 fps, comfortably above the 10fps gate.
    d = summarize(640, [50.0] * 100)
    assert isinstance(d, Decision)
    assert d.fps_median == pytest.approx(20.0)
    assert d.meets_gate is True


def test_summarize_fails_gate_when_slow():
    # 200 ms/frame -> 5 fps, below the gate.
    d = summarize(1280, [200.0] * 100)
    assert d.fps_median == pytest.approx(5.0)
    assert d.meets_gate is False


def test_gate_boundary_is_inclusive():
    # Exactly 100 ms/frame -> exactly 10.0 fps; the gate is >= so this passes.
    d = summarize(960, [100.0] * 50)
    assert d.fps_median == pytest.approx(FPS_GATE)
    assert d.meets_gate is True


def test_gate_uses_median_not_mean_so_one_spike_does_not_flip_it():
    # 99 frames at 50 ms (20 fps) + one 5000 ms stall. Mean is dragged way down in
    # fps, but the median stays at 50 ms -> verdict must remain pass.
    lat = [50.0] * 99 + [5000.0]
    d = summarize(640, lat)
    assert d.median_ms == pytest.approx(50.0)
    assert d.meets_gate is True
    # ...but the tail is still visible in p90/mean so the stall isn't hidden.
    assert d.p90_ms == pytest.approx(50.0)
    assert d.mean_ms > d.median_ms


def test_percentile_interpolates():
    data = [10.0, 20.0, 30.0, 40.0]  # already sorted
    assert _percentile(data, 50.0) == pytest.approx(25.0)
    assert _percentile(data, 0.0) == pytest.approx(10.0)
    assert _percentile(data, 100.0) == pytest.approx(40.0)


def test_percentile_single_value():
    assert _percentile([42.0], 90.0) == pytest.approx(42.0)


def test_summarize_rejects_empty():
    with pytest.raises(ValueError):
        summarize(640, [])


def test_summarize_rejects_nonpositive_latency():
    with pytest.raises(ValueError):
        summarize(640, [50.0, 0.0, 50.0])


def test_summarize_rejects_bad_resolution():
    with pytest.raises(ValueError):
        summarize(0, [50.0])


def test_time_inference_returns_one_latency_per_measured_frame():
    calls = itertools.count()

    def infer():
        next(calls)

    lat = time_inference(infer, warmup_frames=5, measure_frames=20)
    assert len(lat) == 20  # only the measured window, not warm-up
    # warm-up (5) + measured (20) calls total.
    assert next(calls) == 25
    assert all(x >= 0 for x in lat)


def test_time_inference_zero_warmup_allowed():
    lat = time_inference(lambda: None, warmup_frames=0, measure_frames=3)
    assert len(lat) == 3


def test_time_inference_rejects_zero_measure():
    with pytest.raises(ValueError):
        time_inference(lambda: None, warmup_frames=1, measure_frames=0)


def test_ane_placement_flags_cpu_fallback():
    # ALL tracks CPU_ONLY (no speedup) -> Core ML fell back to CPU, not the ANE.
    p = assess_ane_placement(640, cpu_only_ms=20.0, all_ms=19.5)
    assert p.speedup < ANE_SPEEDUP_FLOOR
    assert p.ane_served is False


def test_ane_placement_confirms_when_much_faster():
    # The observed Air result: ~20 ms CPU vs ~3.5 ms ALL -> ANE served it.
    p = assess_ane_placement(640, cpu_only_ms=19.8, all_ms=3.5)
    assert p.speedup > ANE_SPEEDUP_FLOOR
    assert p.ane_served is True


def test_ane_placement_boundary_is_inclusive():
    p = assess_ane_placement(640, cpu_only_ms=20.0, all_ms=10.0)  # exactly 2.0x
    assert p.speedup == pytest.approx(ANE_SPEEDUP_FLOOR)
    assert p.ane_served is True


def test_ane_placement_rejects_nonpositive():
    with pytest.raises(ValueError):
        assess_ane_placement(640, cpu_only_ms=0.0, all_ms=3.5)


def test_format_table_marks_pass_and_fail():
    fast = summarize(640, [50.0] * 10)   # passes
    slow = summarize(1280, [200.0] * 10)  # fails
    table = format_table([fast, slow])
    assert "640" in table and "1280" in table
    assert "✅" in table  # the passing row
    assert "❌" in table  # the failing row
    assert "fps (median)" in table
