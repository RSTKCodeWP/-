"""Phase 6 Task 6.1 — the baked demo mission must be REAL pipeline output, honest, and
schema-faithful both ways.

The demo site replays a static `mission.json` through the same React UI the live service
drives. The danger the adversarial panel flagged: a hand-authored mission, a Null-Island
pin from a None→0.0 slip, a NaN that detonates `JSON.parse`, or a frame/JSON misalignment
that silently draws zero boxes. These tests pin the honest-and-correct contract.

`build_mission()` drives the REAL `Projector`/`Fuser` with full-attitude poses from the P4
simulator (`locate/geom_sim`) against KNOWN ground-truth survivors, so every pin/ellipse/R95
is genuine localizer output — not a hand-drawn coordinate. The mix is deliberately honest:
an orbit (aspect diversity → PINPOINT), a straight pass (heading-limited → SWEEP), and one
position-only track (no fix → CUE_ONLY with null coordinate).
"""

from __future__ import annotations

import json
import math

import pytest

from hades.cli.record_mission import build_mission
from hades.ws.schema import ContactRecord, DetectionMessage


@pytest.fixture(scope="module")
def mission() -> dict:
    # A fixed seed keeps the bake deterministic (the demo + Playwright must reproduce).
    return build_mission(seed=0)


def _contacts(mission: dict) -> list[dict]:
    return [m for m in mission["json"] if m["type"] == "contact"]


def _detections(mission: dict) -> list[dict]:
    return [m for m in mission["json"] if m["type"] == "detection"]


def test_mission_has_frames_and_json(mission: dict) -> None:
    assert mission["frames"], "no frames baked — the video panel would be empty"
    assert mission["json"], "no JSON messages baked"
    # provenance is the honesty block the demo banner reads.
    prov = mission["provenance"]
    assert prov["scene"] == "synthetic"
    assert prov["pipeline"] == "real"
    assert math.isfinite(prov["median_error_m"]) and prov["median_error_m"] >= 0.0


def test_every_contact_roundtrips_through_the_real_schema(mission: dict) -> None:
    """Each baked contact must validate as a real `ContactRecord` (Python↔JSON, both ways)."""
    for raw in _contacts(mission):
        rec = ContactRecord.model_validate(raw)
        # round-trip back out and in again — model_dump → json → model_validate is stable.
        again = ContactRecord.model_validate_json(rec.model_dump_json())
        assert again == rec


def test_every_detection_roundtrips_through_the_real_schema(mission: dict) -> None:
    for raw in _detections(mission):
        DetectionMessage.model_validate(raw)


def test_at_least_one_located_contact_with_finite_r95(mission: dict) -> None:
    """The whole point of the demo: REAL pins. At least one contact has a non-null fix and a
    finite R95 (an empty/CUE-only map is the failure the panel warned about)."""
    located = [
        c for c in _contacts(mission)
        if c["lat"] is not None and c["lon"] is not None
    ]
    assert located, "no located contacts — the demo map would have zero pins"
    for c in located:
        assert math.isfinite(c["r95_m"]) and c["r95_m"] > 0.0
        assert math.isfinite(c["lat"]) and math.isfinite(c["lon"])


def test_has_an_honest_cue_only_contact(mission: dict) -> None:
    """Honesty: a position-only track surfaces as CUE_ONLY with a NULL coordinate — never a
    Null-Island (0,0) pin. null must STAY null through serialization."""
    cue = [c for c in _contacts(mission) if c["actionability_class"] == "CUE_ONLY"]
    assert cue, "no CUE_ONLY contact — the demo omits the honest no-fix case"
    for c in cue:
        assert c["lat"] is None and c["lon"] is None


def test_mix_includes_pinpoint_and_sweep(mission: dict) -> None:
    """The believable + honest distribution the demo-craft panel required: not all-PINPOINT
    (reads as fake), and a heading-limited SWEEP to show the uncertainty story."""
    classes = {c["actionability_class"] for c in _contacts(mission)}
    assert "PINPOINT" in classes
    assert "SWEEP" in classes


def test_no_nan_or_inf_anywhere(mission: dict) -> None:
    """NaN/Inf are invalid JSON; `Python json.dumps` emits literal NaN which `JSON.parse`
    REJECTS — a hard parse failure that blanks the whole demo. Forbid them outright."""
    text = json.dumps(mission)  # would raise only on un-encodable types, not NaN — so scan:
    assert "NaN" not in text
    assert "Infinity" not in text


def test_every_json_frame_id_has_a_matching_frame(mission: dict) -> None:
    """The silent-no-boxes killer: VideoPanel draws a box only when det.frame_id ==
    frame.frame_id. Every JSON message's frame_id must exist on the frame channel, and at
    least one detection must coincide with a baked frame so a box actually draws."""
    frame_ids = {f["frame_id"] for f in mission["frames"]}
    for m in mission["json"]:
        assert m["frame_id"] in frame_ids, f"orphan frame_id {m['frame_id']} draws nothing"
    det_ids = {d["frame_id"] for d in _detections(mission) if d["boxes"]}
    assert det_ids & frame_ids, "no detection coincides with a frame — zero boxes ever draw"


def test_frames_carry_real_frame_id_and_share_one_inlined_jpeg(mission: dict) -> None:
    """Frames are tagged with the REAL wire frame_id (NOT a local 0..n counter), so the
    file-source emits the cross-channel join key. The looped still is inlined ONCE at the top
    level (one fetch, no per-frame duplication) — not repeated on every frame."""
    assert isinstance(mission["frame_jpeg_b64"], str) and mission["frame_jpeg_b64"]
    for f in mission["frames"]:
        assert isinstance(f["frame_id"], int)
        assert "timestamp" in f
        assert "jpeg_b64" not in f, "per-frame bytes would bloat mission.json ~Nx"
    # the baked frame_ids should be the real pipeline seq, contiguous from 0 here.
    ids = sorted(f["frame_id"] for f in mission["frames"])
    assert ids == list(range(len(ids)))


def test_baked_link_lost_and_refined_promote_events(mission: dict) -> None:
    """Two scripted demo moments the panel wanted, driven from the timeline (not a fake
    socket): a LINK-LOST window and a pre-computed refined record for the promote demo."""
    assert mission["link_lost"], "no baked LINK-LOST window — the degrade-visibly moment is lost"
    lo, hi = mission["link_lost"]["from_frame"], mission["link_lost"]["to_frame"]
    assert 0 <= lo < hi
    refined = mission["promote_refined"]
    assert refined is not None
    rec = ContactRecord.model_validate(refined)
    # the refined record is a REAL fused estimate (located, tighter) — honest promote replay.
    assert rec.lat is not None and rec.r95_m > 0.0
