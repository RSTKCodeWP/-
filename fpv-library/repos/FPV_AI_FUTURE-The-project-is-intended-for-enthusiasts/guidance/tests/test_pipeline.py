"""Seeker->guidance pipeline + full-system integration (Block-3 piece #1).

Drives REAL synthetic thermal frames (S1 ThermalSimulator) through the actual
perception+guidance chain, and then through the onboard runtime's safety layers to RC.
"""

from __future__ import annotations

import numpy as np

from fpv.seeker.thermal_sim import ThermalSceneConfig, ThermalSimulator
from fpv.guidance.pipeline import SeekerGuidancePipeline

from fpv_ai.betaflight_link.arming import ArmingConfig, ArmingStateMachine, ArmState
from fpv_ai.betaflight_link.failsafe import FailsafeController
from fpv_ai.betaflight_link.hwkill import HardwareKill
from fpv_ai.betaflight_link.onboard_runtime import OnboardRuntime
from fpv_ai.betaflight_link.serial_link import MockFcChannel, MspLink
from fpv_ai.betaflight_link.tests.test_arming import live_auth

DT = 1.0 / 60.0


def test_pipeline_locks_and_commands_on_thermal_target():
    sim = ThermalSimulator(ThermalSceneConfig(ffc_freeze_interval=0, n_stars=3))
    frames = sim.generate(10)
    pipe = SeekerGuidancePipeline()
    commands = 0
    out = None
    for i, (frame, _gt) in enumerate(frames):
        out = pipe.step(now=i * DT, frame_u16=frame, gyro_omega_xyz=(0.0, 0.0, 0.0), dt=DT)
        if out.command is not None:
            commands += 1
            assert -1.0 <= out.command.roll_cmd <= 1.0
            assert 0.0 <= out.command.throttle_cmd <= 1.0
    assert commands >= 1                  # the real chain produced guidance from pixels
    assert out.locked is True
    assert out.tracking_state in ("LOCKED", "CANDIDATE", "PREDICTIVE_TRACK", "REACQUIRE")


def test_pipeline_no_target_no_command():
    pipe = SeekerGuidancePipeline()
    cold_sky = np.full((512, 640), 4096, dtype=np.uint16)   # uniform cold sky, no hot blob
    out = pipe.step(now=0.0, frame_u16=cold_sky, gyro_omega_xyz=(0.0, 0.0, 0.0), dt=DT)
    assert out.command is None and out.locked is False


def test_default_acquisition_is_a_centered_basket_not_full_frame():
    # A1: the full-frame acquisition default was the look-down bug; default to a basket.
    pipe = SeekerGuidancePipeline()
    w, h = float(pipe.intrinsics.width), float(pipe.intrinsics.height)
    box = pipe._tracker._acq_box
    assert box is not None
    bx, by, bw, bh = box
    assert bw < w and bh < h                                  # NOT the whole frame
    assert abs((bx + bw / 2.0) - w / 2.0) < 1.0               # centred on boresight
    assert abs((by + bh / 2.0) - h / 2.0) < 1.0


def test_designate_reseeds_basket_on_operator_aim():
    pipe = SeekerGuidancePipeline()
    pipe.designate((100.0, 90.0), basket_px=60.0)
    bx, by, bw, bh = pipe._tracker._acq_box
    assert (bw, bh) == (60.0, 60.0)
    assert abs((bx + bw / 2.0) - 100.0) < 1e-6
    assert abs((by + bh / 2.0) - 90.0) < 1e-6


def test_basket_fraction_validated():
    import pytest
    for bad in (0.0, -0.5, 1.5, float("nan")):
        with pytest.raises(ValueError):
            SeekerGuidancePipeline(acquisition_basket_fraction=bad)   # C7


