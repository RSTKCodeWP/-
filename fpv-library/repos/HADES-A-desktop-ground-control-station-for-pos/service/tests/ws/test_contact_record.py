"""Tests for the taskable ContactRecord WS message (Task 4.6; research gate §9).

ContactRecord is the localized, taskable contact on the JSON channel, `frame_id`-aligned to
video like DetectionMessage. The schema is the MINIMUM honest set the localizer can populate
today (research gate §9); deferred fields (clearance_state, snapshot+delta, cluster_id) are
NOT here - adding JSON fields later is cheap and backward-compatible, inventing fields the
localizer cannot fill is not.

The record round-trips and schema-validates at the process boundary (the §3.2 bug-class
guard: a malformed contact fails loudly here, not as a wrong coordinate downstream).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hades.ws.schema import ContactRecord


def _valid_kwargs():
    return dict(
        frame_id=42,
        track_id=7,
        lat=40.0,
        lon=-74.0,
        r95_m=8.5,
        actionability_class="SWEEP",
        semi_major_m=12.0,
        semi_minor_m=4.0,
        orientation_deg=33.0,
        priority_tier="strong",
        convergence_state="CONVERGING",
        heading_limited=True,
        aspect_spread_deg=15.0,
        detection_conf=0.9,
        localization_conf=0.6,
        mc_reject_fraction=0.0,
        moving_suspected=False,
        age_frames=120,
    )


def test_valid_record_round_trips_through_json():
    rec = ContactRecord(**_valid_kwargs())
    blob = rec.model_dump_json()
    back = ContactRecord.model_validate_json(blob)
    assert back == rec
    assert back.type == "contact"  # the discriminator for UI routing


def test_lat_lon_order_and_types():
    rec = ContactRecord(**_valid_kwargs())
    # (lat, lon) order per DESIGN.md §3.1 — lat first, both degrees.
    assert rec.lat == pytest.approx(40.0)
    assert rec.lon == pytest.approx(-74.0)


def test_frame_id_must_be_non_negative():
    with pytest.raises(ValidationError):
        ContactRecord(**{**_valid_kwargs(), "frame_id": -1})


def test_actionability_class_is_constrained():
    for cls in ("PINPOINT", "SWEEP", "AREA", "CUE_ONLY"):
        ContactRecord(**{**_valid_kwargs(), "actionability_class": cls})
    with pytest.raises(ValidationError):
        ContactRecord(**{**_valid_kwargs(), "actionability_class": "MAYBE"})


def test_priority_tier_is_constrained():
    for tier in ("contact", "candidate", "strong"):
        ContactRecord(**{**_valid_kwargs(), "priority_tier": tier})
    with pytest.raises(ValidationError):
        ContactRecord(**{**_valid_kwargs(), "priority_tier": "definitely"})


def test_convergence_state_is_constrained():
    for st in ("CONVERGING", "STABLE"):
        ContactRecord(**{**_valid_kwargs(), "convergence_state": st})
    with pytest.raises(ValidationError):
        ContactRecord(**{**_valid_kwargs(), "convergence_state": "DONE"})


def test_confidences_are_separate_axes_in_unit_range():
    # detection_conf and localization_conf are SEPARATE axes (research gate §9): a contact
    # can be confidently DETECTED but poorly LOCALIZED (heading-limited). Both in [0, 1].
    rec = ContactRecord(**{**_valid_kwargs(), "detection_conf": 0.95, "localization_conf": 0.2})
    assert rec.detection_conf != rec.localization_conf
    with pytest.raises(ValidationError):
        ContactRecord(**{**_valid_kwargs(), "localization_conf": 1.5})


def test_negative_radius_rejected():
    with pytest.raises(ValidationError):
        ContactRecord(**{**_valid_kwargs(), "r95_m": -1.0})


def test_deferred_fields_are_absent():
    # §9 explicitly DEFERS these to v1.x — they must not be in the v1 schema (the localizer
    # cannot honestly populate them yet). Locks the minimum-honest boundary.
    fields = set(ContactRecord.model_fields)
    for deferred in ("clearance_state", "snapshot_on_dispatch_coord", "cluster_id"):
        assert deferred not in fields


def test_from_fused_estimate_adapter():
    # The emit-side adapter builds a ContactRecord from a FusedEstimate + the per-track
    # metadata (track_id, tier, detection_conf, frame_id, age) the loop owns.
    from hades.locate.fuse import ConvergenceState

    rec = ContactRecord.from_fused(
        frame_id=10,
        track_id=3,
        coord=(40.1, -74.2),
        r95_m=6.0,
        actionability_class="SWEEP",
        semi_major_m=9.0,
        semi_minor_m=3.0,
        orientation_deg=10.0,
        convergence=ConvergenceState.CONVERGING,
        heading_limited=True,
        aspect_spread_deg=12.0,
        moving_suspected=False,
        mc_reject_fraction=0.01,
        priority_tier="strong",
        detection_conf=0.88,
        localization_conf=0.5,
        age_frames=30,
    )
    assert rec.track_id == 3
    assert rec.lat == pytest.approx(40.1)
    assert rec.convergence_state == "CONVERGING"
