"""Tests for the Confirmation rule + world-clustering (Task 3.6).

Confirmation is a RULE ON THE TRACK (not a framework): persistence + accumulated
confidence + world-location clustering promote a track's DISPLAY-PRIORITY TIER
(contact → candidate → strong). It NEVER gates visibility — every detection above a low
threshold surfaces immediately as a faint "contact"; only the tier changes. Downstream,
the Localizer (Phase 4) runs on confirmed/promoted contacts, so a false "strong" confirm
is the cardinal sin (a rescue team sent to an empty coordinate), and a missed real
survivor is equally catastrophic (recall-first doctrine).

Design (hardened by an adversarial red-team panel):
- The promotion DRIVER is a leaky-integrator decay score (score←score*decay; score+=conf
  on a hit). A pure N-of-M count is defeated by a resonant flicker that hits exactly on
  the window boundary; the decay accumulator starves sparse flicker between bursts. The
  human-legible `hits in last M` is kept as a floor / display number.
- Schmitt hysteresis: promote at θ_up, demote only below θ_down (< θ_up); the decay coast
  carries a contact through a short occlusion; a demote never deletes the contact.
- World-cluster corroboration counts ONE centroid vote per track (never per-frame points —
  that would be fake self-corroboration) and drops duplicate detector firings (two track
  IDs whose boxes co-occur with high IoU = one source, not two corroborators).
- Only gate-PASSING ground points corroborate; gated-out points keep the track VISIBLE
  but don't vote.

KNOWN LIMITATION (documented, not handled): persistence+clustering is a consistency
filter, not a semantic classifier — a STABLE false positive (AC unit / sun glint the
detector reliably fires on) WILL reach "strong." "Strong" means "worth a human look,"
never autonomous dispatch. See `test_stable_false_positive_is_a_known_limitation`.
"""

from __future__ import annotations

from hades.confirm.confirmation import Confirmation, Tier
from hades.detect.detector import Detection
from hades.locate.frame_gate import GateVerdict
from hades.locate.projector import GroundPoint


def _gp(track_lat, track_lon, conf=0.9, verdict=GateVerdict.PASS, box=(940.0, 900.0, 980.0, 960.0)):
    """A gate-passing ground point for a synthetic track (box drives IoU de-dup)."""
    det = Detection(box_xyxy=box, conf=conf)
    return GroundPoint(
        detection=det, lat=track_lat, lon=track_lon, conf=conf, verdict=verdict
    )


def _feed(conf_rule, track_observations, *, slant_range=100.0):
    """Drive Confirmation frame-by-frame.

    `track_observations` is a list (one per frame) of dict {track_id: GroundPoint|None};
    None means that track was not detected this frame (a miss). Returns the final tier map.
    """
    tiers = {}
    for frame in track_observations:
        present = {tid: gp for tid, gp in frame.items() if gp is not None}
        tiers = conf_rule.update(present, slant_range=slant_range)
    return tiers


# --- visibility is NEVER gated ----------------------------------------------


def test_single_glimpse_is_visible_as_contact():
    # The one-frame glimpse through a debris gap MUST surface immediately (recall-first).
    conf = Confirmation()
    tiers = conf.update({1: _gp(0.0, 0.0)}, slant_range=100.0)
    assert tiers[1] is Tier.CONTACT  # visible, lowest tier — never suppressed


def test_gated_out_detection_still_visible_but_not_corroborating():
    # A REJECT-gated point keeps the track visible (contact) but does not vote in clusters.
    conf = Confirmation()
    rejected = _gp(0.0, 0.0, verdict=GateVerdict.REJECT)
    tiers = conf.update({1: rejected}, slant_range=100.0)
    assert tiers[1] is Tier.CONTACT  # still visible
    assert conf.cluster_vote_count() == 0  # gated-out point cast no corroboration vote


# --- persistence promotes a real, stable survivor ---------------------------


def test_persistent_high_conf_track_promotes_to_candidate_then_strong():
    conf = Confirmation()
    # A real survivor seen every frame at a tight ground point.
    obs = [{1: _gp(0.0, 0.0, conf=0.9)} for _ in range(40)]
    tiers = _feed(conf, obs)
    assert tiers[1] is Tier.STRONG  # solo very-persistent high-conf path


def test_candidate_reached_before_strong():
    conf = Confirmation()
    # A few frames in, it should be candidate but not yet strong.
    tiers = {}
    for _ in range(6):
        tiers = conf.update({1: _gp(0.0, 0.0, conf=0.7)}, slant_range=100.0)
    assert tiers[1] in (Tier.CONTACT, Tier.CANDIDATE)
    assert tiers[1] is not Tier.STRONG


