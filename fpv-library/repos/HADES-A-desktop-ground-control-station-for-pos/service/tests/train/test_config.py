"""Tests for TrainConfig (Tasks 2.5.2 + 2.5.3).

This is also where Task 2.5.2 (augmentation) lives: rather than a hand-rolled transform
(cut — it fights Ultralytics' stochastic pipeline and 'deterministic-under-seed' is a
category error there), the motion-blur + scale-jitter are Ultralytics built-in
hyperparameters carried on the config. The test asserts they're set to the intended
values — that's the meaningful check, not mocking `.train()`.

The config also pins the ablation-fairness knobs (seed, deterministic, fixed batch) so the
two arms differ in exactly one thing: the pretrain weights.
"""

import pytest

from hades.train.config import TrainConfig


def test_config_defaults_pin_ablation_fairness():
    cfg = TrainConfig(weights="yolo11s.pt")
    assert cfg.seed == 0
    assert cfg.deterministic is True
    assert cfg.batch > 0  # a FIXED int, never -1/AutoBatch (non-deterministic across nodes)
    assert cfg.batch != -1


def test_config_augmentation_hyperparams_reach_ultralytics():
    # Task 2.5.2: scale-jitter is the augmentation knob that actually flows to YOLO.train().
    # It MUST appear in to_ultralytics() — a config field that never reaches the trainer
    # would be a silent no-op (the dead-blur_p bug Codex caught).
    cfg = TrainConfig(weights="yolo11s.pt", scale=0.6)
    assert cfg.scale == pytest.approx(0.6)
    assert cfg.to_ultralytics()["scale"] == pytest.approx(0.6)


def test_config_rejects_non_stride32_imgsz():
    with pytest.raises(ValueError, match="32"):
        TrainConfig(weights="yolo11s.pt", imgsz=641)


def test_config_rejects_nonpositive_epochs():
    with pytest.raises(ValueError):
        TrainConfig(weights="yolo11s.pt", epochs=0)


def test_config_to_ultralytics_excludes_meta_fields():
    # The dict handed to YOLO.train must carry hyperparams but not our bookkeeping
    # (weights is the model arg; arm/run-name are passed separately).
    cfg = TrainConfig(weights="yolo11s.pt", imgsz=960, epochs=100, batch=64)
    d = cfg.to_ultralytics()
    assert d["imgsz"] == 960
    assert d["epochs"] == 100
    assert d["batch"] == 64
    assert d["seed"] == 0
    assert d["deterministic"] is True
    assert "weights" not in d  # weights is YOLO(weights), not a train() kwarg
