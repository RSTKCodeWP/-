"""LAUNCH-AND-FORGET end-to-end proof: the WHOLE system closes and hits as ONE loop.

Unlike the piece-wise harnesses (sim3d_honest = physics loop but bypasses mission/auth/arming;
sil_runtime = full stack but open physics loop), this runs the REAL ProductionRuntime -- perception ->
mission FSM (acquire→ready→engage) -> REAL Ed25519 dual-signature -> arming -- inside an honest quad
closing loop with an up-looking camera. After the operator's two presses NOTHING external steers the
aircraft; it flies itself to contact. These tests pin that the autonomous chain actually closes.
"""

from __future__ import annotations

import pytest

from fpv_ai.bench.launch_and_forget import LaFConfig, run_launch_and_forget
from fpv_ai.betaflight_link.mission_fsm import MissionPhase

pytestmark = pytest.mark.slow

# NOTE (2026-07-19). Every PERFORMANCE assertion below passes ``camera_tilts_with_body=False`` -- a
# world-stabilised head, i.e. an ideal gimbal. That is what this harness silently modelled until the camera
# was made to tilt with the airframe, and it is the configuration these numbers were originally measured in.
# Keeping them means keeping a real result about a GIMBALLED build; it is not the strapdown build the
# doctrine currently specifies. The honest strapdown outcome is pinned separately, below.


def test_full_chain_closes_and_hits_body_to_body():
    """The complete stack -- perception + mission FSM + REAL dual-signed commit + arming -- autonomously
    closes on the target and reaches CPA within the capture radius. This is 'launch and forget' as one
    system, not a guidance snippet."""
    r = run_launch_and_forget(LaFConfig(seed=11, camera_tilts_with_body=False))
    assert r.hit and r.cpa_m <= LaFConfig().cap_m, f"expected body-to-body hit, CPA={r.cpa_m:.2f} m"
    assert r.armed_ai_active, "the dual-signed two-press must have driven arming to AI_ACTIVE"
    phases = [p for _, p in r.phases]
    assert MissionPhase.READY in phases and MissionPhase.ENGAGING in phases, phases  # studied -> committed -> flew
    assert r.lock_frames > 0.7 * r.n_ticks, f"tracker should hold most frames, {r.lock_frames}/{r.n_ticks}"


def test_arming_denied_without_the_two_press():
    """Default-DENY: with no operator authorization submitted, arming never reaches AI_ACTIVE and the
    aircraft is never flown -> it does NOT hit. The two-press is load-bearing, not decorative."""
    import fpv_ai.bench.launch_and_forget as laf

    class _NoAuth(laf.ProductionRuntime):
        def submit_authorization(self, envelope):        # swallow the commit -> operator never authorizes
            super().submit_authorization(envelope)
            from types import SimpleNamespace
            return SimpleNamespace(verifier_passed=False)

    orig = laf.ProductionRuntime
    laf.ProductionRuntime = _NoAuth
    try:
        r = run_launch_and_forget(LaFConfig(seed=11, camera_tilts_with_body=False))
    finally:
        laf.ProductionRuntime = orig
    assert not r.armed_ai_active, "arming must NOT reach AI_ACTIVE without a verified two-press"
    assert not r.hit, "with the aircraft never authorized to fly, it must not reach the target"


def test_hits_across_seeds():
    """The autonomous close is not a single lucky seed."""
    hits = [run_launch_and_forget(LaFConfig(seed=s, camera_tilts_with_body=False)).hit for s in (7, 23, 42)]
    assert all(hits), f"expected a hit on every seed, got {hits}"


def test_honest_maneuver_envelope_wall():
    """HONEST ENVELOPE: the 0.84 g quad plant intercepts a NON-maneuvering overhead target, but a target
    that weaves at ~0.4 g defeats it (miss grows to metres). This pins the real capability boundary of the
    hardware -- not a bug, a physics wall. If a future airframe raises the g ceiling this test should start
    failing; that's the signal the envelope widened."""
    calm = run_launch_and_forget(LaFConfig(seed=11, tgt_weave_g=0.0, camera_tilts_with_body=False))
    jinking = run_launch_and_forget(LaFConfig(seed=11, tgt_weave_g=0.6, camera_tilts_with_body=False))
    assert calm.hit, f"a calm overhead target must be hit, CPA={calm.cpa_m:.2f}"
    assert not jinking.hit and jinking.cpa_m > 2.0, (
        f"a 0.6 g weaving target must defeat the 0.84 g plant, got CPA={jinking.cpa_m:.2f}")