def test_designate_validates_and_clamps():
    import pytest
    pipe = SeekerGuidancePipeline()
    for bad in (0.0, -5.0):
        with pytest.raises(ValueError):
            pipe.designate((100.0, 90.0), basket_px=bad)             # C5
    with pytest.raises(ValueError):
        pipe.designate((float("nan"), 90.0))                         # center must be finite
    pipe.designate((320.0, 256.0), basket_px=99999.0)                # C9: oversized -> clamped
    bx, by, bw, bh = pipe._tracker._acq_box
    w, h = float(pipe.intrinsics.width), float(pipe.intrinsics.height)
    assert bw <= w and bh <= h and bx >= 0.0 and by >= 0.0
    assert bx + bw <= w + 1e-6 and by + bh <= h + 1e-6


def test_full_system_pixels_to_rc_reaches_ai_active():
    sim = ThermalSimulator(ThermalSceneConfig(ffc_freeze_interval=0))
    frames = sim.generate(40)
    pipe = SeekerGuidancePipeline()

    fc = MockFcChannel()
    link = MspLink.for_bench(fc)
    sm = ArmingStateMachine(ArmingConfig(armed_idle_dwell_s=0.02, stabilize_dwell_s=0.02, ramp_s=0.05))
    rt = OnboardRuntime(link=link, arming=sm, failsafe=FailsafeController(), hwkill=HardwareKill())
    auth = live_auth(now=0.0, ttl=100.0)

    seeker_commands = 0
    states = []
    for i, (frame, _gt) in enumerate(frames):
        now = i * DT
        rt.hwkill.permit_beacon(now)                                   # the ground console keeps power permitted
        out = pipe.step(now, frame, (0.0, 0.0, 0.0), DT)               # pixels -> guidance command
        if out.command is not None:
            seeker_commands += 1
        step = rt.step(now, guidance_command=out.command, los_fresh=out.locked,
                       authorization=(auth if i == 0 else None))       # -> arming/failsafe/hwkill -> RC
        states.append(step)

    assert seeker_commands >= 5                                         # the seeker drove the loop
    assert any(s.arm_state == ArmState.AI_ACTIVE for s in states)       # the system reached live AI control
    final = states[-1]
    assert final.arm_state == ArmState.AI_ACTIVE
    assert final.effective_motor_power is True                          # armed AND hw-kill permits power
    assert fc.armed is True                                             # the FC actually armed from the runtime's RC


def test_pipeline_mti_gates_static_clutter_distractor():
    # Phase B (C1-aware): the operator-designated target is centred (in the basket); a bright
    # STATIC clutter distractor sits OFF-CENTRE.  The tracker locks the moving target; MTI gates
    # the static distractor out of the detections.
    H, W = 512, 640
    yy, xx = np.mgrid[0:H, 0:W]
    rng = np.random.default_rng(0)
    bg = (4096 + rng.normal(0, 5, (H, W))).astype(np.float32)
    bg += 3000.0 * np.exp(-((xx - 560) ** 2 + (yy - 420) ** 2) / (2 * 2.0 ** 2))   # off-centre STATIC clutter

    def frame(tx):
        f = bg + 1800.0 * np.exp(-((xx - tx) ** 2 + (yy - 256) ** 2) / (2 * 2.0 ** 2))  # centred MOVING target
        return np.clip(f, 0, 65535).astype(np.uint16)

    pipe = SeekerGuidancePipeline(motion_gate=True)
    out = None
    tx = 320
    for i in range(12):
        out = pipe.step(now=i * DT, frame_u16=frame(tx), gyro_omega_xyz=(0.0, 0.0, 0.0), dt=DT)
        tx += 4
    cents = [(b.centroid_px[0], b.centroid_px[1]) for b in out.blobs]
    assert not any(abs(x - 560) < 12 and abs(y - 420) < 12 for x, y in cents), "static distractor must be gated"
    assert out.locked


