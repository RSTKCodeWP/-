"""Generate the dense localization-error surface data the Wolfram 3D render reads.

The routine meter-error report (`hades-locsim`) samples only a handful of flight geometries,
so it populates 3 cells of the range x pitch plane - enough for a bar chart, too sparse for a
smooth 3D surface. This helper sweeps a dense grid of (slant range, camera pitch) by varying
the drone AGL and lateral standoff, runs the REAL fuser at each grid point against known
ground truth, and writes the median localization error per cell. Every value is a real sim
output (kind=sim), never interpolated or invented - empty cells (geometry the path cannot
reach) are written as NaN so Wolfram can drop them.

Run from the repo (the `service` venv has the deps):

    cd service && uv run python ../docs/documentation/wolfram/make_surface_data.py

Writes: docs/documentation/data/localization_surface.csv
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np

from hades.locate.camera_model import CameraModel
from hades.locate.error_model import SensorErrorModel
from hades.locate.fuse import FuseObservation, Fuser
from hades.locate.geom_sim import GeomSim, OrbitPath, StraightPass

_M_PER_DEG = 111320.0


def _enu_err(a: tuple[float, float], b: tuple[float, float]) -> float:
    dlat = (a[0] - b[0]) * _M_PER_DEG
    dlon = (a[1] - b[1]) * _M_PER_DEG * math.cos(math.radians(b[0]))
    return math.hypot(dlat, dlon)


def make_surface(out_csv: Path, *, seed: int = 0, targets_per_cell: int = 6) -> Path:
    cam = CameraModel(fx=1000.0, fy=1000.0, cx=960.0, cy=540.0, mount="nadir")
    model = SensorErrorModel()
    fuser = Fuser(error_model=model, mc_draws=120, seed=seed)
    rng = np.random.default_rng(seed)

    # The sweep traces the (slant, pitch) plane with two real flight shapes (the fixed O4
    # mount has no gimbal, so camera pitch comes from the airframe, not a lateral offset):
    #   - StraightPass at varied AGL  -> the near-nadir, low-pitch rows (pitch ~0 deg).
    #   - OrbitPath at varied (agl, radius) -> the oblique rows, where airframe pitch aims
    #     the mount and camera pitch = atan2(radius, agl), genuinely sweeping the pitch axis.
    straight = [(agl, off) for agl in (30.0, 50.0, 80.0, 120.0, 180.0)
                for off in (4.0, 20.0, 50.0)]
    orbits = [(agl, r) for agl in (40.0, 60.0, 90.0, 130.0)
              for r in (40.0, 90.0, 160.0, 260.0)]

    cells: dict[tuple[float, float], list[float]] = {}

    def _accumulate(path, target: tuple[float, float]) -> None:
        gts = list(path.frames())
        if not gts:
            return
        slant = float(np.median([g.slant_range_m for g in gts]))
        pitch = float(np.median([g.nadir_angle_deg for g in gts]))
        sim = GeomSim(camera=cam, ground_elev=0.0)
        frames = sim.run(path, error_model=model, seed=int(rng.integers(0, 2**31 - 1)))
        obs = [FuseObservation(pose=f.pose_meas, camera=cam, pixel=f.pixel_meas)
               for f in frames]
        result = fuser.fuse(obs)
        if result is None:
            return
        err = _enu_err(result.coord, target)
        # Snap to a regular lattice so Wolfram gets a clean grid.
        key = (round(slant / 25.0) * 25.0, round(pitch / 10.0) * 10.0)
        cells.setdefault(key, []).append(err)

    def _rand_target() -> tuple[float, float]:
        return (40.0 + float(rng.normal(0.0, 0.0004)), -74.0 + float(rng.normal(0.0, 0.0004)))

    for agl, off in straight:
        for _ in range(targets_per_cell):
            t = _rand_target()
            _accumulate(StraightPass(t, agl_m=agl, speed_mps=15.0, n_frames=20,
                                     lateral_offset_m=off, camera=cam), t)
    for agl, radius in orbits:
        for _ in range(targets_per_cell):
            t = _rand_target()
            _accumulate(OrbitPath(t, agl_m=agl, radius_m=radius, n_frames=20, camera=cam), t)

    slants = sorted({k[0] for k in cells})
    pitches = sorted({k[1] for k in cells})
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["slant_range_m", "pitch_deg", "median_err_m", "n", "kind"])
        for s in slants:
            for p in pitches:
                errs = cells.get((s, p), [])
                if errs:
                    w.writerow([s, p, round(float(np.median(errs)), 2), len(errs), "sim"])
                else:
                    w.writerow([s, p, "NaN", 0, "sim"])
    print(f"wrote surface grid ({len(slants)}x{len(pitches)}) to {out_csv}")
    return out_csv


if __name__ == "__main__":
    repo = Path(__file__).resolve().parents[3]
    make_surface(repo / "docs" / "documentation" / "data" / "localization_surface.csv")
