"""Honest CLOSED-LOOP tests for the GIMBAL-FRAMED seeker (the head points BY the tracked pixel).

Companion to test_strapdown_honest_weaknesses.py. Those pin the strapdown *failures*; these pin the two
positive facts of the gimbal-framed closed loop, where the render follows the head (gimbal_los="seeker"):
the stabilized head keeps the target near boresight and PN rides the head's OWN pixel-derived LOS
(g_point), so PERCEPTION is now IN the guidance loop.

  1. Closing the loop on the seeker's pixel HITS body-to-body (~1.3 m) -- unlike the strapdown, the
     gimbal holds the target in FOV so the pixel-derived lambda-dot is clean enough to guide.

  2. A perception failure MOVES THE MISS. A terminal occlusion (target dims behind a cloud) with a fixed
     off-axis bright source: WITHOUT the occlusion-coast lock-hold the tracker deletes the track and
     reacquires the SUN; the head physically slews to center it and PN drives off the true target ->
     catastrophic miss. WITH the coast it holds the true target through the occlusion -> hit. Same scene,
     same seed -- only the ThermalLockConfig.occlusion_coast_frames flag differs. The false-lock is
     PHYSICALLY PRODUCED (the tracked centroid lands on the sun's pixel), not asserted.

Body-to-body means CPA within cfg.cap_m (1.5 m). The coast=0 miss below is ~10 m -- unambiguous.
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import pytest

from fpv_ai.bench.sim3d import Sim3DConfig, _geometry_ic
from fpv_ai.bench.sim3d_honest import run_honest

pytestmark = pytest.mark.slow  # each scenario is a full MuJoCo closing engagement

SEED = 11
CAP_M = Sim3DConfig().cap_m
_GIMBAL = dict(gimbal=True, gimbal_los="seeker", gimbal_rate_max_dps=300.0, gimbal_tau_s=0.05)


def _cfg() -> Sim3DConfig:
    return Sim3DConfig(geometry="head_on", g_max=6.0, committed=True, seed=SEED)


def _sun_dir(off_deg: float = 8.0) -> np.ndarray:
    """A fixed bright source off the INITIAL launch LOS by off_deg (rotated about the vertical)."""
    cfg = _cfg()
    tpos, _ = _geometry_ic(cfg)
    los = tpos - np.array(cfg.int_pos)
    los = los / np.linalg.norm(los)
    k = np.array([0.0, 0.0, 1.0])
    a = math.radians(off_deg)
    d = los * math.cos(a) + np.cross(k, los) * math.sin(a) + k * float(np.dot(k, los)) * (1 - math.cos(a))
    return d / np.linalg.norm(d)


def _terminal_occlusion(step, px, py, rng_m):
    """Target dims behind a cold cloud in a terminal range band that CLEARS at ~92 m -- the worst case:
    the reacquire fires with just enough time to slew the head onto a distractor, none to recover."""
    if 92.0 <= rng_m <= 120.0:
        return {"occ_scale": 0.08, "occ_cold": (px, py, 55.0, -34.0)}
    return {}


@lru_cache(maxsize=None)
def _run(coast: int | None) -> dict:
    """coast=None -> the clean baseline (no occlusion, no sun); else the occlusion+sun scene at that coast."""
    if coast is None:
        return run_honest(_cfg(), **_GIMBAL)
    return run_honest(_cfg(), **_GIMBAL, scene=_terminal_occlusion, sun_dir=_sun_dir(),
                      pipeline_kwargs={"occlusion_coast_frames": coast})


def test_gimbal_framed_seeker_closes_body_to_body():
    """The pixel-closed gimbal loop FLIES: guiding on the head's own tracked-pixel LOS reaches CPA within
    the capture radius (~1.3 m). This is the closed-loop counterpart to the strapdown misses -- the head
    keeps the target in FOV, so perception can guide."""
    r = _run(None)
    assert r["hit"], f"gimbal-framed closed loop should hit body-to-body, CPA={r['cpa']:.2f} m"
    assert r["cpa"] <= CAP_M, f"CPA {r['cpa']:.2f} m should be within the {CAP_M} m capture radius"
    assert r["lock_rate"] > 0.8, f"the centered head should hold lock most frames, got {r['lock_rate']:.2f}"


def test_perception_false_lock_moves_the_miss():
    """Same terminal-occlusion scene, same seed: WITHOUT the occlusion coast the seeker false-locks the
    off-axis sun and the head chases it -> a ~10 m miss; WITH the coast it holds the true target -> a hit.
    Perception is genuinely in the loop -- a tracker failure becomes a guidance miss."""
    miss = _run(0)
    hold = _run(20)
    assert not miss["hit"] and miss["cpa"] > 5.0, (
        f"without the coast, the terminal-occlusion false-lock should miss badly, got {miss['cpa']:.2f} m")
    assert hold["hit"] and hold["cpa"] <= CAP_M, (
        f"with the coast, the head should hold through the occlusion and hit, got {hold['cpa']:.2f} m")
    assert miss["cpa"] > hold["cpa"] + 5.0, (
        f"the coast must clearly rescue the engagement: miss {miss['cpa']:.2f} vs hold {hold['cpa']:.2f}")
