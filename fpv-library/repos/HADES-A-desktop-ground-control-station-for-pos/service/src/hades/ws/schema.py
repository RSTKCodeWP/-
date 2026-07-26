"""WebSocket message contracts (pydantic → JSON Schema) — the cross-process boundary.

Two localhost channels, aligned by `frame_id` (== the FrameSource `seq`): a binary
channel of JPEG frames and this JSON channel. `DetectionMessage` is the Phase-2 JSON
payload — the per-frame boxes the UI overlays. `ContactRecord` (the taskable localized
record) is added in Phase 4 on the same channel.

These models ARE the schema: validation happens at the process boundary so a malformed
message fails loudly here instead of flowing downstream as a wrong coordinate (the
DESIGN.md §3.2 bug class). Boxes are `box_xyxy` in **original-frame pixels**, `(x_min,
y_min, x_max, y_max)`, confidence in `[0, 1]` — same convention as `detect.Detection`.
The pydantic models export to JSON Schema (`model_json_schema()`) for the UI side.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hades.detect.detector import Detection
    from hades.locate.fuse import ConvergenceState


class BoxMessage(BaseModel):
    """One detected box on the wire — mirrors `detect.Detection` (DESIGN.md §3.2)."""

    model_config = ConfigDict(frozen=True)

    box_xyxy: tuple[float, float, float, float]
    conf: float = Field(ge=0.0, le=1.0)
    cls: str = "person"

    @model_validator(mode="after")
    def _check_box_ordered(self) -> BoxMessage:
        x_min, y_min, x_max, y_max = self.box_xyxy
        if x_max <= x_min or y_max <= y_min:
            raise ValueError(
                f"box_xyxy must be ordered with positive area "
                f"(x_min<x_max, y_min<y_max): {self.box_xyxy}"
            )
        return self


class DetectionMessage(BaseModel):
    """Per-frame detections on the JSON channel, aligned to video by `frame_id`."""

    model_config = ConfigDict(frozen=True)

    type: Literal["detection"] = "detection"
    frame_id: int = Field(ge=0, description="FrameSource seq this message belongs to")
    timestamp: float = Field(description="frame presentation time in seconds")
    boxes: list[BoxMessage] = Field(default_factory=list)

    @classmethod
    def from_detections(
        cls,
        *,
        frame_id: int,
        timestamp: float,
        detections: Sequence[Detection],
    ) -> DetectionMessage:
        """Build a message from the detector's `Detection`s (the emit-side adapter)."""
        return cls(
            frame_id=frame_id,
            timestamp=timestamp,
            boxes=[
                BoxMessage(box_xyxy=d.box_xyxy, conf=d.conf, cls=d.cls) for d in detections
            ],
        )


class ContactRecord(BaseModel):
    """A taskable, localized contact on the JSON channel (Task 4.6; research gate §9).

    The MINIMUM honest field set the localizer can populate today. `frame_id`-aligned to video
    like `DetectionMessage`. `detection_conf` and `localization_conf` are SEPARATE axes: a
    contact can be confidently DETECTED yet poorly LOCALIZED (heading-limited) - that
    separation is what stops the smug-filter lie from reaching the operator. `r95_m` is the
    honest equal-coverage sweep radius (the empirical MC quantile, NOT the major semi-axis);
    the ellipse (semi-axes + orientation) is the expert overlay.

    Deferred to v1.x (NOT here - the localizer cannot honestly fill them): `clearance_state`
    (a UI-mutated mission-log field), `snapshot_on_dispatch_coord`/`delta` (premature wire
    optimization), `cluster_id` (needs multi-survivor disambiguation v1 does not claim).
    """

    model_config = ConfigDict(frozen=True)

    type: Literal["contact"] = "contact"
    frame_id: int = Field(ge=0, description="FrameSource seq this record aligns to")
    track_id: int = Field(ge=0)

    # Localized coordinate, (lat, lon) degrees WGS84 order (§3.1). None for a CUE-ONLY contact
    # with no fused coordinate (position-only pose / un-projectable): a hard (0, 0) would plot
    # at Null Island and read as a discovered survivor, so the wire says None and forces the UI
    # to special-case "no fix" rather than trust a false-precision pin.
    lat: float | None
    lon: float | None

    # Honest uncertainty: the equal-coverage sweep radius + actionability + the expert ellipse.
    r95_m: float = Field(ge=0.0, description="empirical 95% equal-coverage sweep radius, meters")
    actionability_class: Literal["PINPOINT", "SWEEP", "AREA", "CUE_ONLY"]
    semi_major_m: float = Field(ge=0.0)
    semi_minor_m: float = Field(ge=0.0)
    orientation_deg: float

    # Display priority (from Confirmation, Phase 3) + temporal-stability + heading-limited cap.
    priority_tier: Literal["contact", "candidate", "strong"]
    convergence_state: Literal["CONVERGING", "STABLE"]
    heading_limited: bool
    aspect_spread_deg: float = Field(ge=0.0)

    # The two SEPARATE confidence axes (§9).
    detection_conf: float = Field(ge=0.0, le=1.0)
    localization_conf: float = Field(ge=0.0, le=1.0)

    # Honesty flags the localizer surfaces.
    mc_reject_fraction: float = Field(ge=0.0, le=1.0)
    moving_suspected: bool
    age_frames: int = Field(ge=0)

    @classmethod
    def from_fused(
        cls,
        *,
        frame_id: int,
        track_id: int,
        coord: tuple[float, float],
        r95_m: float,
        actionability_class: str,
        semi_major_m: float,
        semi_minor_m: float,
        orientation_deg: float,
        convergence: ConvergenceState,
        heading_limited: bool,
        aspect_spread_deg: float,
        moving_suspected: bool,
        mc_reject_fraction: float,
        priority_tier: str,
        detection_conf: float,
        localization_conf: float,
        age_frames: int,
    ) -> ContactRecord:
        """Build a wire record from a `FusedEstimate` plus the per-track metadata the service
        loop owns (track_id, tier, detection_conf, frame_id, age)."""
        return cls(
            frame_id=frame_id,
            track_id=track_id,
            lat=coord[0],
            lon=coord[1],
            r95_m=r95_m,
            actionability_class=actionability_class,
            semi_major_m=semi_major_m,
            semi_minor_m=semi_minor_m,
            orientation_deg=orientation_deg,
            priority_tier=priority_tier,
            convergence_state=str(convergence.value),
            heading_limited=heading_limited,
            aspect_spread_deg=aspect_spread_deg,
            detection_conf=detection_conf,
            localization_conf=localization_conf,
            mc_reject_fraction=mc_reject_fraction,
            moving_suspected=moving_suspected,
            age_frames=age_frames,
        )