def test_pipeline_mti_keeps_locked_target_when_distractor_moves():
    # C1: a LOCKED (hovering) target must NOT be dropped when a BACKGROUND distractor moves.
    H, W = 512, 640
    yy, xx = np.mgrid[0:H, 0:W]
    rng = np.random.default_rng(0)

    def frame(dx):
        f = 4096 + rng.normal(0, 5, (H, W))
        f += 2000.0 * np.exp(-((xx - 320) ** 2 + (yy - 256) ** 2) / (2 * 2.0 ** 2))  # STATIC locked target
        f += 2000.0 * np.exp(-((xx - dx) ** 2 + (yy - 60) ** 2) / (2 * 2.0 ** 2))    # MOVING distractor (top)
        return np.clip(f, 0, 65535).astype(np.uint16)

    pipe = SeekerGuidancePipeline(motion_gate=True)
    out = None
    dx = 100
    for i in range(14):
        out = pipe.step(now=i * DT, frame_u16=frame(dx), gyro_omega_xyz=(0.0, 0.0, 0.0), dt=DT)
        dx += 8
    assert out.locked, "C1: a static locked target must survive while a background distractor moves"
    assert out.centroid_px is not None and abs(out.centroid_px[0] - 320) < 12


def test_pipeline_mti_keeps_hovering_target_when_nothing_moves():
    # soft MTI gate: a stationary/hovering target must NOT be erased when nothing moves.
    H, W = 512, 640
    yy, xx = np.mgrid[0:H, 0:W]
    rng = np.random.default_rng(0)

    def frame():
        f = 4096 + rng.normal(0, 5, (H, W))
        f += 2000.0 * np.exp(-((xx - 320) ** 2 + (yy - 256) ** 2) / (2 * 2.0 ** 2))  # STATIC target
        return np.clip(f, 0, 65535).astype(np.uint16)

    pipe = SeekerGuidancePipeline(motion_gate=True)
    out = None
    for i in range(12):
        out = pipe.step(now=i * DT, frame_u16=frame(), gyro_omega_xyz=(0.0, 0.0, 0.0), dt=DT)
    assert out.locked, "a hovering target must still be tracked under the soft MTI gate"


# ── B3 trajectory-continuity backstop ────────────────────────────────────────

_H, _W = 512, 640
_YY, _XX = np.mgrid[0:_H, 0:_W]