def test_survives_a_brief_occlusion():
    """The from-below close is forgiving: the pipeline's coast + momentum carry it through a target that is
    briefly occluded (behind a cloud) mid-flight -- it still hits. (MARCH's distinct value is the LONGER,
    off-frame loss proven in march_sim, not this short gap.)"""
    r = run_launch_and_forget(LaFConfig(seed=11, occl_start_s=0.7, occl_end_s=1.2, camera_tilts_with_body=False))
    assert r.hit, f"a 0.5 s occlusion should not defeat the close, CPA={r.cpa_m:.2f}"


def test_formal_commit_is_blocked_by_the_transient_g_abort_not_by_range():
    """Wiring passive range into the commit gate did NOT produce a formal COMMITTED, and this pins why.

    The engage-FSM aborts on a SINGLE-frame over-demand (bearing_rate raises ROEAbort the instant demand
    exceeds the envelope, with no persistence), and ABORTED is sticky -- so a transient spike at ~1.2 s ends
    the engagement while the target is still ~100 m out. The abort is also disabled post-commit by design,
    which makes it a deadlock: the abort prevents the commit that would have disabled the abort.

    Consequence, and the honest reading of this scenario: the recorded HIT is a post-abort ballistic coast on
    the collision course PN had already established -- NOT an authorized, committed, guided intercept.
    """
    from fpv_ai.bench.launch_and_forget import LaFConfig, run_launch_and_forget

    tight = run_launch_and_forget(LaFConfig(seed=11, passive_range=True, camera_tilts_with_body=False))
    assert tight.hit
    # NOTE: the original form of this test also asserted `not tight.committed`. That was true only while
    # the assumed target span was 2x the rendered one, which put measured range at ~2x truth so the 50 m
    # commit gate could never fire. With the span matched, this seed does now commit -- the deadlock this
    # test documents is still real (see the persistence comparison below), it just no longer manifests here.

    # Give the abort persistence (leaky accumulator) so a transient spike no longer ends the engagement.
    # NOTE this is opt-in, not the shipped default -- see GuidanceConfig.envelope_abort_persist_ticks for
    # why (it exposes a terminal blow-up in our perp-LOS law that the instant abort was masking).
    relaxed = run_launch_and_forget(LaFConfig(seed=11, passive_range=True, envelope_persist_ticks=25, camera_tilts_with_body=False))
    assert relaxed.committed, "with the transient abort ridden out, the formal chain closes"
    assert relaxed.hit


def test_passive_range_does_not_change_the_outcome_here():
    """Honest negative: on this near-collision-course geometry the interceptor barely moves across the LOS,
    so it never earns the parallax a passive range needs. Enabling it changes nothing -- which is the gate
    behaving correctly, not the feature failing."""
    from fpv_ai.bench.launch_and_forget import LaFConfig, run_launch_and_forget

    off = run_launch_and_forget(LaFConfig(seed=11, passive_range=False, camera_tilts_with_body=False))
    on = run_launch_and_forget(LaFConfig(seed=11, passive_range=True, camera_tilts_with_body=False))
    assert (off.hit, off.committed) == (on.hit, on.committed)
    assert abs(off.cpa_m - on.cpa_m) < 1e-9


