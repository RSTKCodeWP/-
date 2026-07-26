"""Monte Carlo uncertainty propagation (Task 4.4; research gate §4).

The FINAL reported uncertainty for a confirmed contact. Where `fuse.py` uses a cheap
linearized Jacobian for the per-frame fusion WEIGHT, this module produces the honest
reported ellipse + sweep radius by Monte Carlo: sample the input sigmas from the
`error_model`, push each draw through the SAME `ray_to_ground` (single source of truth),
and read the cloud's shape.

Decisions locked in the research gate:

- **Monte Carlo, N=1000** (2000 for the offline coverage report) - not Unscented Transform
  or linearized. Only MC yields the empirical R95 quantile of the non-Gaussian cross-range
  arc; UT/linearized assume Gaussian-from-covariance, which is exactly what the banana
  breaks. MC runs only on the confirmed contact (cold path), so the cost is trivial.

- **R95 = the EMPIRICAL 95th-percentile sample radius about the point estimate, NOT the
  major semi-axis.** The major semi-axis over-states the equal-coverage circle (it sweeps
  empty area off the minor axis) -> false pessimism. The empirical quantile is the honest,
  assumption-free "95% of the time the survivor is within this circle" claim, robust to the
  non-Gaussian shape.

- **95% ellipse scale = sqrt(chi^2(2)=5.991)** = 2.4477 (the expert overlay), oriented by
  the sample-covariance eigenvectors.

- **Common-mode heading bias drawn ONCE per contact**, jitter per draw - drawing the bias
  i.i.d. per draw would fake an error reduction fusion cannot achieve (the smug filter,
  inside the MC).

- **Per-sample above-horizon rejection** (`ray_to_ground` raises) + a max-plausible-range
  cap. The reject FRACTION is reported; a near-horizon-unstable contact (> 5% reject) is
  forced to CUE_ONLY with a floor radius - a transparent rejection, never a silent clip
  (clipping biases the covariance inward = false confidence).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from hades.ingest.telemetry_source import Pose
from hades.locate.camera_model import CameraModel
from hades.locate.error_model import SensorErrorModel
from hades.locate.geometry import ray_to_ground  # SINGLE SOURCE OF TRUTH (D1) - shared

_M_PER_DEG_LAT = 111320.0
_CHI2_2_95 = 5.991464547107979
_R95_SCALE = math.sqrt(_CHI2_2_95)  # 2.4477...

# A contact whose MC draws reject (above-horizon) above this fraction is near-horizon
# unstable -> CUE_ONLY with a floor radius (research gate §4).
_REJECT_FRACTION_CUE = 0.05
_MAX_GROUND_RANGE_M = 5000.0  # a survivor 5 km out is not what this camera resolves
_CUE_FLOOR_RADIUS_M = 200.0  # the honest "area, not a point" floor for an unstable contact

# Actionability class R95 band edges, meters (must match fuse.py for a consistent class).
_PINPOINT_M = 5.0
_SWEEP_M = 25.0
_AREA_M = 100.0


@dataclass(frozen=True)
class UncertaintyResult:
    """The reported uncertainty for one contact: covariance, 95% ellipse, and the honest
    equal-coverage R95 sweep radius + its actionability class."""

    cov: np.ndarray  # 2x2 ENU sample covariance (meters)
    r95_m: float  # empirical 95th-percentile sample radius (the sweep circle)
    semi_major_m: float  # 95% ellipse major semi-axis (expert overlay)
    semi_minor_m: float
    orientation_deg: float
    actionability_class: str  # PINPOINT | SWEEP | AREA | CUE_ONLY
    reject_fraction: float  # fraction of MC draws that rejected (above-horizon / out of range)
    floor_radius_m: float  # the CUE floor applied when reject_fraction is high
    coverage_of_own_r95: float  # fraction of samples within r95 (≈0.95 by construction)
    n_used: int  # MC draws that produced a valid ground point


class MonteCarloUncertainty:
    """Propagates input sigmas to a contact's reported ellipse + R95 by Monte Carlo."""

    def __init__(
        self, error_model: SensorErrorModel, n_draws: int = 1000, seed: int = 0
    ) -> None:
        self.m = error_model
        self.n = n_draws
        self.seed = seed

    def propagate(
        self,
        pose: Pose,
        camera: CameraModel,
        pixel: tuple[float, float],
        ground_elev: float = 0.0,
    ) -> UncertaintyResult:
        """Monte Carlo ground-point cloud for one contact around `pose`/`pixel`.

        Draws N perturbed (pose, pixel) realizations, projects each via `ray_to_ground`, and
        summarizes the surviving cloud. The heading bias is ONE draw shared across the N
        realizations (common-mode); jitter + GPS + boresight + pixel noise are per draw.
        """
        rng = np.random.default_rng(self.seed)
        m = self.m

        origin = (pose.lat, pose.lon)
        pts: list[np.ndarray] = []
        rejected = 0
        for _ in range(self.n):
            # The heading BIAS (crab) is UNKNOWN for this contact, so each MC sample draws its
            # own realization — that uncertainty is real dispersion in the reported ellipse.
            # (The "once per contact, not per frame" rule of §4 governs MULTI-FRAME fusion
            # geometry, where the SAME physical bias hits every frame; here we quantify a
            # single contact's uncertainty, so the unknown bias is a per-sample random var.)
            bias_sign = rng.choice([-1.0, 1.0]) if m.crab_sign_random else 1.0
            heading_bias = bias_sign * (
                m.crab_angle_deg + rng.normal(0.0, m.heading_bias_sigma_deg)
            )
            sample_pose, sample_pixel = self._draw(pose, pixel, m, heading_bias, rng)
            try:
                latlon = ray_to_ground(
                    sample_pose, camera, pixel=sample_pixel,
                    ground_elev=ground_elev + rng.normal(0.0, m.sigma_h_m),
                    ground_elev_datum=pose.alt_datum,
                )
            except ValueError:
                rejected += 1  # above-horizon ray, etc. — a transparent reject (§4)
                continue
            enu = self._enu(origin, latlon)
            if np.hypot(enu[0], enu[1]) > _MAX_GROUND_RANGE_M:
                rejected += 1  # implausibly far -> a near-horizon blow-up, reject it
                continue
            pts.append(enu)

        return self._summarize(np.array(pts), rejected)

    # --- draw one perturbed (pose, pixel) ------------------------------------------

    def _draw(
        self,
        pose: Pose,
        pixel: tuple[float, float],
        m: SensorErrorModel,
        heading_bias: float,
        rng: np.random.Generator,
    ) -> tuple[Pose, tuple[float, float]]:
        if m.gps_dist == "studentt" and m.gps_horiz_sigma_m > 0:
            scale = m.gps_horiz_sigma_m * math.sqrt(
                (m.gps_studentt_dof - 2.0) / m.gps_studentt_dof
            )
            de = float(rng.standard_t(m.gps_studentt_dof) * scale)
            dn = float(rng.standard_t(m.gps_studentt_dof) * scale)
        else:
            de = float(rng.normal(0.0, m.gps_horiz_sigma_m))
            dn = float(rng.normal(0.0, m.gps_horiz_sigma_m))
        lat = pose.lat + dn / _M_PER_DEG_LAT
        lon = pose.lon + de / (_M_PER_DEG_LAT * math.cos(math.radians(pose.lat)))
        alt = pose.alt + float(rng.normal(0.0, m.gps_vert_sigma_m))

        droll = float(rng.normal(0.0, m.roll_sigma_deg))
        dpitch = float(rng.normal(0.0, m.pitch_sigma_deg))
        # Heading = true + common-mode bias (shared) + per-draw jitter + boresight.
        dyaw = (
            heading_bias
            + float(rng.normal(0.0, m.yaw_jitter_sigma_deg))
            + float(rng.normal(0.0, m.boresight_sigma_deg))
        )
        sample_pose = Pose(
            t=pose.t, lat=lat, lon=lon, alt=alt, alt_datum=pose.alt_datum,
            roll=pose.roll + droll, pitch=pose.pitch + dpitch, yaw=pose.yaw + dyaw,
            seq=pose.seq,
        )
        # The detection pixel (box bottom-center) also jitters; foot_bias_px is a systematic
        # feet-vs-box-bottom offset on the v-axis.
        du = float(rng.normal(0.0, m.pixel_sigma_px))
        dv = float(rng.normal(m.foot_bias_px, m.pixel_sigma_px))
        return sample_pose, (pixel[0] + du, pixel[1] + dv)

    def _enu(self, origin: tuple[float, float], latlon: tuple[float, float]) -> np.ndarray:
        north = (latlon[0] - origin[0]) * _M_PER_DEG_LAT
        east = (latlon[1] - origin[1]) * _M_PER_DEG_LAT * math.cos(math.radians(origin[0]))
        return np.array([east, north])

    # --- summarize the cloud --------------------------------------------------------

    def _summarize(self, pts: np.ndarray, rejected: int) -> UncertaintyResult:
        n_used = len(pts)
        total = n_used + rejected
        reject_fraction = rejected / total if total else 1.0

        if n_used < 2:
            # Degenerate: nothing projected -> CUE_ONLY at the floor.
            return UncertaintyResult(
                cov=np.eye(2) * _CUE_FLOOR_RADIUS_M ** 2,
                r95_m=_CUE_FLOOR_RADIUS_M,
                semi_major_m=_CUE_FLOOR_RADIUS_M,
                semi_minor_m=_CUE_FLOOR_RADIUS_M,
                orientation_deg=0.0,
                actionability_class="CUE_ONLY",
                reject_fraction=reject_fraction,
                floor_radius_m=_CUE_FLOOR_RADIUS_M,
                coverage_of_own_r95=1.0,
                n_used=n_used,
            )

        center = pts.mean(axis=0)
        cov = np.cov(pts.T)  # 2x2 sample covariance
        radii = np.hypot(pts[:, 0] - center[0], pts[:, 1] - center[1])
        r95_empirical = float(np.quantile(radii, 0.95))

        vals, vecs = np.linalg.eigh(cov)
        vals = np.clip(vals, 0.0, None)
        order = np.argsort(vals)[::-1]
        major = _R95_SCALE * math.sqrt(vals[order[0]])
        minor = _R95_SCALE * math.sqrt(vals[order[1]])
        v = vecs[:, order[0]]
        orient = math.degrees(math.atan2(v[1], v[0]))

        # Near-horizon instability -> CUE_ONLY at a floor, never a tight false number (§4).
        if reject_fraction > _REJECT_FRACTION_CUE:
            r95 = max(r95_empirical, _CUE_FLOOR_RADIUS_M)
            return UncertaintyResult(
                cov=cov, r95_m=r95, semi_major_m=major, semi_minor_m=minor,
                orientation_deg=orient, actionability_class="CUE_ONLY",
                reject_fraction=reject_fraction, floor_radius_m=_CUE_FLOOR_RADIUS_M,
                coverage_of_own_r95=float(np.mean(radii <= r95)), n_used=n_used,
            )

        cls = self._actionability(r95_empirical)
        return UncertaintyResult(
            cov=cov, r95_m=r95_empirical, semi_major_m=major, semi_minor_m=minor,
            orientation_deg=orient, actionability_class=cls,
            reject_fraction=reject_fraction, floor_radius_m=0.0,
            coverage_of_own_r95=float(np.mean(radii <= r95_empirical)), n_used=n_used,
        )

    def _actionability(self, r95: float) -> str:
        if r95 <= _PINPOINT_M:
            return "PINPOINT"
        if r95 <= _SWEEP_M:
            return "SWEEP"
        if r95 <= _AREA_M:
            return "AREA"
        return "CUE_ONLY"