def _centered_blob_frame(present: bool, *, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    f = 4096 + rng.normal(0, 5, (_H, _W))
    if present:
        f += 2000.0 * np.exp(-((_XX - 320) ** 2 + (_YY - 256) ** 2) / (2 * 2.0 ** 2))
    return np.clip(f, 0, 65535).astype(np.uint16)


def test_pipeline_engage_permitted_on_clean_target():
    # A4: a clean, consistent track is engagement-permitted; the field is wired through.
    sim = ThermalSimulator(ThermalSceneConfig(ffc_freeze_interval=0, n_stars=3))
    frames = sim.generate(10)
    pipe = SeekerGuidancePipeline()
    out = None
    for i, (frame, _gt) in enumerate(frames):
        out = pipe.step(now=i * DT, frame_u16=frame, gyro_omega_xyz=(0.0, 0.0, 0.0), dt=DT)
    assert out.locked is True
    assert out.engage_permitted is True       # the IMM model-wrong alarm never fired


# ── B3 trajectory-continuity backstop ────────────────────────────────────────


def test_pipeline_continuity_locks_persistent_target():
    # A genuine, persistent target must still lock with the backstop on -- it only delays
    # acquisition by the few frames the manager needs to confirm trajectory continuity.
    pipe = SeekerGuidancePipeline(trajectory_continuity=True)
    out = None
    for i in range(16):
        out = pipe.step(now=i * DT, frame_u16=_centered_blob_frame(True, seed=i),
                        gyro_omega_xyz=(0.0, 0.0, 0.0), dt=DT)
    assert out.locked, "a persistent target must confirm and lock under the continuity backstop"


def test_pipeline_continuity_rejects_short_transient_that_fools_bare_tracker():
    # A 3-frame transient blink (a parallax/flash artefact) at boresight: the bare tracker
    # (stable_frame_count=3) locks onto it, but the continuity backstop -- which needs N-of-M
    # hits AND enough CV-residual history -- refuses to ever let it seed a lock.
    def frames():
        # empty sky, then the blob present on exactly frames 4,5,6, then empty again
        return [i in (4, 5, 6) for i in range(12)]

    bare = SeekerGuidancePipeline()                       # no backstop
    guarded = SeekerGuidancePipeline(trajectory_continuity=True)
    bare_locked = guarded_locked = False
    for i, present in enumerate(frames()):
        fr = _centered_blob_frame(present, seed=i)
        ob = bare.step(now=i * DT, frame_u16=fr, gyro_omega_xyz=(0.0, 0.0, 0.0), dt=DT)
        og = guarded.step(now=i * DT, frame_u16=fr, gyro_omega_xyz=(0.0, 0.0, 0.0), dt=DT)
        bare_locked = bare_locked or ob.locked
        guarded_locked = guarded_locked or og.locked
    assert bare_locked, "sanity: the bare tracker is fooled by the 3-frame transient"
    assert not guarded_locked, "the continuity backstop must reject the short transient"


# ===========================================================================
# Subtense range aiding — helper gating logic + end-to-end wiring
# ===========================================================================

import math                                                       # noqa: E402
import pytest                                                     # noqa: E402

from fpv.guidance.pipeline import RangeAiding, range_aiding_from_estimate   # noqa: E402
from fpv.seeker.subtense_range import RangeRateEstimate           # noqa: E402


def _rre(*, R=120.0, Vc=80.0, t_go=1.5, sig_vc_total=8.0, resolved=True, initialized=True):
    """Build a RangeRateEstimate with the fields the aiding gate reads."""
    return RangeRateEstimate(
        range_m=R, closing_mps=Vc, t_go_s=t_go,
        sigma_range_random_m=1.0, sigma_range_systematic_m=1.0, sigma_range_total_m=1.4,
        sigma_closing_random_mps=sig_vc_total, sigma_closing_systematic_mps=0.0,
        sigma_closing_total_mps=sig_vc_total,
        rho=1.0 / R, resolved=resolved, measurement_applied=True,
        initialized=initialized, frame_id=10)


def test_aiding_none_is_inactive():
    a = range_aiding_from_estimate(None)
    assert a.source == "inactive" and a.vc_override_mps is None


def test_aiding_uses_confident_closing():
    a = range_aiding_from_estimate(_rre(Vc=80.0, sig_vc_total=8.0))   # rel sigma 0.1 <= 0.5
    assert a.source == "measured"
    assert a.vc_override_mps == pytest.approx(80.0)
    assert a.t_go_s == pytest.approx(1.5)
    assert a.closing_mps == pytest.approx(80.0)


def test_aiding_declines_when_not_yet_initialized():
    a = range_aiding_from_estimate(_rre(initialized=False))
    assert a.source == "fallback" and a.vc_override_mps is None and a.range_m is None


def test_aiding_declines_below_closing_floor():
    a = range_aiding_from_estimate(_rre(Vc=1.0), min_closing_mps=3.0)   # too slow / near-static
    assert a.source == "fallback" and a.vc_override_mps is None


def test_aiding_declines_when_uncertain():
    a = range_aiding_from_estimate(_rre(Vc=80.0, sig_vc_total=60.0),   # rel sigma 0.75 > 0.5
                                   max_closing_rel_sigma=0.5)
    assert a.source == "fallback" and a.vc_override_mps is None
    assert a.range_m is not None                                        # range still reported


def test_aiding_declines_on_opening_target():
    a = range_aiding_from_estimate(_rre(Vc=-20.0))                      # opening -> not closing
    assert a.source == "fallback" and a.vc_override_mps is None


def test_aiding_drops_nonfinite_tgo():
    a = range_aiding_from_estimate(_rre(Vc=80.0, t_go=float("inf"), sig_vc_total=8.0))
    assert a.source == "measured" and a.t_go_s is None                 # closing but t_go not finite


# -- end-to-end wiring on hand-built growing (closing) blobs -----------------

def _frame_with_blob(cx, cy, sigma, *, peak=2000.0, w=640, h=512, bg=4096, seed=0):
    rng = np.random.default_rng(seed)
    img = np.full((h, w), float(bg), dtype=np.float64)
    img += rng.normal(0.0, 8.0, img.shape)
    yy, xx = np.mgrid[0:h, 0:w]
    img += peak * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma ** 2))
    return np.clip(img, 0, 16383).astype(np.uint16)


