"""Engine tests for the seeker bench -- synthetic frames, no hardware, no Flask."""

from __future__ import annotations

import json

import numpy as np
import pytest

from fpv_ai.sensor.thermal_capture import SyntheticSource
from fpv_ai.bench.observer import ObserverConfig, SeekerObserver

H, W = 512, 640


def _frame(cx: int, cy: int, hot: int = 230, bg: int = 30, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    f = (bg + rng.normal(0, 2, (H, W))).clip(0, 255).astype(np.uint16)
    f[max(0, cy - 3):cy + 3, max(0, cx - 3):cx + 3] = hot
    return f


def _make(frames, **kw) -> SeekerObserver:
    cfg = ObserverConfig(width=W, height=H, border_crop=0, warmup_frames=5,
                         mask_on=kw.pop("mask_on", False), **kw)
    return SeekerObserver(cfg, source=SyntheticSource(frames))


def test_process_one_shapes_and_keys() -> None:
    obs = _make([_frame(320, 256, seed=i) for i in range(4)])
    annotated, telem = obs.process_one()
    assert annotated is not None and annotated.shape == (H, W, 3)
    assert annotated.dtype == np.uint8
    for k in ("state", "locked", "fps_total", "n_blobs", "threshold", "resolution"):
        assert k in telem
    assert telem["resolution"] == [W, H]


def test_telemetry_is_json_serialisable() -> None:
    obs = _make([_frame(300, 240, seed=i) for i in range(4)])
    _, telem = obs.process_one()
    json.dumps(telem)  # must not raise


def test_hot_spot_is_detected() -> None:
    obs = _make([_frame(320, 256, seed=i) for i in range(3)])
    _, telem = obs.process_one()
    assert telem["n_blobs"] >= 1
    assert telem["top"] is not None
    assert abs(telem["top"]["x"] - 320) < 6 and abs(telem["top"]["y"] - 256) < 6


def test_tracker_locks_a_stable_target() -> None:
    obs = _make([_frame(320, 256, seed=i) for i in range(14)])
    states = []
    for _ in range(12):
        _, telem = obs.process_one()
        states.append(telem["state"])
    assert any(s in ("TRACKING", "LOCKED") for s in states), states
    last = telem
    assert last["centroid"] is not None
    assert abs(last["centroid"][0] - 320) < 8


def test_no_frame_returns_error_telemetry() -> None:
    obs = _make([_frame(320, 256)])
    obs.process_one()             # consumes the only frame
    annotated, telem = obs.process_one()  # source now exhausted
    assert annotated is None
    assert telem.get("error") == "no_frame"


def test_clutter_mask_calibration_flags_static_bright_region() -> None:
    # a persistent bright square -> should be masked
    static = _frame(100, 100, hot=255, seed=7)
    frames = [static.copy() for _ in range(8)]
    obs = _make(frames, mask_on=True)
    assert obs._clutter is not None
    assert int(obs._clutter.sum()) > 0


def test_apply_control_toggles() -> None:
    obs = _make([_frame(320, 256, seed=i) for i in range(4)])
    st = obs.apply_control({"min_snr": 5.0, "min_area": 7, "invert": True})
    assert st["min_snr"] == 5.0 and st["min_area"] == 7 and st["invert"] is True
    assert obs.cap.cfg.invert is True
    obs.apply_control({"mask_on": False})
    assert obs.cfg.mask_on is False and obs._clutter is None


def test_sim_source_drives_a_visible_lock() -> None:
    from fpv_ai.bench.sim_source import SimFrameSource
    obs = SeekerObserver(ObserverConfig(border_crop=0, mask_on=False),
                         source=SimFrameSource(n_frames=80))
    telem = {}
    annotated = None
    for _ in range(30):
        annotated, telem = obs.process_one()
    assert annotated is not None and annotated.shape == (H, W, 3)   # renders 14-bit sim frames
    assert telem["state"] in ("TRACKING", "LOCKED")                 # locks the moving sim target


def test_starts_in_standby() -> None:
    obs = _make([_frame(320, 256, seed=i) for i in range(4)])
    _, telem = obs.process_one()
    assert obs.engaged is False
    assert telem["mode"] == "STANDBY" and telem["armed"] is False


def test_launch_requires_lock() -> None:
    obs = _make([_frame(40, 40, seed=i) for i in range(8)])   # corner -> outside reticle
    for _ in range(6):
        obs.process_one()
    ok, reason = obs.launch()
    assert ok is False and reason == "no_lock"
    assert obs.engaged is False


def test_launch_engages_on_centred_lock() -> None:
    obs = _make([_frame(320, 256, seed=i) for i in range(16)])
    telem = {}
    for _ in range(10):
        _, telem = obs.process_one()
    assert telem["locked"] is True
    ok, reason = obs.launch()
    assert ok is True and reason == "engaged"
    _, telem2 = obs.process_one()
    assert obs.engaged is True
    assert telem2["mode"] == "ENGAGED" and telem2["can_launch"] is False


def test_safe_returns_to_standby() -> None:
    obs = _make([_frame(320, 256, seed=i) for i in range(18)])
    for _ in range(10):
        obs.process_one()
    obs.launch()
    assert obs.engaged is True
    ok, reason = obs.safe()
    assert ok and reason == "standby" and obs.engaged is False


def test_reticle_gates_offcentre_target() -> None:
    obs = _make([_frame(40, 40, seed=i) for i in range(16)])   # corner target, outside reticle
    telem = {}
    states = []
    for _ in range(12):
        _, telem = obs.process_one()
        states.append(telem["state"])
    assert all(s != "LOCKED" for s in states), states
    assert telem["locked"] is False


def test_min_snr_control_reaches_detector() -> None:
    obs = _make([_frame(320, 256, seed=i) for i in range(8)])
    _, before = obs.process_one()
    assert before["n_blobs"] >= 1
    obs.apply_control({"min_snr": 9999.0})       # impossibly strict -> nothing passes
    assert obs.pipe.min_snr == 9999.0
    _, after = obs.process_one()
    assert after["n_blobs"] == 0                  # the gate actually bites the detector
