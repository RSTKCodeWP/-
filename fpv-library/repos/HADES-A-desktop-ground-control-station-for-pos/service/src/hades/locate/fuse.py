"""Fuse - geometry-weighted multi-frame localization with an honest bias floor (Task 4.3).

The flagship estimator. Given the per-frame fusable observations of ONE stationary survivor
track, it produces a single fused ground coordinate with an HONEST 2x2 covariance. The
design is the research gate (docs/plans/p4-localization-research.md) sections 1, 2, 6:

- **Full-information weighted mean** (`Wi = Sigma_i^-1`), in the local ENU tangent plane in
  meters about a fixed mission origin. NOT a scalar `1/trace` weight: the dominant heading
  error makes each `Sigma_i` anisotropic and rotated, and the only real fusion gain on a
  heading-limited system is azimuthal diversity collapsing the cross-range axis - which a
  scalar weight discards. Full `Sigma_i^-1` also self-down-weights oblique/long-range frames
  (their `Sigma_i` is huge along down-range), so no hand-tuned cos/range factor is applied.

- **Per-frame `Sigma_i` via the linearized Jacobian of the SHARED `ray_to_ground`** (central
  finite difference, 2x7). The same single-source-of-truth function the Projector uses (D1),
  never re-implemented. The cheap Jacobian is for the WEIGHT only; the final reported tail is
  refined by Monte Carlo in `uncertainty.py` (Task 4.4).

- **THE BIAS FLOOR (the headline honesty point), via MONTE CARLO OVER FUSION.** Inverse-
  variance averaging drives the zero-mean jitter down as ~1/sqrt(N) but CANNOT touch the
  common-mode heading bias (the same wind-crab offset on every frame of one pass). A naive
  `Sigma_fuse = Lambda^-1` therefore shrinks toward zero while the estimate sits on a
  CONFIDENTLY WRONG point - the "smug filter," the worst SAR failure. The research gate (§2)
  originally specified an additive analytic floor `Sigma_report = Lambda^-1 + Sigma_bias`;
  this implementation supersedes that with the gate's own §1.2 Monte-Carlo-over-fusion (the
  linearized additive form under-covered: matched coverage 0.46 / NEES ~11, vs 0.99 / NEES ~1
  for MC). `_mc_fused_cov` resamples the inputs - drawing the heading BIAS ONCE per realization
  (the common-mode rule), jitter per frame - re-fuses each, and reports the spread of the FUSED
  estimates. Because the bias is shared across a realization's frames, it does NOT average out
  within that realization: the cloud stays wide and R95 asymptotes to a floor that grows with
  the heading lever arm (ground range), never to zero. The reported R95 is the EMPIRICAL 95th-
  percentile radius of that cloud about x_hat (the honest equal-coverage circle, §4), NOT the
  major semi-axis.

- **Aspect diversity informs the floor.** A heading bias displaces the ground point roughly
  perpendicular to the camera->target azimuth; observed from a spread of azimuths it partially
  cancels (the MC cloud tightens because the per-realization bias projects to different ground
  directions across diverse frames). A single straight pass (aspect_spread < ~70 deg) is
  flagged `heading_limited` and capped at SWEEP (never PINPOINT) no matter how tight the
  variance. v1 reports the floor and the regime; it does not ESTIMATE the bias (Schmidt-
  consider is v1.x).

- **Moving-target / model-mismatch detection** via a NIS-style residual-consistency test
  (mean squared Mahalanobis ~ 2 under a static target). High/over-threshold -> the estimate
  stays CONVERGING with the (large) empirical-scatter radius, `moving_suspected=True`. A
  single gross outlier is chi^2-rejected from the fused mean first (still visible as a
  detection - the gate owns fusion-eligibility, never visibility) so it can't fake "moving".
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np

from hades.ingest.telemetry_source import Pose
from hades.locate.camera_model import CameraModel
from hades.locate.error_model import SensorErrorModel
from hades.locate.geometry import ray_to_ground  # SINGLE SOURCE OF TRUTH (D1) - shared

_M_PER_DEG_LAT = 111320.0
_CHI2_2_95 = 5.991464547107979  # chi^2(2) at 0.95 -> the 95% ellipse scale
_CHI2_2_999 = 13.815510557964274  # chi^2(2) at 0.999 -> per-frame outlier reject gate
_R95_FROM_SIGMA = math.sqrt(_CHI2_2_95)  # 2.4477...: circular-Gaussian R95 from an isotropic sigma

# Aspect-spread regime boundary (research gate §2): below this the heading bias does NOT
# cancel (single-pass), so the contact is heading_limited and capped at SWEEP; an orbit spans
# ~180 deg of axial spread and clears it (the bias is observable -> relaxed).
_ASPECT_RELAXED_DEG = 70.0

# Moving-target NIS threshold: mean squared Mahalanobis ~ 2 (=dim) under a static target.
# tau is the multiple of that expectation above which we declare non-convergence.
_NIS_TAU = 3.0

# Actionability class R95 band edges, meters (research gate §4; locked on sim calibration).
_PINPOINT_M = 5.0
_SWEEP_M = 25.0
_AREA_M = 100.0


class ConvergenceState(str, Enum):
    """Temporal-stability axis (orthogonal to the R95-band actionability class)."""

    CONVERGING = "CONVERGING"
    STABLE = "STABLE"


@dataclass(frozen=True)
class FuseObservation:
    """One fusable per-frame look at the track: the pose, the camera, and the detection
    pixel (the box bottom-center, the §3.2 feet-on-ground point). The fuser re-projects this
    pixel through the shared `ray_to_ground` and linearizes around the pose for the weight."""

    pose: Pose
    camera: CameraModel
    pixel: tuple[float, float]


@dataclass(frozen=True)
class FusedEstimate:
    """The fused result for one track. `coord` is (lat, lon). `r95_m` is the floored,
    honest sweep radius; `r95_prefloor_m` exposes the pure information radius (for tests /
    diagnostics). The ellipse (semi-axes + orientation) is the expert overlay."""

    coord: tuple[float, float]
    r95_m: float
    r95_prefloor_m: float
    cov_report: np.ndarray  # 2x2 ENU covariance INCLUDING the bias floor
    semi_major_m: float
    semi_minor_m: float
    orientation_deg: float
    actionability_class: str  # PINPOINT | SWEEP | AREA | CUE_ONLY
    convergence: ConvergenceState
    heading_limited: bool
    aspect_spread_deg: float
    moving_suspected: bool
    n_fused: int
    n_rejected: int
    nis: float


def _enu_offset(origin: tuple[float, float], latlon: tuple[float, float]) -> np.ndarray:
    """(east, north) meters of `latlon` relative to the `origin` lat/lon."""
    north = (latlon[0] - origin[0]) * _M_PER_DEG_LAT
    east = (latlon[1] - origin[1]) * _M_PER_DEG_LAT * math.cos(math.radians(origin[0]))
    return np.array([east, north])


def _enu_to_latlon(origin: tuple[float, float], enu: np.ndarray) -> tuple[float, float]:
    lat = origin[0] + enu[1] / _M_PER_DEG_LAT
    lon = origin[1] + enu[0] / (_M_PER_DEG_LAT * math.cos(math.radians(origin[0])))
    return lat, lon


class Fuser:
    """Stateless multi-frame fuser. One `fuse(observations)` call per (re-)evaluation."""

    def __init__(self, error_model: SensorErrorModel, mc_draws: int = 200, seed: int = 0) -> None:
        self.m = error_model
        self.mc_draws = mc_draws  # MC-over-fusion realizations for the reported covariance
        self.seed = seed

    # --- public ---------------------------------------------------------------------

    def fuse(self, observations: list[FuseObservation]) -> FusedEstimate | None:
        """Fuse the fusable observations of one stationary track into a FusedEstimate.

        Returns None if no observation projects (a CUE-ONLY contact upstream).
        """
        projected = self._project_all(observations)
        if not projected:
            return None

        origin = projected[0][0]  # mission origin = first projected lat/lon
        points = [_enu_offset(origin, latlon) for latlon, _ in projected]
        covs = [Sigma for _, Sigma in projected]

        # --- robust outlier reject (GROSS single bad boxes only) ---
        # Iteratively drop the single worst-residual frame while its removal is justified: it
        # must be a gross outlier vs the bulk AND the bulk must otherwise be consistent. This
        # removes a misassociation/glint without mass-rejecting a coherent DRIFT (whose points
        # are all mildly off, none grossly) - the drift must survive to feed the NIS test.
        kept_idx, n_rejected = self._reject_outliers(points, covs)
        pts = [points[i] for i in kept_idx]
        cvs = [covs[i] for i in kept_idx]

        # --- full-information weighted mean (the point estimate + its info radius) ---
        x_hat, cov_info = self._weighted_mean(pts, cvs)

        aspect_spread = self._aspect_spread(observations, origin)

        # --- REPORTED covariance + cloud = Monte Carlo OVER THE FUSION (research gate §1.2, §4) ---
        # The cheap linearized cov_info under-states the true fused error: at 20 deg heading the
        # ray map is non-linear and the per-frame errors are correlated, so Lambda^-1 over-
        # shrinks. The honest reported covariance is the spread of the FUSED estimate under
        # resampled input noise (jitter per frame, bias ONCE per realization - the common-mode
        # rule). This naturally carries both the non-Gaussian tail AND the non-shrinking bias.
        cov_report, mc_cloud = self._mc_fused_cov(observations, origin, x_hat)

        # --- NIS residual-consistency test (moving target / model mismatch) ---
        nis, moving = self._nis(pts, cvs, x_hat)
        if moving:
            # Stay honest: use the empirical scatter (it reflects the spread the static model
            # cannot explain), inflated above the over-optimistic information ellipse.
            cov_report = self._empirical_scatter(pts, x_hat) + cov_report
            mc_cloud = None  # the cloud no longer describes the (inflated) reported spread

        # --- derived reporting quantities ---
        r95_prefloor = self._r95_from_cov(cov_info)
        # R95 = the EMPIRICAL 95th-pct sample radius about x_hat (the honest equal-coverage
        # circle, §4), NOT the major semi-axis. Measuring about x_hat (the reported coord, the
        # weighted mean) - not the cloud's own unweighted mean - folds the weighted-vs-unweighted
        # offset into the radius. Falls back to the covariance form only when the cloud is
        # unavailable (moving-target inflation path).
        r95 = self._empirical_r95(mc_cloud, x_hat) if mc_cloud is not None else self._r95_from_cov(
            cov_report
        )
        major, minor, orient = self._ellipse(cov_report)
        heading_limited = aspect_spread < _ASPECT_RELAXED_DEG
        cls = self._actionability(r95, heading_limited, moving)
        convergence = (
            ConvergenceState.CONVERGING if moving else self._convergence(r95)
        )

        coord = _enu_to_latlon(origin, x_hat)
        return FusedEstimate(
            coord=coord,
            r95_m=r95,
            r95_prefloor_m=r95_prefloor,
            cov_report=cov_report,
            semi_major_m=major,
            semi_minor_m=minor,
            orientation_deg=orient,
            actionability_class=cls,
            convergence=convergence,
            heading_limited=heading_limited,
            aspect_spread_deg=aspect_spread,
            moving_suspected=moving,
            n_fused=len(pts),
            n_rejected=n_rejected,
            nis=nis,
        )

    # --- per-frame projection + linearized covariance -------------------------------

    def _project_all(
        self, observations: list[FuseObservation]
    ) -> list[tuple[tuple[float, float], np.ndarray]]:
        """Project each observation to (lat, lon) + its linearized 2x2 ENU covariance.
        Frames that refuse to project (pose-None, above-horizon) are dropped here."""
        out = []
        for ob in observations:
            try:
                latlon = ray_to_ground(
                    ob.pose, ob.camera, pixel=ob.pixel, ground_elev=0.0,
                    ground_elev_datum=ob.pose.alt_datum,
                )
            except ValueError:
                continue
            Sigma = self._frame_cov(ob)
            if Sigma is None:
                continue
            out.append((latlon, Sigma))
        return out

    def _frame_cov(self, ob: FuseObservation) -> np.ndarray | None:
        """Linearized 2x2 ENU ground covariance for one frame: J . Sigma_inputs . J^T.

        J = d(east, north)/d(roll, pitch, yaw, lat, lon, alt, ground_elev) by central
        finite difference on the SHARED `ray_to_ground`. Sigma_inputs is the diagonal of the
        per-frame ZERO-MEAN input variances from the error_model."""
        m = self.m
        # Input 1-sigmas, in the SI units ray_to_ground consumes (deg for attitude, m for
        # GPS/alt, deg for lat/lon converted to meters via the small-angle scale).
        s_lat_deg = m.gps_horiz_sigma_m / _M_PER_DEG_LAT
        s_lon_deg = m.gps_horiz_sigma_m / (
            _M_PER_DEG_LAT * math.cos(math.radians(ob.pose.lat))
        )
        # Heading variance for the per-frame Sigma_i is JITTER ONLY. The systematic bias does
        # NOT belong here: it does not average down, so putting it in Sigma_i (which feeds the
        # information sum Lambda^-1 that shrinks ~1/N) would let fusion wrongly cancel it -
        # the smug filter. The bias instead enters via the MC-over-fusion cloud (`_mc_fused_cov`,
        # one shared bias draw per realization), where it stays non-shrinking (§1.2, §2).
        s_yaw = m.yaw_jitter_sigma_deg
        sigmas = {
            "roll": m.roll_sigma_deg,
            "pitch": m.pitch_sigma_deg,
            "yaw": s_yaw,
            "lat": s_lat_deg,
            "lon": s_lon_deg,
            "alt": m.gps_vert_sigma_m,
            "ground_elev": m.sigma_h_m,
        }
        J = self._jacobian(ob)
        if J is None:
            return None
        Sigma_inputs = np.diag([sigmas[k] ** 2 for k in _JAC_ORDER])
        Sigma = J @ Sigma_inputs @ J.T
        # Add the detector pixel-jitter contribution (cheap, isotropic-ish in ground meters
        # via the same Jacobian columns would need pixel partials; approximate with the
        # GPS-scale floor so a zero-attitude-noise config still has a non-singular Sigma).
        Sigma += np.eye(2) * (0.01 ** 2)  # 1 cm jitter floor -> never singular
        return Sigma

    def _jacobian(self, ob: FuseObservation) -> np.ndarray | None:
        """2x7 central finite-difference Jacobian of (east, north) wrt the 7 inputs."""
        origin_latlon = self._safe_project(ob, {})
        if origin_latlon is None:
            return None
        origin = origin_latlon
        cols = []
        for key in _JAC_ORDER:
            h = _JAC_STEP[key]
            plus = self._safe_project(ob, {key: +h})
            minus = self._safe_project(ob, {key: -h})
            if plus is None or minus is None:
                return None
            de = _enu_offset(origin, plus) - _enu_offset(origin, minus)
            cols.append(de / (2.0 * h))
        return np.column_stack(cols)  # 2x7

    def _safe_project(
        self, ob: FuseObservation, perturb: dict[str, float]
    ) -> tuple[float, float] | None:
        """Project the observation with the given input perturbations applied. None if the
        perturbed ray refuses (above-horizon etc.)."""
        p = ob.pose
        pose = Pose(
            t=p.t,
            lat=p.lat + perturb.get("lat", 0.0),
            lon=p.lon + perturb.get("lon", 0.0),
            alt=p.alt + perturb.get("alt", 0.0),
            alt_datum=p.alt_datum,
            roll=p.roll + perturb.get("roll", 0.0),
            pitch=p.pitch + perturb.get("pitch", 0.0),
            yaw=p.yaw + perturb.get("yaw", 0.0),
            seq=p.seq,
        )
        try:
            return ray_to_ground(
                pose, ob.camera, pixel=ob.pixel,
                ground_elev=perturb.get("ground_elev", 0.0),
                ground_elev_datum=p.alt_datum,
            )
        except ValueError:
            return None

    # --- aspect diversity + geometry helpers ----------------------------------------

    def _bearings(
        self, observations: list[FuseObservation], origin: tuple[float, float]
    ) -> np.ndarray:
        bs = []
        for ob in observations:
            if ob.pose.lat is None:
                continue
            d = _enu_offset((ob.pose.lat, ob.pose.lon), origin)  # drone -> origin(target)
            bs.append(math.degrees(math.atan2(d[0], d[1])) % 360.0)
        return np.array(bs)

    def _aspect_spread(
        self, observations: list[FuseObservation], origin: tuple[float, float]
    ) -> float:
        """Aspect diversity that predicts heading-bias CANCELLATION, in degrees [0, 180].

        The bias displaces the ground point perpendicular to the camera->target azimuth, so
        what matters for cancellation is the spread of the azimuth LINE orientation, not the
        raw bearing. Two antiparallel bearings (a drone flying directly over the target, 0 and
        180 deg) lie on ONE axis; an orbit spans all axes. Use the AXIAL (doubled-angle,
        mod-180) circular resultant: `R = |mean(exp(i*2*bearing))|`, spread = `(1-R)*180`.

        Verified against the sim: a lateral single pass -> ~5-25 deg (heading-limited, bias
        does NOT cancel); an orbit -> ~180 deg (diverse, bias cancels). A perfectly symmetric
        overhead pass reads ~0 deg too, which is the honest answer for the realistic
        (laterally-offset) single leg; v1 does not special-case the degenerate exact-overpass.
        """
        bs = self._bearings(observations, origin)
        if len(bs) < 2:
            return 0.0
        doubled = np.radians(bs) * 2.0
        R = abs(np.mean(np.exp(1j * doubled)))
        return float((1.0 - R) * 180.0)

    # --- NIS / outliers / empirical scatter -----------------------------------------

    def _weighted_mean(
        self, pts: list[np.ndarray], cvs: list[np.ndarray]
    ) -> tuple[np.ndarray, np.ndarray]:
        """Full-information weighted mean: x_hat = Lambda^-1 sum(Sigma_i^-1 x_i)."""
        Lambda = np.zeros((2, 2))
        info_sum = np.zeros(2)
        for x, S in zip(pts, cvs):
            Wi = np.linalg.inv(S)
            Lambda += Wi
            info_sum += Wi @ x
        cov_info = np.linalg.inv(Lambda)
        return cov_info @ info_sum, cov_info

    def _mc_fused_cov(
        self,
        observations: list[FuseObservation],
        origin: tuple[float, float],
        x_hat: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray | None]:
        """Reported covariance + the fused-estimate cloud, under resampled input noise.

        For each of `mc_draws` realizations: draw a single common-mode heading bias (the §2
        once-per-contact rule), then perturb every observation's pose by per-frame jitter +
        GPS + the shared bias, re-project via `ray_to_ground`, and re-fuse by an UNWEIGHTED
        mean (the weighting is for the point estimate; the cloud spread is what we want here).
        Returns the covariance of the resulting fused points (the honest reported covariance,
        carrying the heading non-linearity AND the non-shrinking bias the linearized cov_info
        misses) AND the cloud itself (for the empirical-quantile R95, §4). The cloud is None if
        too few realizations project.
        """
        m = self.m
        rng = np.random.default_rng(self.seed)
        fused_pts = []
        for _ in range(self.mc_draws):
            bias_sign = rng.choice([-1.0, 1.0]) if m.crab_sign_random else 1.0
            heading_bias = bias_sign * (
                m.crab_angle_deg + rng.normal(0.0, m.heading_bias_sigma_deg)
            )
            pts = []
            for ob in observations:
                latlon = self._perturbed_project(ob, m, heading_bias, rng)
                if latlon is not None:
                    pts.append(_enu_offset(origin, latlon))
            if pts:
                fused_pts.append(np.mean(pts, axis=0))
        if len(fused_pts) < 3:
            return np.eye(2) * 1.0, None
        arr = np.array(fused_pts)
        cov = np.cov(arr.T) + np.eye(2) * (0.25 ** 2)  # tiny floor: never singular
        return cov, arr  # return the cloud too, for the honest empirical-quantile R95 (§4)

    def _empirical_r95(self, cloud: np.ndarray, x_hat: np.ndarray) -> float:
        """R95 = the 95th-percentile radius of the MC-over-fusion cloud ABOUT x_hat (§4).

        Measured about x_hat (the reported, weighted coordinate) - not the cloud's unweighted
        mean - so any weighted-vs-unweighted offset is folded into the radius as honest extra
        coverage. This is the equal-coverage circle: 95% of resampled fused estimates land
        within it, with zero Gaussian assumption (robust to the cross-range arc). Mirrors
        uncertainty.py's empirical R95."""
        radii = np.hypot(cloud[:, 0] - x_hat[0], cloud[:, 1] - x_hat[1])
        return float(np.quantile(radii, 0.95))

    def _perturbed_project(
        self,
        ob: FuseObservation,
        m: SensorErrorModel,
        heading_bias: float,
        rng: np.random.Generator,
    ) -> tuple[float, float] | None:
        """Project one observation with input noise applied (jitter per frame + shared bias)."""
        p = ob.pose
        de = float(rng.normal(0.0, m.gps_horiz_sigma_m))
        dn = float(rng.normal(0.0, m.gps_horiz_sigma_m))
        lat = p.lat + dn / _M_PER_DEG_LAT
        lon = p.lon + de / (_M_PER_DEG_LAT * math.cos(math.radians(p.lat)))
        pose = Pose(
            t=p.t, lat=lat, lon=lon,
            alt=p.alt + float(rng.normal(0.0, m.gps_vert_sigma_m)),
            alt_datum=p.alt_datum,
            roll=p.roll + float(rng.normal(0.0, m.roll_sigma_deg)),
            pitch=p.pitch + float(rng.normal(0.0, m.pitch_sigma_deg)),
            yaw=p.yaw + heading_bias + float(rng.normal(0.0, m.yaw_jitter_sigma_deg)),
            seq=p.seq,
        )
        du = float(rng.normal(0.0, m.pixel_sigma_px))
        dv = float(rng.normal(m.foot_bias_px, m.pixel_sigma_px))
        try:
            return ray_to_ground(
                pose, ob.camera, pixel=(ob.pixel[0] + du, ob.pixel[1] + dv),
                ground_elev=float(rng.normal(0.0, m.sigma_h_m)),
                ground_elev_datum=p.alt_datum,
            )
        except ValueError:
            return None

    def _reject_outliers(
        self, points: list[np.ndarray], covs: list[np.ndarray]
    ) -> tuple[list[int], int]:
        """Iteratively drop the single GROSS outlier frame, capped at a small fraction.

        A frame is a gross outlier if its residual vs the ROBUST median center is far beyond
        BOTH its own predicted Sigma (chi^2 99.9%) AND the empirical spread of the bulk (so a
        coherent drift, where every point is mildly off but none is gross relative to the
        spread, is NOT rejected - it must survive to trip the moving-target NIS test). At most
        ceil(10%) of frames may be removed; beyond that the data is "spread," not "outliers."
        """
        n = len(points)
        if n < 4:
            return list(range(n)), 0
        idx = list(range(n))
        cap = max(1, n // 10)
        rejected = 0
        while rejected < cap and len(idx) >= 4:
            arr = np.array([points[i] for i in idx])
            center = np.median(arr, axis=0)
            # Robust spread scale: median abs deviation -> a per-axis sigma the drift sets.
            mad = np.median(np.abs(arr - center), axis=0)
            spread_var = np.maximum((1.4826 * mad) ** 2, 1e-6)  # MAD->sigma; floor non-zero
            worst_i, worst_d2_cov, worst_d2_spread = None, 0.0, 0.0
            for i in idx:
                r = points[i] - center
                d2_cov = float(r @ np.linalg.inv(covs[i]) @ r)
                d2_spread = float(np.sum((r ** 2) / spread_var))
                if d2_cov > worst_d2_cov:
                    worst_i, worst_d2_cov, worst_d2_spread = i, d2_cov, d2_spread
            # Reject only if it's gross BOTH vs its own Sigma AND vs the bulk spread (the
            # latter is what spares a coherent drift, whose worst point is ~in-family).
            if worst_i is not None and worst_d2_cov > _CHI2_2_999 and worst_d2_spread > 16.0:
                idx.remove(worst_i)
                rejected += 1
            else:
                break
        return idx, rejected

    def _nis(
        self, points: list[np.ndarray], covs: list[np.ndarray], x_hat: np.ndarray
    ) -> tuple[float, bool]:
        if len(points) < 2:
            return 0.0, False
        d2s = []
        for x, S in zip(points, covs):
            r = x - x_hat
            d2s.append(float(r @ np.linalg.inv(S) @ r))
        nis = float(np.mean(d2s))
        moving = nis > 2.0 * _NIS_TAU  # E[d2]=2 under static; tau-multiple is the trigger
        return nis, moving

    def _empirical_scatter(self, points: list[np.ndarray], x_hat: np.ndarray) -> np.ndarray:
        if len(points) < 2:
            return np.eye(2) * 1.0
        R = np.array([x - x_hat for x in points])
        return (R.T @ R) / (len(points) - 1)

    # --- ellipse / R95 / class / convergence ----------------------------------------

    def _ellipse(self, cov: np.ndarray) -> tuple[float, float, float]:
        vals, vecs = np.linalg.eigh(cov)
        vals = np.clip(vals, 0.0, None)
        order = np.argsort(vals)[::-1]
        l1, l2 = vals[order[0]], vals[order[1]]
        major = _R95_FROM_SIGMA * math.sqrt(l1)
        minor = _R95_FROM_SIGMA * math.sqrt(l2)
        v = vecs[:, order[0]]
        orient = math.degrees(math.atan2(v[1], v[0]))
        return major, minor, orient

    def _r95_from_cov(self, cov: np.ndarray) -> float:
        """A covariance-form radius, used ONLY for the `r95_prefloor` diagnostic and the rare
        moving-target inflation fallback - NOT for the reported R95 (that is the empirical
        quantile, `_empirical_r95`, the honest equal-coverage form per §4). This Gaussian-
        major-axis form over-states the equal-coverage circle, so it is deliberately kept off
        the public sweep radius."""
        vals = np.clip(np.linalg.eigvalsh(cov), 0.0, None)
        return _R95_FROM_SIGMA * math.sqrt(vals.max())

    def _actionability(self, r95: float, heading_limited: bool, moving: bool) -> str:
        if moving:
            return "AREA" if r95 < _AREA_M else "CUE_ONLY"
        if r95 <= _PINPOINT_M and not heading_limited:
            return "PINPOINT"
        if r95 <= _SWEEP_M:
            return "SWEEP"
        if r95 <= _AREA_M:
            return "AREA"
        return "CUE_ONLY"

    def _convergence(self, r95: float) -> ConvergenceState:
        # A tight, non-moving estimate is STABLE; the full Schmitt+dwell state machine lives
        # in the streaming service loop (Task 4.7) where frame-to-frame history exists. The
        # batch fuser reports the instantaneous state from the radius.
        return ConvergenceState.STABLE if r95 <= _SWEEP_M else ConvergenceState.CONVERGING


# Input order for the Jacobian columns + their finite-difference steps.
_JAC_ORDER = ("roll", "pitch", "yaw", "lat", "lon", "alt", "ground_elev")
_JAC_STEP = {
    "roll": 1e-3,  # degrees
    "pitch": 1e-3,
    "yaw": 1e-3,
    "lat": 1e-7,  # degrees (~1 cm)
    "lon": 1e-7,
    "alt": 1e-2,  # meters
    "ground_elev": 1e-2,
}
