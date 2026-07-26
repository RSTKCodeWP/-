"""Bench Y16 LOSSLESS dataset recording (server-side wiring)."""

from __future__ import annotations

import numpy as np

from fpv_ai.sensor.thermal_capture import SyntheticSource
from fpv_ai.bench.observer import ObserverConfig, SeekerObserver
from fpv_ai.bench.server import BenchServer
from fpv.seeker.classify.collect import load_y16_clip

H, W = 64, 80


def _u16(seed=0):
    rng = np.random.default_rng(seed)
    f = (4096 + rng.integers(0, 4000, (H, W))).astype(np.uint16)
    f[28:34, 36:44] = 12000
    return f


def _server(tmp_path):
    obs = SeekerObserver(ObserverConfig(width=W, height=H, border_crop=0, warmup_frames=2, mask_on=False),
                         source=SyntheticSource([_u16(i) for i in range(6)]))
    srv = BenchServer(obs)
    srv._y16_dataset_dir = str(tmp_path)
    return srv


def test_y16_record_writes_a_labelled_lossless_clip(tmp_path):
    srv = _server(tmp_path)
    r = srv._toggle_y16_record(True, {"class_label": "drone", "sortie_id": "t1",
                                      "is_radiometric_y16": True, "sensor": "Y16_x",
                                      "range_hint_m": 150, "aspect_deg": 20, "conditions": "day/sky"})
    assert r["ok"] and srv._y16_rec is not None
    # the seeker loop feeds raw u16 frames -> mimic that capture
    frames = [_u16(i) for i in range(5)]
    for f in frames:
        srv._y16_rec.add(f)
    stop = srv._toggle_y16_record(False, {})
    assert stop["ok"] and stop["info"].endswith(".npz")

    got, man = load_y16_clip(stop["info"])
    assert np.array_equal(got, np.stack(frames))            # LOSSLESS raw u16
    assert man.class_label == "DRONE" and man.is_radiometric_y16 is True
    assert man.sortie_id == "t1" and man.range_hint_m == 150.0 and man.n_frames == 5


def test_y16_record_defaults_to_honest_non_radiometric(tmp_path):
    # The bench's 8-bit CVBS source records honestly-flagged transcodes by default (do NOT count as Y16).
    srv = _server(tmp_path)
    srv._toggle_y16_record(True, {"class_label": "BIRD", "sortie_id": "b"})
    srv._y16_rec.add(_u16())
    path = srv._toggle_y16_record(False, {})["info"]
    _, man = load_y16_clip(path)
    assert man.is_radiometric_y16 is False and man.sensor == "FT640_CVBS_8bit"


def test_double_start_and_stop_without_start_are_safe(tmp_path):
    srv = _server(tmp_path)
    assert srv._toggle_y16_record(False, {})["ok"] is False   # stop with nothing recording
    srv._toggle_y16_record(True, {"class_label": "DRONE", "sortie_id": "x"})
    assert srv._toggle_y16_record(True, {})["ok"] is False     # already recording
    srv._y16_rec.add(_u16())
    assert srv._toggle_y16_record(False, {})["ok"] is True
