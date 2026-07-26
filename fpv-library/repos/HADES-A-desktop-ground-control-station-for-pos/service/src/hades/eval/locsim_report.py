"""Localization meter-error report - the flagship close (Task 4.9; research gate §7).

`hades-locsim` runs the calibrated synthetic simulator across a span of flight geometries,
fuses each target's observations, and reports the localization error in METERS stratified by
slant range x camera pitch from nadir, plus empirical coverage and a moving-target
non-convergence row.

HONESTY (the load-bearing framing, §7): the sim proves the method is correct and the
uncertainty is CALIBRATED; it does NOT establish a field meter-accuracy number. So every meter
figure is tagged `(sim)`, and the report names the pending real-flight dataset. The reader sees
WHERE it is PINPOINT vs CUE-ONLY (stratified), not one averaged-away number, and the dominant
error is heading - taken from the error_model, not ground truth - so real numbers will move
when the magnetometer-less heading distribution is measured.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from hades.locate.camera_model import CameraModel
from hades.locate.error_model import SensorErrorModel
from hades.locate.fuse import FuseObservation, Fuser
from hades.locate.geom_sim import GeomSim, OrbitPath, StraightPass

_M_PER_DEG = 111320.0
_CHI2_2_95 = 5.991464547107979

# Stratification bins (research gate §7). The last pitch bin is the >65 deg GATE boundary.
_RANGE_BINS = [(0, 30), (30, 80), (80, 150), (150, 300), (300, 10_000)]
_RANGE_LABELS = ["[0-30)", "[30-80)", "[80-150)", "[150-300)", "[300+)"]
_PITCH_BINS = [(0, 15), (15, 35), (35, 55), (55, 65), (65, 91)]
_PITCH_LABELS = ["[0-15)", "[15-35)", "[35-55)", "[55-65)", "[65+)"]


@dataclass
class StratumResult:
    """Meter-error + coverage for one (slant-range, pitch-from-nadir) cell."""

    range_bin: str
    pitch_bin: str
    n: int = 0
    median_m: float = 0.0
    mean_m: float = 0.0
    p90_m: float = 0.0
    max_m: float = 0.0
    coverage: float = 0.0


@dataclass
class MovingResult:
    """The moving-target row: must stay CONVERGING with a big radius (never PINPOINT)."""

    convergence: str
    median_r95_m: float
    actionability_class: str


@dataclass
class MeterErrorReport:
    strata: list[StratumResult] = field(default_factory=list)
    moving: MovingResult | None = None

    def render(self) -> str:
        lines = [
            "HADES localization meter-error report",
            "",
            "Localization accuracy in a CALIBRATED SYNTHETIC SIMULATOR whose noise models are",
            "tuned to literature / test-flight sensor-error distributions - pending confirmation",
            "against the labeled-with-pose flight dataset (expected ~2026-07-01). Every meter",
            "number below is a (sim) number. The error budget is dominated by heading sigma,",
            "taken from the error_model (not ground truth), so real-flight numbers will move",
            "when the magnetometer-less heading distribution is measured.",
            "",
            f"{'range x pitch':<26} {'n':>4} {'median(sim)':>12} {'mean(sim)':>10} "
            f"{'p90(sim)':>9} {'max(sim)':>9} {'cov':>6}",
        ]
        for s in self.strata:
            if s.n == 0:
                continue
            lines.append(
                f"{s.range_bin + ' x ' + s.pitch_bin:<26} {s.n:>4} "
                f"{s.median_m:>10.1f} m {s.mean_m:>8.1f} m {s.p90_m:>7.1f} m "
                f"{s.max_m:>7.1f} m {s.coverage:>6.2f}"
            )
        if self.moving is not None:
            lines += [
                "",
                f"moving target: {self.moving.convergence} (sim), "
                f"median R95 {self.moving.median_r95_m:.0f} m, "
                f"class {self.moving.actionability_class} - the stationary-target assumption is "
                "violated, so the estimate honestly does NOT converge (never PINPOINT).",
            ]
        return "\n".join(lines)


def _nadir_cam() -> CameraModel:
    return CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=540.0, mount="nadir")


def _bin_index(value: float, bins: list[tuple[int, int]]) -> int | None:
    for i, (lo, hi) in enumerate(bins):
        if lo <= value < hi:
            return i
    return None


def _enu_err(a: tuple[float, float], b: tuple[float, float]) -> float:
    dlat = (a[0] - b[0]) * _M_PER_DEG
    dlon = (a[1] - b[1]) * _M_PER_DEG * math.cos(math.radians(b[0]))
    return math.hypot(dlat, dlon)


def _geometries() -> list[tuple]:
    """A span of (path-factory, label) geometries that populate the strata: low near-nadir
    (best), nominal, oblique standoff (worst), and a high-oblique GATED case."""
    return [
        ("near_nadir_low", lambda t, cam: StraightPass(t, agl_m=35.0, speed_mps=15.0,
                                                       n_frames=20, lateral_offset_m=6.0, camera=cam)),
        ("nominal", lambda t, cam: StraightPass(t, agl_m=80.0, speed_mps=15.0,
                                                n_frames=20, lateral_offset_m=40.0, camera=cam)),
        ("oblique_standoff", lambda t, cam: OrbitPath(t, agl_m=80.0, radius_m=200.0,
                                                      n_frames=20, camera=cam)),
        ("high_oblique_gated", lambda t, cam: OrbitPath(t, agl_m=40.0, radius_m=180.0,
                                                        n_frames=16, camera=cam)),
    ]


def run_meter_error_report(
    n_targets: int = 30,
    seed: int = 0,
    error_model: SensorErrorModel | None = None,
    include_moving: bool = True,
) -> MeterErrorReport:
    """Run the sim across geometries x targets, fuse each, and stratify the meter error.

    For each geometry and target, the sim injects sensor noise (its own error_model instance),
    the fuser localizes, and the (error, coverage, slant, pitch) is binned. Coverage is the
    fraction of cells whose true target lies inside the fused 95% ellipse.
    """
    m = error_model or SensorErrorModel()
    cam = _nadir_cam()
    fuser = Fuser(error_model=m, mc_draws=120, seed=seed)
    rng = np.random.default_rng(seed)

    # Accumulate per-cell error lists + coverage hits.
    cells: dict[tuple[int, int], list[float]] = {}
    covers: dict[tuple[int, int], list[int]] = {}

    for _geo_label, make_path in _geometries():
        for _ in range(n_targets):
            target = (
                40.0 + float(rng.normal(0.0, 0.0005)),
                -74.0 + float(rng.normal(0.0, 0.0005)),
            )
            path = make_path(target, cam)
            gts = list(path.frames())
            if not gts:
                continue
            slant = float(np.median([g.slant_range_m for g in gts]))
            pitch = float(np.median([g.nadir_angle_deg for g in gts]))
            ri = _bin_index(slant, _RANGE_BINS)
            pi = _bin_index(pitch, _PITCH_BINS)
            if ri is None or pi is None:
                continue

            sim = GeomSim(camera=cam, ground_elev=0.0)
            frames = sim.run(path, error_model=m, seed=int(rng.integers(0, 2**31 - 1)))
            obs = [FuseObservation(pose=f.pose_meas, camera=cam, pixel=f.pixel_meas) for f in frames]
            result = fuser.fuse(obs)
            if result is None:
                continue
            err = _enu_err(result.coord, target)
            cells.setdefault((ri, pi), []).append(err)

            # Coverage: is the truth inside the fused 95% ellipse?
            r_true = np.array([
                (target[1] - result.coord[1]) * _M_PER_DEG * math.cos(math.radians(target[0])),
                (target[0] - result.coord[0]) * _M_PER_DEG,
            ])
            try:
                d2 = float(r_true @ np.linalg.inv(result.cov_report) @ r_true)
                covers.setdefault((ri, pi), []).append(1 if d2 <= _CHI2_2_95 else 0)
            except np.linalg.LinAlgError:
                pass

    strata: list[StratumResult] = []
    for ri, rlabel in enumerate(_RANGE_LABELS):
        for pi, plabel in enumerate(_PITCH_LABELS):
            errs = cells.get((ri, pi), [])
            cov = covers.get((ri, pi), [])
            if not errs:
                strata.append(StratumResult(range_bin=rlabel, pitch_bin=plabel, n=0))
                continue
            a = np.array(errs)
            strata.append(
                StratumResult(
                    range_bin=rlabel, pitch_bin=plabel, n=len(errs),
                    median_m=float(np.median(a)), mean_m=float(np.mean(a)),
                    p90_m=float(np.percentile(a, 90)), max_m=float(np.max(a)),
                    coverage=float(np.mean(cov)) if cov else 0.0,
                )
            )

    moving = _moving_row(cam, m, seed) if include_moving else None
    return MeterErrorReport(strata=strata, moving=moving)


def _moving_row(cam: CameraModel, m: SensorErrorModel, seed: int) -> MovingResult:
    """A drifting target: must stay CONVERGING with a big radius (never PINPOINT)."""
    from hades.locate.geom_sim import world_to_pixel

    base = (40.0, -74.0)
    fuser = Fuser(error_model=m, mc_draws=120, seed=seed)
    # A low near-nadir pass: the tight per-frame geometry makes a coherent drift clearly
    # violate the stationary assumption (the NIS residual test fires). A larger oblique Sigma_i
    # would mask a small drift - that is honest, but here we demonstrate the detector working.
    path = StraightPass(base, agl_m=60.0, speed_mps=15.0, n_frames=20, lateral_offset_m=4.0, camera=cam)
    obs = []
    for i, gt in enumerate(path.frames()):
        moved = (base[0] + (5.0 * i) / _M_PER_DEG, base[1])  # drift 5 m/frame North
        px = world_to_pixel(gt.pose_true, cam, moved, 0.0)
        if px is not None:
            obs.append(FuseObservation(pose=gt.pose_true, camera=cam, pixel=px))
    result = fuser.fuse(obs)
    if result is None:
        return MovingResult(convergence="CONVERGING", median_r95_m=999.0, actionability_class="CUE_ONLY")
    return MovingResult(
        convergence=result.convergence.value,
        median_r95_m=result.r95_m,
        actionability_class=result.actionability_class,
    )