def test_assumed_target_span_scales_the_subtense_range_and_can_disable_the_commit_gate():
    """Subtense range is f*ASSUMED_span/extent_px, so a wrong assumed span biases range proportionally --
    silently, with no symptom anywhere in the system.

    This actually bit us: the harness rendered a 2 m target while the runtime assumed 4 m, so measured range
    read ~2x truth and never crossed the 50 m commit gate (it bottomed out around 100 m while the true CPA
    was 1.4 m). In flight the true span of an unknown winged UAV is genuinely unknown, so this error class is
    unavoidable for subtense -- which is the whole case for the size-free passive parallax range.
    """
    from fpv_ai.bench.launch_and_forget import LaFConfig, run_launch_and_forget
    from fpv_ai.bench.sim3d import WINGSPAN_M
    from fpv_ai.production_runtime import ProductionConfig

    assert ProductionConfig().target_span_m != WINGSPAN_M, (
        "the runtime DEFAULT span still differs from what the scene renders -- the harness must pass "
        "target_span_m=WINGSPAN_M explicitly, which is exactly the bug this test guards")

    # With the span matched AND the abort given persistence, the formal chain closes on these seeds.
    committed = [run_launch_and_forget(LaFConfig(seed=s, envelope_persist_ticks=25, camera_tilts_with_body=False)).committed
                 for s in (7, 23, 42, 101)]
    assert all(committed), f"span-matched runs should reach formal COMMITTED, got {committed}"


def test_a_real_strapdown_head_does_not_close_this_intercept():
    """THE HONEST STRAPDOWN RESULT, pinned so it cannot go quiet again.

    Until 2026-07-19 this harness projected through ``fwd = rel[2]`` -- the boresight was nailed to world-up
    and never tilted with the airframe, i.e. it silently modelled an IDEAL GIMBAL. Every "launch-and-forget
    proven" number in this file was measured that way.

    With the camera actually strapped to the body (and a physical 0.10 s attitude lag, without which the
    camera teleports between commanded attitudes and reports impossible body rates), the same intercept
    FAILS on every seed: CPA ~2.4 m against a 1.5 m contact radius.

    The mechanism is measured, not assumed: body rotation writes a huge apparent LOS rate into the seeker
    (lambda-dot median ~2.5 rad/s vs ~0.03 rad/s for the stabilised head) while the target sits comfortably
    inside the frame (offset ~0.7 deg against a 19.9 deg half-FOV). The airframe's own motion, not the
    target's, dominates what the seeker reports.

    This independently reproduces the 2026-07-05 sim3d_honest result (gimbal ~1.1 m vs strapdown ~10 m) in
    a completely separate harness, which is why it is worth pinning.
    """
    from fpv_ai.bench.launch_and_forget import LaFConfig, run_launch_and_forget

    seeds = (7, 11, 23, 42, 101)
    strapdown = [run_launch_and_forget(LaFConfig(seed=s, camera_tilts_with_body=True)) for s in seeds]
    stabilised = [run_launch_and_forget(LaFConfig(seed=s, camera_tilts_with_body=False)) for s in seeds]

    assert all(r.hit for r in stabilised), "a stabilised (gimballed) head closes this intercept"
    assert not any(r.hit for r in strapdown), (
        "strapdown is expected to MISS here; if this starts passing, something real improved -- "
        f"verify it before celebrating. CPA={[round(r.cpa_m, 2) for r in strapdown]}")

    worst_stab = max(r.cpa_m for r in stabilised)
    best_strap = min(r.cpa_m for r in strapdown)
    assert best_strap > worst_stab, "the two configurations must not overlap -- the gap is the whole finding"


def test_a_real_gimbal_closes_the_intercept():
    """THE MEASUREMENT THAT FILLED THE EMPTY CELL.

    Five independent lines of evidence said strapdown is the binding problem, but the configuration they
    pointed at had never been measured end to end. This is that measurement, and it is a REAL gimbal, not
    the idealisation: servo slew-rate limit and lag from ``fpv.gimbal.plant`` (500 deg/s, 0.01 s), and it
    steers on the centroid THE SEEKER ITSELF reports -- a closed perception loop that never sees truth.
    When unlocked it holds inertial attitude, as a stabilised head does.

    Result across 10 seeds: 10/10 hits, mean CPA 1.23 m (1.11-1.44), lock 90%, arming 10/10 -- against
    strapdown's 0/5 at CPA ~2.4 m on the same harness.

    The enabling piece is subtle and worth stating: a tracking gimbal makes full ego-compensation
    ARCHITECTURALLY REQUIRED. The head rotates to hold the target centred, so image motion is
    (true LOS motion - head motion) -- the tracking cancels exactly the signal guidance needs. Feeding the
    head's own inertial rate back reconstructs it. Without that the same gimbal scores 0/5 at CPA 2.52.
    """
    from fpv_ai.bench.launch_and_forget import LaFConfig, run_launch_and_forget

    seeds = (7, 11, 23, 42, 101)
    gimbal = [run_launch_and_forget(LaFConfig(seed=s, mount="gimbal")) for s in seeds]
    strapdown = [run_launch_and_forget(LaFConfig(seed=s, mount="strapdown")) for s in seeds]

    assert all(r.hit for r in gimbal), (
        f"a real gimbal should close this intercept, CPA={[round(r.cpa_m, 2) for r in gimbal]}")
    assert all(r.armed_ai_active for r in gimbal), "the two-press authority must still be what arms it"
    assert not any(r.hit for r in strapdown), "and strapdown must still miss -- the gap is the finding"


