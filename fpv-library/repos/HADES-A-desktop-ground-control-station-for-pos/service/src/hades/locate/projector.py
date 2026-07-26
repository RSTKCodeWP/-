"""Projector — cheap per-detection ground point, tagged with the frame-gate verdict (3.5).

For each `Detection` the Projector calls the shared `geometry.ray_to_ground` (the SAME
function Fuse uses in Phase 4 — never re-implemented) on the box's **bottom-center**
`((x_min+x_max)/2, y_max)`, the feet-on-ground reference point (DESIGN.md §3.2; the seam
the detector→localizer glue test, Task 4.8, guards).

Each resulting `GroundPoint` is tagged with the per-frame gate verdict (Task 3.3) so
Confirmation (3.6) clusters only gate-passing points. Crucially, a detection is **never
dropped from visibility**: a gated-out frame, an above-horizon ray, or a position-only
pose all still emit a `GroundPoint` — just one that is not `fusable` (a CUE-ONLY contact)
and may carry no coordinate. The gate governs *fusion eligibility*, never visibility.

The gate's obliqueness signal (`camera_pitch_deg`, measured from nadir) is computed from
the actual camera optical-axis world direction — mount boresight + airframe attitude — so
it is exact, not a hand-rolled additive approximation. IMU signals (angular rate, accel)
are absent on the replay path, so the gate returns PASS_UNVERIFIED there (still fusable).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from hades.detect.detector import Detection
from hades.ingest.telemetry_source import Pose
from hades.locate.camera_model import CameraModel
from hades.locate.frame_gate import GateInput, GateResult, GateVerdict, evaluate
from hades.locate.geometry import R_world_body, ray_to_ground


@dataclass(frozen=True)
class GroundPoint:
    """One detection projected (or not) to the ground, tagged with the gate verdict.

    `lat`/`lon` are None when the detection could not be projected (above-horizon ray,
    position-only pose, datum mismatch) — the detection still surfaces as a CUE-ONLY
    contact. `fusable` is True only when the gate passed AND a coordinate exists.
    """

    detection: Detection
    lat: float | None
    lon: float | None
    conf: float
    verdict: GateVerdict
    gate_reasons: tuple[str, ...] = ()

    @property
    def fusable(self) -> bool:
        """Eligible for the fused estimate: gate not REJECT and a FINITE coordinate exists.

        Rejects a non-finite (nan/inf) coordinate explicitly — `nan is not None` is True, so
        a None-only check would let a poisoned pin into the fused estimate (review F3).
        """
        return (
            self.verdict is not GateVerdict.REJECT
            and self.lat is not None
            and self.lon is not None
            and math.isfinite(self.lat)
            and math.isfinite(self.lon)
        )


class Projector:
    """Projects detections to gated ground points (cheap, per-detection, no Monte Carlo).

    Args:
        camera: the fixed-mount camera model (intrinsics + boresight).
        ground_elev / ground_elev_datum: operator-set ground plane for the intersection.
        mount_angle_from_nadir_deg: advisory; the obliqueness signal is derived from the
            true optical-axis direction, but this records the nominal mount tilt for docs.
    """

    def __init__(
        self,
        camera: CameraModel,
        ground_elev: float = 0.0,
        ground_elev_datum: str = "REL_TAKEOFF",
        mount_angle_from_nadir_deg: float = 0.0,
    ) -> None:
        self.camera = camera
        self.ground_elev = ground_elev
        self.ground_elev_datum = ground_elev_datum
        self.mount_angle_from_nadir_deg = mount_angle_from_nadir_deg

    def project(self, detections: list[Detection], pose: Pose) -> list[GroundPoint]:
        """Project every detection; emit a GroundPoint each (never drops a detection)."""
        gate = self._gate(pose)
        return [self._project_one(d, pose, gate) for d in detections]

    def _project_one(
        self, det: Detection, pose: Pose, gate: GateResult
    ) -> GroundPoint:
        x_min, _y_min, x_max, y_max = det.box_xyxy
        bottom_center = ((x_min + x_max) / 2.0, y_max)  # feet-on-ground (§3.2)
        try:
            lat, lon = ray_to_ground(
                pose,
                self.camera,
                pixel=bottom_center,
                ground_elev=self.ground_elev,
                ground_elev_datum=self.ground_elev_datum,
            )
        except ValueError:
            # Un-projectable (above-horizon ray, no GPS/attitude, datum mismatch): the
            # detection still surfaces as a CUE-ONLY contact with no coordinate.
            lat, lon = None, None
        return GroundPoint(
            detection=det,
            lat=lat,
            lon=lon,
            conf=det.conf,
            verdict=gate.verdict,
            gate_reasons=gate.reasons,
        )

    def _gate(self, pose: Pose) -> GateResult:
        """Build the GateInput from the pose + mount and evaluate it once per frame."""
        return evaluate(
            GateInput(
                camera_pitch_deg=self._camera_pitch_from_nadir(pose),
                # IMU signals are live-CRSF-path only; absent on the replay path → the gate
                # returns PASS_UNVERIFIED (still fusable). Wired when the live source lands.
                angular_rate_dps=None,
                accel_magnitude_g=None,
                vibration_metric=None,
            )
        )

    def _camera_pitch_from_nadir(self, pose: Pose) -> float | None:
        """Angle (deg) between the camera optical axis and straight-down (nadir).

        Exact from the geometry: rotate the optical +z axis into the world and measure its
        angle from ENU-down. None when attitude is absent (the gate then can't evaluate
        obliqueness and falls to PASS_UNVERIFIED). 0° = straight down, 90° = horizon.
        """
        if pose.roll is None or pose.pitch is None or pose.yaw is None:
            return None
        optical_axis_cam = np.array([0.0, 0.0, 1.0])  # +z into the scene
        axis_world = (
            R_world_body(pose.roll, pose.pitch, pose.yaw)
            @ self.camera.R_body_cam
            @ optical_axis_cam
        )
        down = np.array([0.0, 0.0, -1.0])  # ENU straight down
        cos_angle = float(np.clip(np.dot(axis_world, down), -1.0, 1.0))
        return float(np.degrees(np.arccos(cos_angle)))