def test_range_aiding_wires_measured_vc_into_guidance_on_closing_target():
    # A growing silhouette (closing) -> measured range + closing -> PN uses the MEASURED Vc.
    # NOTE: asserts the WIRING (measured Vc reaches guidance); quantitative range/Vc accuracy is covered
    # by the 24 subtense-filter unit tests. Extent here is bbox-major (a first cut; robust silhouette
    # extent under top-hat interior-suppression is the next refinement), and the growth is kept gentle
    # and monotonic to stay out of the fill-the-FOV saturation regime.
    pipe = SeekerGuidancePipeline(target_span_m=3.0, target_span_sigma_m=0.0,
                                  range_aiding_max_rel_sigma=0.6)
    measured = None
    prev_R = None
    for k in range(40):
        sigma = 2.5 + 0.08 * k                                 # blob grows 2.5 -> ~5.6 px (gentle approach)
        out = pipe.step(now=k * DT, frame_u16=_frame_with_blob(320, 256, sigma, seed=k),
                        gyro_omega_xyz=(0.0, 0.0, 0.0), dt=DT)
        if out.range_aiding_source == "measured":
            if prev_R is not None:
                assert out.range_m <= prev_R + 1.0             # range monotonically closing (± noise)
            prev_R = out.range_m
            measured = out
    assert measured is not None, "a closing target should eventually yield a confident measured Vc"
    assert 3.0 <= measured.closing_mps < 500.0                 # positive, physical closing (not degenerate)
    assert measured.range_m is not None and measured.range_m > 0.0
    assert math.isfinite(measured.t_go_s)                      # a real time-to-go, not 'unobservable'
    assert measured.vc_used_mps == pytest.approx(measured.closing_mps)   # measured Vc handed to PN


def test_range_aiding_does_not_fabricate_closing_on_static_target():
    # A constant-size silhouette (non-approaching) must NOT invent closing -> PN keeps scheduled Vc.
    pipe = SeekerGuidancePipeline(target_span_m=3.0)
    sources = []
    for k in range(50):
        out = pipe.step(now=k * DT, frame_u16=_frame_with_blob(320, 256, 6.0, seed=k),
                        gyro_omega_xyz=(0.0, 0.0, 0.0), dt=DT)
        sources.append(out.range_aiding_source)
    # Range may be measured (a static blob still has a range) but closing must never be trusted:
    # no frame promotes to a MEASURED Vc override on a non-closing target.
    assert "measured" not in sources
    assert all(s in ("inactive", "fallback") for s in sources)


def test_silhouette_extent_stays_monotonic_where_bbox_collapses():
    # THE TERMINAL FAILURE MODE the silhouette fixes: as the target grows into the FOV, detect_frame's
    # bbox is top-hat-suppressed and COLLAPSES (would make range spuriously INCREASE), while the
    # silhouette extent the range filter now uses keeps GROWING (range keeps honestly closing).
    pipe = SeekerGuidancePipeline(target_span_m=3.0)
    extents, bboxes = [], []
    for k in range(46):
        sigma = 3.0 + 0.5 * k                                  # grows 3 -> ~25 px: small -> fills the FOV
        out = pipe.step(now=k * DT, frame_u16=_frame_with_blob(320, 256, sigma, peak=3000.0, seed=k),
                        gyro_omega_xyz=(0.0, 0.0, 0.0), dt=DT)
        if out.extent_px is not None and out.bbox is not None:
            extents.append(out.extent_px)
            bboxes.append(float(max(out.bbox[2], out.bbox[3])))
    assert len(extents) >= 20
    # Silhouette span at the END (target filling) is much larger than at the START (small) -- monotone up.
    assert extents[-1] > 1.8 * extents[0]
    # The detector bbox, in contrast, does NOT keep growing: its peak is well before the end (it collapses
    # under top-hat suppression as the target fills). This is exactly why the range channel needs the
    # silhouette, not the bbox.
    assert max(bboxes) > bboxes[-1] + 3.0                      # bbox peaked then fell back
    assert extents[-1] > bboxes[-1]                            # silhouette recovers what the bbox lost