# --- world-clustering: fragmented tracks corroborate ------------------------


def test_fragmented_sequential_tracks_corroborate_to_strong():
    # Ego-motion fragments ONE survivor into sequential short track IDs at the same spot.
    # The relay should world-cluster and reach strong even though no single track is long.
    conf = Confirmation()
    tiers = {}
    # Track 7 lives frames 0-9, then dies; track 12 picks up the same ground point 10-19.
    for _ in range(10):
        tiers = conf.update({7: _gp(0.0001, 0.0001, conf=0.8)}, slant_range=100.0)
    for _ in range(10):
        tiers = conf.update({12: _gp(0.0001, 0.0001, conf=0.8)}, slant_range=100.0)
    # The later track, corroborated by the earlier one at the same world point, is strong.
    assert tiers[12] is Tier.STRONG


def test_duplicate_detector_firings_do_not_fake_corroborate():
    # Two CONCURRENT track IDs whose BOXES overlap heavily = ONE detector stuttering, not
    # two corroborators. They must NOT manufacture a strong confirm from a single source.
    conf = Confirmation()
    box = (940.0, 900.0, 980.0, 960.0)
    tiers = {}
    for _ in range(15):
        # Same box (IoU≈1) → de-duplicated to one corroboration vote.
        tiers = conf.update(
            {
                1: _gp(0.0, 0.0, conf=0.5, box=box),
                2: _gp(0.0, 0.0, conf=0.5, box=box),
            },
            slant_range=100.0,
        )
    # Neither low-confidence duplicate should reach strong via fake mutual corroboration.
    assert tiers[1] is not Tier.STRONG
    assert tiers[2] is not Tier.STRONG


# --- adversarial flicker: the hardest false-confirm tests -------------------


def test_resonant_boundary_flicker_never_confirms():
    # The aliasing attack: a periodic 1-hit-then-3-miss pattern engineered to keep exactly
    # N hits in every M-frame window. A pure N-of-M count promotes it forever; the decay
    # accumulator starves it between bursts so it never reaches strong.
    conf = Confirmation()
    tiers = {}
    for k in range(80):
        present = {1: _gp(0.0, 0.0, conf=0.9)} if k % 4 == 0 else {}
        tiers = conf.update(present, slant_range=100.0)
    assert tiers.get(1) is not Tier.STRONG


def test_burst_then_vanish_decays_out_of_strong():
    # A transient ghost (sun glint as the aircraft banks): 12 hits then gone. It may touch
    # candidate briefly, but once the source vanishes the tier must DECAY back down — a
    # real survivor reacquires; a ghost does not.
    conf = Confirmation()
    tiers = {}
    for _ in range(12):
        tiers = conf.update({1: _gp(0.0, 0.0, conf=0.9)}, slant_range=100.0)
    # Now it vanishes for a long stretch.
    for _ in range(40):
        tiers = conf.update({}, slant_range=100.0)
    assert tiers.get(1) is not Tier.STRONG  # decayed back down, not latched


def test_walking_phantom_jitter_does_not_cluster():
    # A flicker track whose ground point DRIFTS meters/frame (low oblique detection on a
    # moving wave crest): decent hit-ratio but large centroid scatter, never co-locates
    # with a second independent source → must not reach strong.
    conf = Confirmation()
    tiers = {}
    for k in range(40):
        # Drift the ground point ~3 m/frame (≈3e-5 deg) — never a stable cluster.
        lat = 0.0 + k * 3e-5
        tiers = conf.update({1: _gp(lat, 0.0, conf=0.6)}, slant_range=400.0)
    assert tiers.get(1) is not Tier.STRONG


# --- hysteresis: no tier flapping; sticky operator promote ------------------


def test_strong_contact_coasts_through_short_occlusion():
    # A dispatched survivor briefly occluded behind debris must NOT immediately demote —
    # the decay coast carries it through a few missed frames (pin stays stable).
    conf = Confirmation()
    tiers = {}
    for _ in range(40):
        tiers = conf.update({1: _gp(0.0, 0.0, conf=0.9)}, slant_range=100.0)
    assert tiers[1] is Tier.STRONG
    # 3-frame occlusion.
    for _ in range(3):
        tiers = conf.update({}, slant_range=100.0)
    assert tiers[1] is Tier.STRONG  # coasted, did not flap down


