"""Tests for the detect golden-vector harness (M0 verification backbone).

These pin the REFERENCE CONTRACT the PL detect IP must reproduce:
  * determinism  -- the golden set is byte-reproducible (so it is a real regression gate);
  * S1 centroid  -- on READY, target-visible frames the float detector tracks ground truth
                    to within the scene's sub-pixel budget (what fixed-point must also meet);
  * FFC freeze   -- no blobs are emitted during the camera-blind window (S1 gate d);
  * false alarm  -- the best blob locks to the target, not to a hard-negative star;
  * on-disk I/O  -- the manifest + raw frames round-trip (the HLS testbench's input format).
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from fpga.ref_model.golden_vectors import (
    GOLDEN_SCENES,
    generate_scene,
    write_vectors,
)


def _ready_visible(records):
    return [r for r in records if r.ffc_state == "READY" and r.gt_visible]


@pytest.mark.parametrize("scene", GOLDEN_SCENES, ids=lambda s: s.name)
def test_generation_is_deterministic(scene):
    """Same scene -> identical records and byte-identical frames. The gate depends on this."""
    rec_a, frames_a = generate_scene(scene)
    rec_b, frames_b = generate_scene(scene)
    assert [r.to_manifest() for r in rec_a] == [r.to_manifest() for r in rec_b]
    assert len(frames_a) == len(frames_b) == scene.n_frames
    for fa, fb in zip(frames_a, frames_b):
        assert np.array_equal(fa, fb), "golden frames must be byte-reproducible"


@pytest.mark.parametrize("scene", GOLDEN_SCENES, ids=lambda s: s.name)
def test_detect_tracks_ground_truth_within_budget(scene):
    """Best-blob centroid vs ground-truth centroid RMSE <= the scene's sub-pixel gate.

    This is the physical contract the fixed-point PL IP must also satisfy.
    """
    records, _ = generate_scene(scene)
    rv = _ready_visible(records)
    assert len(rv) >= 20, "need enough READY frames to grade the centroid"

    errs = []
    detected = 0
    for r in rv:
        if r.best_centroid_px is None:
            continue
        detected += 1
        dx = r.best_centroid_px[0] - r.gt_centroid_px[0]
        dy = r.best_centroid_px[1] - r.gt_centroid_px[1]
        errs.append(math.hypot(dx, dy))

    det_rate = detected / len(rv)
    rmse = math.sqrt(sum(e * e for e in errs) / len(errs)) if errs else float("inf")
    print(f"\n[{scene.name}] detect_rate={det_rate:.3f}  centroid_RMSE={rmse:.4f} px  "
          f"(gate {scene.centroid_rmse_gate_px} px, n={len(errs)})")

    assert det_rate >= 0.90, f"detection rate {det_rate:.3f} < 0.90 (S1 gate c)"
    assert rmse <= scene.centroid_rmse_gate_px, (
        f"centroid RMSE {rmse:.4f} px exceeds the {scene.centroid_rmse_gate_px} px budget "
        f"the fixed-point PL IP must fit under")


@pytest.mark.parametrize("scene", GOLDEN_SCENES, ids=lambda s: s.name)
def test_no_blobs_during_ffc_freeze(scene):
    """S1 gate (d): the detector emits nothing during the FFC camera-blind window."""
    records, _ = generate_scene(scene)
    frozen = [r for r in records if r.ffc_state in ("FREEZE", "RECOVERING")]
    if not frozen:
        pytest.skip("scene has no FFC events")
    offenders = [r.frame_id for r in frozen if r.n_blobs != 0]
    assert not offenders, f"blobs emitted during FFC freeze at frames {offenders}"


@pytest.mark.parametrize("scene", GOLDEN_SCENES, ids=lambda s: s.name)
def test_best_blob_is_target_not_star(scene):
    """False-alarm gate (S1 gate b): the salience-top blob is the target, not a bright star."""
    records, _ = generate_scene(scene)
    sim_cfg = scene.cfg
    rv = _ready_visible(records)

    # star positions are fixed across the run; pull them from the sim once.
    from fpv.seeker.thermal_sim import ThermalSimulator
    stars = ThermalSimulator(sim_cfg).generate(1)[0][1].star_positions_px

    false_locks = 0
    graded = 0
    for r in rv:
        if r.best_centroid_px is None:
            continue
        graded += 1
        d_target = math.hypot(r.best_centroid_px[0] - r.gt_centroid_px[0],
                              r.best_centroid_px[1] - r.gt_centroid_px[1])
        d_star = min((math.hypot(r.best_centroid_px[0] - sx, r.best_centroid_px[1] - sy)
                      for sx, sy in stars), default=float("inf"))
        if d_star < d_target:
            false_locks += 1

    assert graded > 0
    far = false_locks / graded
    print(f"\n[{scene.name}] false-alarm rate (best blob nearer a star than target) = {far:.3f}")
    assert far <= 0.05, f"false-alarm rate {far:.3f} > 5% (S1 gate b)"


def test_vectors_roundtrip_to_disk(tmp_path):
    """The on-disk manifest + raw frames are the HLS testbench's input format; verify they load."""
    scene = GOLDEN_SCENES[0]
    scene_dir = write_vectors(scene, tmp_path)
    manifest = json.loads((scene_dir / "manifest.json").read_text())

    assert manifest["scene"] == scene.name
    assert manifest["n_frames"] == scene.n_frames
    assert len(manifest["frames"]) == scene.n_frames

    # raw frame round-trips to the right shape/dtype and matches the in-memory generation.
    _, frames = generate_scene(scene)
    first = manifest["frames"][0]
    loaded = np.fromfile(scene_dir / first["file"], dtype="<u2").reshape(
        manifest["height"], manifest["width"])
    assert loaded.shape == (scene.cfg.height, scene.cfg.width)
    assert np.array_equal(loaded, frames[0]), "on-disk frame must equal the generated frame"
