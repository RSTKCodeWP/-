"""Coverage validation - the anti-circular honesty check (Task 4.5; research gate §5).

This is the flagship's credibility. It does NOT just confirm the propagation arithmetic; it
proves the uncertainty is HONEST under model error. The structure that makes it
non-tautological:

- The SIMULATOR injects noise from `sim_model` (what reality does).
- The FUSER assumes noise from `fuser_model` (what the system believes) - it is handed ONLY
  this config object, NEVER the sim's realized draws (the no-leakage tooth).
- Both call the identical `ray_to_ground` (one geometry).

Two regimes:
- MATCHED (`sim_model == fuser_model`): coverage ~95% proves only the arithmetic (C1).
- MISMATCHED: coverage degrades in the predicted direction (C2). The mandatory out-of-schema
  mismatch is the TIME-SYNC offset (the sim displaces poses down-track by velocity*offset; the
  fuser models no offset) - a systematic bias that fusion makes WORSE, so cov(N=30) < cov(N=1).
  That monotone "fusion worsens" signature is what distinguishes a bias from a variance
  underestimate, and is the single most convincing demonstration the metric measures the
  world, not its own math.

Per row we report empirical coverage (fraction of trials whose true target falls inside the
95% ellipse) and mean NEES (`r^T Sigma^-1 r`, target ~2 = the state dimension). NEES catches
shape errors coverage cannot see (an ellipse too big in range but too small in cross-range can
still score ~95% while being wrong about shape). Predicted numbers are measure-then-lock; the
committed assertions are directions + threshold bands.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

import numpy as np

from hades.locate.camera_model import CameraModel
from hades.locate.error_model import SensorErrorModel
from hades.locate.fuse import FuseObservation, Fuser
from hades.locate.geom_sim import GeomSim, StraightPass

_M_PER_DEG_LAT = 111320.0
_CHI2_2_95 = 5.991464547107979  # the 95% ellipse gate on the squared Mahalanobis distance


@dataclass(frozen=True)
class CoverageRow:
    """One row of the coverage matrix: a (sim, fuser) noise pairing and its results."""

    name: str
    coverage: float  # fraction of trials whose true target lies inside the 95% ellipse
    mean_nees: float  # mean squared Mahalanobis distance (target ~2)
    median_r95_m: float
    n_frames: int
    n_trials: int


def _nadir_cam() -> CameraModel:
    return CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=540.0, mount="nadir")


def _enu_offset(origin: tuple[float, float], latlon: tuple[float, float]) -> np.ndarray:
    north = (latlon[0] - origin[0]) * _M_PER_DEG_LAT
    east = (latlon[1] - origin[1]) * _M_PER_DEG_LAT * math.cos(math.radians(origin[0]))
    return np.array([east, north])


def coverage_trial(
    sim_model: SensorErrorModel,
    fuser_model: SensorErrorModel,
    n_frames: int,
    n_trials: int,
    seed: int,
    lateral_offset_m: float = 5.0,
    agl_m: float = 30.0,
    speed_mps: float = 20.0,
) -> CoverageRow:
    """Run `n_trials` independent localizations and measure empirical coverage + mean NEES.

    Each trial: the sim (driven by `sim_model`) produces noisy observations of a known target
    on a straight lateral pass; the fuser (driven by `fuser_model` - the no-leakage config)
    fuses them into an estimate + reported covariance. The trial "covers" if the true target's
    squared Mahalanobis distance under that covariance is <= chi^2(2)=5.991.

    The matched case (`sim_model == fuser_model`) should land ~95%. A mismatch where the sim
    carries an unmodeled error degrades coverage in its characteristic direction.
    """
    cam = _nadir_cam()
    # A modest MC-over-fusion draw count keeps the harness fast; the 2x2 reported covariance is
    # stable well below the per-contact default, and coverage averages over many trials anyway.
    fuser = Fuser(error_model=fuser_model, mc_draws=120, seed=seed)
    rng = np.random.default_rng(seed)

    covered = 0
    nees_vals: list[float] = []
    r95s: list[float] = []
    valid = 0
    for _ in range(n_trials):
        # A fresh target placement per trial keeps trials independent.
        target = (40.0 + float(rng.normal(0.0, 0.001)), -74.0 + float(rng.normal(0.0, 0.001)))
        path = StraightPass(
            target_latlon=target, agl_m=agl_m, speed_mps=speed_mps, n_frames=n_frames,
            lateral_offset_m=lateral_offset_m, camera=cam,
        )
        sim = GeomSim(camera=cam, ground_elev=0.0)
        trial_seed = int(rng.integers(0, 2**31 - 1))
        frames = sim.run(path, error_model=sim_model, seed=trial_seed)
        obs = [
            FuseObservation(pose=f.pose_meas, camera=cam, pixel=f.pixel_meas)
            for f in frames
        ]
        result = fuser.fuse(obs)
        if result is None:
            continue
        valid += 1

        origin = result.coord
        r_true = _enu_offset(origin, target)  # true target relative to the estimate, ENU m
        cov = result.cov_report
        try:
            d2 = float(r_true @ np.linalg.inv(cov) @ r_true)
        except np.linalg.LinAlgError:
            continue
        if d2 <= _CHI2_2_95:
            covered += 1
        nees_vals.append(d2)
        r95s.append(result.r95_m)

    coverage = covered / valid if valid else 0.0
    mean_nees = float(np.mean(nees_vals)) if nees_vals else 0.0
    median_r95 = float(np.median(r95s)) if r95s else 0.0
    return CoverageRow(
        name="trial", coverage=coverage, mean_nees=mean_nees,
        median_r95_m=median_r95, n_frames=n_frames, n_trials=valid,
    )


def run_coverage_matrix(n_trials: int = 2000, seed: int = 0) -> list[CoverageRow]:
    """The full coverage matrix (research gate §5). Each row pairs a sim noise model with the
    fuser's assumed model; the PASS conditions (not the predicted numbers) are the contract.

    Includes the mandatory out-of-schema TIME-SYNC rows and the upward SIGMA_OVERESTIMATE row
    (the two-sided / meta-assertion teeth)."""
    base = SensorErrorModel()
    rng = np.random.default_rng(seed)

    def s(seed_off: int) -> int:
        return int(rng.integers(0, 2**31 - 1)) + seed_off

    specs: list[tuple[str, SensorErrorModel, SensorErrorModel, int]] = [
        ("matched_control", base, base, 30),
        (
            "sigma_underestimate",
            dataclasses.replace(base, yaw_jitter_sigma_deg=1.5 * base.yaw_jitter_sigma_deg),
            base,
            30,
        ),
        (
            "sigma_overestimate",
            dataclasses.replace(base, yaw_jitter_sigma_deg=0.6 * base.yaw_jitter_sigma_deg),
            base,
            30,
        ),
        (
            "heading_bias_crab",
            dataclasses.replace(base, crab_angle_deg=12.0, heading_bias_sigma_deg=2.0),
            dataclasses.replace(base, crab_angle_deg=0.0, heading_bias_sigma_deg=2.0),
            30,
        ),
        (
            "gps_heavy_tail",
            dataclasses.replace(base, gps_dist="studentt", gps_studentt_dof=3.0),
            base,
            30,
        ),
        ("time_sync_50ms", dataclasses.replace(base, t_sync_offset_ms=50.0), base, 30),
        ("time_sync_100ms", dataclasses.replace(base, t_sync_offset_ms=100.0), base, 30),
        ("time_sync_200ms", dataclasses.replace(base, t_sync_offset_ms=200.0), base, 30),
    ]

    rows: list[CoverageRow] = []
    for name, sim_m, fus_m, nf in specs:
        row = coverage_trial(sim_m, fus_m, n_frames=nf, n_trials=n_trials, seed=s(0))
        rows.append(dataclasses.replace(row, name=name))
    return rows
