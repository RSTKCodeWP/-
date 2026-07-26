"""Synthetic frame source -- watch the seeker in the browser dashboard with no camera.

Two scenes:
  * "sweep"    -- a fixed-size hot target on a Lissajous path + star hard-negatives.
                  Shows detection / lock / the command vector tracking lateral motion.
  * "approach" -- a CLOSING engagement: the target GROWS (looming) frame to frame while
                  drifting toward boresight, then resets. Shows what happens as the target
                  gets bigger -- looming building, then the terminal large-blob regime where
                  the small-target detector degrades (the ENDGAME gap, master-plan Phase C).

Run:  PYTHONPATH=fpv python -m fpv_ai.bench --sim --port 8081           (sweep)
      PYTHONPATH=fpv python -m fpv_ai.bench --sim --sim-mode approach --port 8081
"""

from __future__ import annotations

import math

import numpy as np


class SimFrameSource:
    """A ``FrameSource`` that replays a synthetic scene (loops forever)."""

    def __init__(self, *, mode: str = "sweep", n_frames: int = 600, n_stars: int = 4,
                 seed: int = 7, width: int = 640, height: int = 512) -> None:
        self._w, self._h = width, height
        self._rng = np.random.default_rng(seed)
        if mode == "approach":
            self._frames = self._make_approach(n_frames, n_stars)
        else:
            self._frames = self._make_sweep(n_frames, n_stars)
        self._i = 0

    # ---- sweep (fixed-size target) -------------------------------------------
    def _make_sweep(self, n_frames: int, n_stars: int) -> list[np.ndarray]:
        from fpv.seeker.thermal_sim import ThermalSceneConfig, ThermalSimulator
        w, h = self._w, self._h

        def traj(fid: int) -> tuple[float, float]:
            return (w / 2.0 + 95.0 * math.sin(fid * 0.045),
                    h / 2.0 + 55.0 * math.sin(fid * 0.028 + 1.1))

        sim = ThermalSimulator(
            ThermalSceneConfig(width=w, height=h, n_stars=n_stars, ffc_freeze_interval=0),
            trajectory_fn=traj,
        )
        return [f for (f, _gt) in sim.generate(n_frames)]

    # ---- approach (growing target -> looming + terminal) ---------------------
    def _make_approach(self, n_frames: int, n_stars: int, *, bg: float = 4096.0,
                       peak: float = 2200.0, noise: float = 8.0) -> list[np.ndarray]:
        w, h = self._w, self._h
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        # fixed star hard-negatives (dimmer than the target peak)
        stars = [(float(self._rng.integers(40, w - 40)), float(self._rng.integers(40, h - 40)))
                 for _ in range(n_stars)]
        star_field = np.zeros((h, w), np.float32)
        for sx, sy in stars:
            star_field += 0.5 * peak * np.exp(-((xx - sx) ** 2 + (yy - sy) ** 2) / (2 * 1.6 ** 2))

        frames: list[np.ndarray] = []
        leg = max(40, n_frames // 3)          # one closing run, then loop (repeat the run)
        for fid in range(n_frames):
            t = (fid % leg) / float(leg)       # 0 -> 1 across one approach
            # sigma grows from a 1-2 px point to a frame-filling blob (looming)
            sigma = 1.5 + (min(h, w) * 0.45) * (t ** 2)
            # target drifts from a small lateral offset toward boresight as it closes
            cx = w / 2.0 + (1.0 - t) * 70.0 * math.sin(fid * 0.05)
            cy = h / 2.0 + (1.0 - t) * 45.0 * math.cos(fid * 0.04)
            f = bg + self._rng.normal(0.0, noise, (h, w)).astype(np.float32) + star_field
            f += peak * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma ** 2))
            frames.append(np.clip(f, 0, 65535).astype(np.uint16))
        return frames

    # ---- FrameSource protocol -------------------------------------------------
    def read(self) -> np.ndarray | None:
        if not self._frames:
            return None
        f = self._frames[self._i % len(self._frames)]
        self._i += 1
        return f

    def close(self) -> None:
        pass
