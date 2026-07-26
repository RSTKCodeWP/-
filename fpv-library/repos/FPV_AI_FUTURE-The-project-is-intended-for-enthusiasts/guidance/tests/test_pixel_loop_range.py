"""Range-dependent target rendering in the Mode-B pixel loop.

The legacy renderer drew a FIXED 1.5 px blob at every range, so a closing target never grew and subtense
ranging could not be exercised in the loop.  With ``PixelLoopState.target_span_m`` set, the rendered blob's
silhouette major (~2.3548*sigma) tracks ``f_px*span/range`` above a PSF floor -- a far target is a point
source (unresolved), a near target resolves.  Default (None) is bit-identical to the fixed-blob legacy.

NOTE on scale: a 4 m wing on the wide FT640 lens (f_px~707) already subtends ~9.4 px at 300 m, so it is
RESOLVED well out to ~800 m (consistent with the doctrine's ~1-1.9 km detect / ~140-235 m ID); it only
collapses to the PSF floor beyond ~800 m.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from fpv.guidance.pixel_loop import _render_one_frame, make_pixel_loop_state, run_pixel_vision_tick
from fpv.guidance.quad_sim import QuadState, TargetState
from fpv.seeker.silhouette import silhouette_extent

SPAN = 4.0


def _tick_at_range(ps, range_m, frame_id):
    """Drive one Mode-B vision tick with the target dead ahead (boresight) at ``range_m``."""
    q = QuadState(pos=np.zeros(3), vel=np.array([0.0, 15.0, 0.0]))
    tgt = TargetState(pos=np.array([0.0, float(range_m), 0.0]), vel=np.array([0.0, -5.0, 0.0]))
    return run_pixel_vision_tick(q_state=q, tgt_state=tgt, pixel_state=ps, frame_id=frame_id,
                                 t_sim=frame_id / 60.0, dt_vision=1.0 / 60.0, range_m=float(range_m))


def test_rendered_sigma_matches_subtense_physics_and_grows_closing():
    ps = make_pixel_loop_state(1)
    ps.target_span_m = SPAN
    f = ps.intrinsics.f_px
    sig = {}
    for i, R in enumerate((1500.0, 400.0, 100.0, 50.0)):
        _tick_at_range(ps, R, i)
        sig[R] = ps.last_rendered_sigma_px
        geom = f * SPAN / (2.3548 * R)
        assert ps.last_rendered_sigma_px == math.hypot(ps.psf_sigma_px, geom)   # exact subtense physics
    assert sig[1500.0] < sig[400.0] < sig[100.0] < sig[50.0]                     # grows as it closes
    assert sig[1500.0] < 1.8       # a far target collapses to the PSF floor (point source, unresolved)
    assert sig[50.0] > 15.0        # a near target is strongly resolved


def test_render_to_silhouette_recovers_closing_range():
    # End-to-end honesty: render the closing target, measure its extent with the SILHOUETTE (raw-frame,
    # top-hat-immune), and confirm R = f*span/major recovers the TRUE range and drops as it closes.
    ps = make_pixel_loop_state(3)
    ps.target_span_m = SPAN
    f = ps.intrinsics.f_px
    intr = ps.intrinsics
    R_ests = []
    for R in (300.0, 150.0, 75.0):
        geom = f * SPAN / (2.3548 * R)
        sigma = math.hypot(ps.psf_sigma_px, geom)
        frame = _render_one_frame(
            target_px=320.0, target_py=256.0, target_in_fov=True, cum_ego_dx=0.0, cum_ego_dy=0.0,
            intrinsics=intr, star_positions=[], rng=np.random.default_rng(0),
            target_sigma_px=sigma, star_sigma_px=1.2)
        sil = silhouette_extent(frame, 320.0, 256.0, peak=4096.0 + 1800.0)
        assert sil.resolved
        R_est = f * SPAN / sil.major_px
        R_ests.append(R_est)
        assert R_est == pytest.approx(R, rel=0.15)          # silhouette subtense recovers the true range
    assert R_ests[0] > R_ests[1] > R_ests[2]                # the estimate closes with the true range


def test_off_path_is_fixed_blob_bit_identical():
    ps = make_pixel_loop_state(4)                   # target_span_m default None
    for i, R in enumerate((300.0, 100.0, 50.0)):
        _tick_at_range(ps, R, i)
        assert ps.last_rendered_sigma_px == ps.psf_sigma_px == 1.5   # fixed blob, range-independent