def test_operator_promote_is_sticky_against_auto_demote():
    # A human decision outranks the algorithm: an operator-promoted contact is not silently
    # auto-demoted when detections stop (the human-as-confirmer path, M6).
    conf = Confirmation()
    conf.update({1: _gp(0.0, 0.0, conf=0.9)}, slant_range=100.0)
    conf.operator_promote(1)
    tiers = {}
    for _ in range(50):  # source vanishes entirely
        tiers = conf.update({}, slant_range=100.0)
    assert tiers[1] is Tier.STRONG  # human lock holds


# --- known limitation (documented, asserted as current behavior) ------------


def test_stable_false_positive_is_a_known_limitation():
    # A reliably-detected NON-person (AC unit / glint) is indistinguishable from a survivor
    # to a consistency filter — it WILL reach strong. This test pins the limitation so it
    # is documented, not pretended-away: "strong" means "worth a human look," not truth.
    conf = Confirmation()
    obs = [{1: _gp(0.0, 0.0, conf=0.95)} for _ in range(40)]  # rock-stable false detection
    tiers = _feed(conf, obs)
    assert tiers[1] is Tier.STRONG  # the rule cannot tell this from a real survivor


# --- cluster radius scales with range ---------------------------------------


def test_dead_tracks_are_evicted_no_unbounded_growth():
    # Review H1: the internal track dict must not grow forever. Feed many distinct
    # one-frame track IDs (the fragmentation churn the relay scenario celebrates); after
    # they've been silent past the eviction horizon, they must be evicted — otherwise a
    # long mission leaks memory and dead-strong ghosts keep emitting / corroborating.
    conf = Confirmation()
    for tid in range(200):
        conf.update({tid: _gp(0.0, 0.0, conf=0.9)}, slant_range=100.0)
    # Let everything go silent well past the window.
    for _ in range(40):
        conf.update({}, slant_range=100.0)
    assert conf.live_track_count() < 50  # bounded, not 200+


def test_dead_strong_ghost_does_not_corroborate_later_false_positive():
    # Review H1: a track that was STRONG long ago must not keep voting in clusters after it
    # dies. A present-day lone low-score track at the old coordinate must not be promoted
    # to STRONG by the ghost of a track that vanished many frames earlier.
    conf = Confirmation()
    for _ in range(40):  # track A → strong at the origin
        conf.update({1: _gp(0.0, 0.0, conf=0.9)}, slant_range=100.0)
    for _ in range(60):  # A vanishes entirely, long enough to be evicted
        conf.update({}, slant_range=100.0)
    # A new lone track B appears at the same spot; with A gone it must NOT be corroborated.
    tiers = {}
    for _ in range(6):
        tiers = conf.update({2: _gp(0.0, 0.0, conf=0.6)}, slant_range=100.0)
    assert tiers[2] is not Tier.STRONG


def test_duplicate_source_identity_persists_beyond_window():
    # Review H2: de-dup must not FORGET that two tracks were one detector source once their
    # co-occurrence frames age out of the window. Co-occur briefly, then one fires alone
    # past the window, then both again — the duplicate must still not fake-corroborate.
    conf = Confirmation()
    box = (940.0, 900.0, 980.0, 960.0)
    tiers = {}
    for _ in range(3):  # co-occur (IoU≈1) → one source
        tiers = conf.update(
            {1: _gp(0.0, 0.0, conf=0.5, box=box), 2: _gp(0.0, 0.0, conf=0.5, box=box)},
            slant_range=100.0,
        )
    for _ in range(35):  # track 1 alone, aging the co-occurrence out of the window
        tiers = conf.update({1: _gp(0.0, 0.0, conf=0.5, box=box)}, slant_range=100.0)
    tiers = conf.update({2: _gp(0.0, 0.0, conf=0.5, box=box)}, slant_range=100.0)
    assert tiers[1] is not Tier.STRONG  # not promoted by its own remembered duplicate


def test_close_distinct_survivors_with_overlapping_boxes_still_corroborate():
    # Review M4: two GENUINELY distinct survivors standing close (boxes overlap) but at
    # DISTINCT ground points must still be allowed to corroborate — de-dup keys on world
    # position too, not box-IoU alone, so it doesn't suppress real adjacent people.
    conf = Confirmation()
    # Boxes overlap heavily, but the centroids are a real ~25 m apart on the ground.
    box_a = (900.0, 900.0, 960.0, 980.0)
    box_b = (930.0, 900.0, 990.0, 980.0)  # IoU with box_a > 0.5
    a_lat, b_lat = 0.0, 2.2e-4  # ≈ 25 m apart
    tiers = {}
    for _ in range(20):
        tiers = conf.update(
            {1: _gp(a_lat, 0.0, conf=0.7, box=box_a),
             2: _gp(b_lat, 0.0, conf=0.7, box=box_b)},
            slant_range=900.0,  # long range → radius covers 25 m
        )
    assert tiers[1] is Tier.STRONG  # real adjacent survivors corroborate, not de-duped away


