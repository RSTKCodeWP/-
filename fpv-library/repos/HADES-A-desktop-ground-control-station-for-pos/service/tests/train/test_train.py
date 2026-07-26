"""Tests for the training entry's pure helpers (Task 2.5.3).

Only the pure, failure-prone logic is tested — NOT the `YOLO.train()` call (mocking it
proves nothing). The two things that, done wrong, waste GPU days or corrupt the ablation:

- `should_resume`: on a fresh submit there's no checkpoint (must start fresh); on a SLURM
  requeue the per-arm `last.pt` exists (must resume from it, by absolute path). Getting this
  backwards either crashes the fresh job or silently restarts a requeue from epoch 0.
- `map_visdrone_class`: pedestrian + people → person; vehicles → drop. The collision guard
  for the VisDrone pretrain arm.
"""

import pytest

from hades.train.dataset import DROP
from hades.train.train import map_visdrone_class, resume_arg


def test_resume_arg_fresh_when_no_checkpoint(tmp_path):
    # Fresh submit: runs/<arm>/weights/last.pt does not exist -> resume disabled.
    assert resume_arg(tmp_path / "armA") is False


def test_resume_arg_absolute_path_when_checkpoint_exists(tmp_path):
    arm_dir = tmp_path / "armA"
    weights = arm_dir / "weights"
    weights.mkdir(parents=True)
    last = weights / "last.pt"
    last.write_bytes(b"stub")
    # Requeue: resume from the per-arm checkpoint BY ABSOLUTE PATH (never bare True, which
    # scans sibling runs and could resume the WRONG arm).
    out = resume_arg(arm_dir)
    assert out == str(last)


def test_map_visdrone_pedestrian_and_people_to_person():
    # VisDrone Roboflow export class order: 0=pedestrian, 1=people.
    assert map_visdrone_class("pedestrian") == "person"
    assert map_visdrone_class("people") == "person"


def test_map_visdrone_vehicles_drop():
    for veh in ("car", "van", "truck", "bus", "motor", "bicycle"):
        assert map_visdrone_class(veh) == DROP


def test_map_visdrone_unknown_raises():
    with pytest.raises(ValueError):
        map_visdrone_class("spaceship")
