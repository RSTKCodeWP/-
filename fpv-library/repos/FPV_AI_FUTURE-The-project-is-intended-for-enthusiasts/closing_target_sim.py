"""G1/G2 renderer: a deterministic closing-geometry winged-UAV thermal sequence.

The V3 scenario library exercised individual nuisances; this asset combines the ones that wreck
a *closing* engagement into one parameterized sequence, so the renderer-blocked acceptance numbers
(R5 aimpoint-walk, R9 scale-warp, R10 distractor pull-off) can be graded:

  * an ELONGATED body (winged UAV) whose subtense GROWS with closure (sigma * growth**k),
  * ASPECT rotation head-on -> beam over the run,
  * a bright MOTOR HOTSPOT that WALKS along the body major axis as aspect rotates -- the exact
    disturbance that walks the top-hat centroid off the airframe (R5),
  * an optional crossing DISTRACTOR sweeping through the gate (G2, for R10/R7).

The target stays boresighted (the seeker keeps it centred); pixel-domain motion is the hotspot
walk + aspect rotation + closure growth. Pure function of frame index + seed (deterministic).
"""

from __future__ import annotations

import math

import numpy as np

_H, _W = 512, 640


def winged_uav_frame(k: int, n: int, *, base_sigma: float = 4.0, growth: float = 1.04,
                     body_amp: float = 450.0, hotspot_amp: float = 3200.0,
                     hotspot_walk_px: float = 16.0, aspect_deg: float = 90.0,
                     distractor: bool = False, seed: int = 0) -> tuple[np.ndarray, tuple[float, float]]:
    """One frame of the closing winged-UAV sequence + the true body-centre pixel (cx, cy)."""
    rng = np.random.default_rng((seed * 911 + k) & 0xFFFFFFFF)
    cx, cy = _W / 2.0, _H / 2.0
    t = k / max(n - 1, 1)
    sigma = base_sigma * (growth ** k)
    aspect = math.radians(aspect_deg * t)
    yy, xx = np.mgrid[0:_H, 0:_W]
    dx, dy = xx - cx, yy - cy
    ca, sa = math.cos(aspect), math.sin(aspect)
    u = dx * ca + dy * sa                      # body major axis (elongated)
    v = -dx * sa + dy * ca                      # minor axis
    body = body_amp * np.exp(-(u ** 2 / (2 * (2.4 * sigma) ** 2) + v ** 2 / (2 * sigma ** 2)))
    # motor hotspot walks along the major axis with aspect (head-on: centred; beam: offset)
    hx = cx + hotspot_walk_px * (t - 0.5) * ca
    hy = cy + hotspot_walk_px * (t - 0.5) * sa
    hot = hotspot_amp * np.exp(-((xx - hx) ** 2 + (yy - hy) ** 2) / (2 * 1.6 ** 2))
    f = 4096.0 + rng.normal(0, 4, (_H, _W)) + body + hot
    if distractor:
        dxc = 0.18 * _W + 0.64 * _W * t         # sweeps across the frame
        f += 0.85 * body_amp * np.exp(-((xx - dxc) ** 2 + (yy - (cy + 36)) ** 2) / (2 * 3.0 ** 2))
    return np.clip(f, 0, 65535).astype(np.uint16), (cx, cy)


def sequence(n: int = 60, *, distractor: bool = False, seed: int = 0):
    """Yield (frame_u16, (cx, cy)) for a full closing run."""
    return [winged_uav_frame(k, n, distractor=distractor, seed=seed) for k in range(n)]