def test_degenerate_slant_range_does_not_explode_radius():
    # Review M3: a pathological slant_range (negative or huge from a bad pose) must not make
    # the cluster radius nonsensical. Two tracks 5 km apart must never corroborate, even
    # with an absurd slant_range that a naive base + k·range would turn into a 50,000 km
    # radius.
    conf = Confirmation()
    far_box = (100.0, 100.0, 140.0, 180.0)
    tiers = {}
    for _ in range(20):
        tiers = conf.update(
            {1: _gp(0.0, 0.0, conf=0.7),
             2: _gp(0.045, 0.0, conf=0.7, box=far_box)},  # ~5 km apart
            slant_range=1e9,  # absurd
        )
    assert tiers[1] is not Tier.STRONG  # the radius is clamped; 5 km never corroborates


def test_alternating_duplicate_source_does_not_self_corroborate():
    # Codex P1 (confirmation): two alternating track IDs from ONE flickering false source
    # that NEVER co-occur in a frame (so the same-frame de-dup never fires) must not
    # mutually corroborate into STRONG. A rapidly-interleaved pair at one spot is one
    # source; only a temporally-separated relay (a hand-off) is genuine corroboration.
    conf = Confirmation()
    box = (940.0, 900.0, 980.0, 960.0)
    tiers = {}
    for k in range(60):
        tid = 1 if k % 2 == 0 else 2  # alternate, never in the same frame
        tiers = conf.update({tid: _gp(0.0, 0.0, conf=0.9, box=box)}, slant_range=100.0)
    assert tiers.get(1) is not Tier.STRONG
    assert tiers.get(2) is not Tier.STRONG


def test_all_gated_out_track_never_reaches_strong():
    # Codex P1 (confirmation:153): a track whose points are ALL gate-REJECT (e.g. a
    # persistent above-horizon / oblique false positive) accrues score but has no valid
    # fused coordinate. It must never reach STRONG — STRONG would dispatch a team to a
    # coordinate that does not exist. It stays visible (CONTACT), just never dispatchable.
    conf = Confirmation()
    tiers = {}
    for _ in range(40):
        rejected = _gp(0.0, 0.0, conf=0.95, verdict=GateVerdict.REJECT)
        tiers = conf.update({1: rejected}, slant_range=100.0)
    assert tiers[1] is not Tier.STRONG


def test_unprojectable_track_never_reaches_strong():
    # Codex P1 (confirmation:153): a track with no coordinate (lat/lon None — un-projectable
    # every frame) must not reach STRONG either. No coordinate ⇒ nothing to dispatch to.
    conf = Confirmation()
    tiers = {}
    for _ in range(40):
        no_coord = GroundPoint(
            detection=Detection(box_xyxy=(940.0, 900.0, 980.0, 960.0), conf=0.95),
            lat=None, lon=None, conf=0.95, verdict=GateVerdict.PASS_UNVERIFIED,
        )
        tiers = conf.update({1: no_coord}, slant_range=100.0)
    assert tiers[1] is not Tier.STRONG


def test_cluster_radius_scales_with_slant_range():
    # Two tracks 30 m apart corroborate at long oblique range (loose radius) but not at
    # short nadir range (tight radius) — fixed R would mis-handle one regime.
    conf_near = Confirmation()
    conf_far = Confirmation()
    # Ground points ~30 m apart (≈2.7e-4 deg lat).
    a, b = 0.0, 2.7e-4
    near_tiers = far_tiers = {}
    for _ in range(20):
        near_tiers = conf_near.update(
            {1: _gp(a, 0.0, conf=0.7), 2: _gp(b, 0.0, conf=0.7,
             box=(100.0, 100.0, 140.0, 180.0))},
            slant_range=80.0,
        )
        far_tiers = conf_far.update(
            {1: _gp(a, 0.0, conf=0.7), 2: _gp(b, 0.0, conf=0.7,
             box=(100.0, 100.0, 140.0, 180.0))},
            slant_range=900.0,
        )
    # At long range the 30 m gap is within the scaled radius → corroborated → strong.
    assert far_tiers[1] is Tier.STRONG
    # At short range 30 m exceeds the tight radius → not corroborated → not strong.
    assert near_tiers[1] is not Tier.STRONG