def test_the_gimbal_result_still_requires_the_two_press():
    """Load-bearing negative control: the gimbal improves the SEEKER, not the authority. Without a valid
    dual-signed commit it must still never arm and never reach the target."""
    from fpv_ai.bench.launch_and_forget import LaFConfig, run_launch_and_forget
    import fpv_ai.bench.launch_and_forget as laf

    real_sign = laf.sign_commit
    laf.sign_commit = lambda payload, keys: real_sign(payload, keys[:1])   # one signature, not two
    try:
        r = run_launch_and_forget(LaFConfig(seed=11, mount="gimbal"))
    finally:
        laf.sign_commit = real_sign
    assert not r.armed_ai_active, "a single signature must not arm the aircraft"
    assert not r.hit, "and without arming it must not reach the target"


def test_clutter_and_side_aspect_are_honestly_open_gaps():
    """HONEST BOUNDARIES, pinned so they cannot be silently overclaimed. Measured 2026-07-20.

    The gimbal build closes the DESIGN case (from-below, overhead, clean sky, weakly-maneuvering): 3/3.
    It does NOT close two cases the operator will meet in the field, and these tests record that:

    1. CLUTTER: a single confuser as bright as the target, near its bearing, breaks the naive tracker
       (the gimbal gets pulled onto it). The discrimination features (correlation/JPDA/consensus) exist but
       are UNTUNED for this synthetic scene -- they prevent the target locking at all. So clutter robustness
       is genuinely unresolved here; it needs REAL thermal (real_ingest / HIL), not this render.

    2. SIDE-ASPECT CROSSING: a winged UAV seen from the side, cued from the ground, is acquired and commits,
       but lock retention collapses (~22%) and it misses. Root cause is NOT the gimbal (an ideal head scores
       the same) and not primarily the g-wall: a crossing target that drops lock for even a moment crosses
       out of frame and is not reacquired. MARCH (the dead-reckon slew that fixes exactly this) is not wired
       into this loop.
    """
    from fpv_ai.bench.launch_and_forget import LaFConfig, run_launch_and_forget

    clean = [run_launch_and_forget(LaFConfig(seed=s, mount="gimbal")) for s in (7, 11, 23)]
    assert all(r.hit for r in clean), "the clean from-below design case must still close"

    # one bright confuser near the bearing breaks the naive tracker (records the gap, not a target)
    cluttered = [run_launch_and_forget(LaFConfig(seed=s, mount="gimbal", n_decoys=1,
                                                 decoy_intensity=0.6, netd_scale=1.3, clutter_std=3.0))
                 for s in (7, 11, 23)]
    assert sum(r.hit for r in cluttered) < len(cluttered), (
        "if clutter no longer breaks the naive tracker, real discrimination was tuned in -- update this test")

    # side-aspect crossing UAV, ground-cued: acquires but does not hold lock / does not hit
    crossing = [run_launch_and_forget(LaFConfig(seed=s, mount="gimbal", cue_gimbal_at_target=True,
                                                tgt_pos=(40.0, 5.0, 80.0), tgt_vel=(-18.0, 0.0, -2.0),
                                                tmax=8.0))
                for s in (7, 11, 23)]
    assert not any(r.hit for r in crossing), (
        "if the side-aspect crossing case now closes, something real improved (MARCH wired in?) -- verify it")
