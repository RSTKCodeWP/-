"""Synthetic thermal scene generator for S1 sim-perception testing.

Produces a deterministic sequence of 14-bit Y16-equivalent uint16 frames that
model a FLIR Boson 640 (non-radiometric) imaging a night sky with:

* Cold-sky background with low-frequency spatial gradient and read noise.
* ONE hot target — a 2-D Gaussian spot whose centroid follows a caller-supplied
  trajectory function (sub-pixel accuracy).
* N static star point-sources (hard negatives at near-target brightness).
* Optional FFC-FREEZE events: the previous output frame is repeated for ~30
  frames and ``ffc_state`` is set to ``"FREEZE"`` / ``"RECOVERING"``.
* Camera-temperature drift: a slowly-varying additive and multiplicative offset
  applied to the whole frame so that the adaptive threshold must continuously
  re-base (exercises the non-radiometric drift scenario).

All randomness is seeded through an explicit ``numpy.random.Generator`` — no
global RNG state is touched.  Tests pass a fixed seed for reproducibility.

Typical usage
-------------
::

    from fpv.seeker.thermal_sim import ThermalSceneConfig, ThermalSimulator

    cfg = ThermalSceneConfig(width=640, height=512, n_stars=8, seed=42)
    sim = ThermalSimulator(cfg)
    for frame, gt in sim.generate(n_frames=300):
        # frame: np.ndarray shape (H, W) dtype uint16
        # gt:    GroundTruth  (named fields)
        ...
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import numpy.typing as npt


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ThermalSceneConfig:
    """Parameters that fully describe the synthetic scene.

    Attributes
    ----------
    width, height:
        Frame dimensions in pixels.  Default 640×512 (Boson native).
    sky_base_counts:
        Mean background count level for the cold sky.  14-bit range → ~0–16383.
        Default 4096 corresponds to a scene temperature of ~260 K on a typical
        non-radiometric core with a mid-gain table.
    sky_gradient_amplitude:
        Peak-to-peak amplitude of a slow sinusoidal spatial gradient added to
        the background.  Models warm-ground / cold-zenith illumination.
    read_noise_sigma:
        Standard deviation of per-pixel Gaussian read noise (in counts).
    target_peak_above_bg:
        How many counts the target peak rises above the local background.
        Controls the scene-level SNR.
    target_sigma_px:
        Gaussian sigma of the target PSF in pixels.  ~1–2 px models a drone
        at 100–200 m through a 24 mm lens.
    n_stars:
        Number of static point sources (stars / fixed warm spots).  These are
        deliberately seeded at similar brightness as the target to act as hard
        negatives for the false-alarm gate.
    star_peak_fraction:
        Star peak counts relative to ``target_peak_above_bg``.  Range (0, 1].
        Set < 1 to make stars slightly dimmer than the target.
    ffc_freeze_interval:
        If > 0, an FFC freeze event is injected every this many *real* frames.
        During a freeze the last valid frame is repeated for ``ffc_freeze_frames``
        frames and ``ffc_state`` is set to ``"FREEZE"`` / ``"RECOVERING"``.
    ffc_freeze_frames:
        Number of frozen/recovering frames per FFC event.  ~30 at 60 Hz ≈ 0.5 s.
    cam_temp_drift_rate_cts_per_frame:
        Rate of camera-housing temperature induced additive count drift
        (counts per frame).  Models the slow warm-up of the sensor housing.
        The drift reverses to keep cam_temp from diverging.
    cam_temp_gain_drift_rate:
        Rate of multiplicative gain drift per frame (dimensionless per frame).
        Small positive means counts increase slightly as cam heats up.
    cam_temp_start_c:
        Synthetic camera housing temperature at frame 0 (°C).
    cam_temp_amplitude_c:
        Peak-to-peak amplitude of a sinusoidal cam-temp oscillation around the
        start temperature (°C).  Period = ``cam_temp_period_frames`` frames.
    cam_temp_period_frames:
        Period of the sinusoidal cam-temp oscillation.
    seed:
        Seed for the numpy random generator.  Pass ``None`` for a random seed.
    """

    width: int = 640
    height: int = 512

    # sky
    sky_base_counts: int = 4096
    sky_gradient_amplitude: float = 200.0
    read_noise_sigma: float = 12.0

    # target
    target_peak_above_bg: float = 1800.0
    target_sigma_px: float = 1.5

    # stars (hard negatives)
    n_stars: int = 12
    star_peak_fraction: float = 0.55   # stars are ~55 % of target brightness

    # FFC freeze
    ffc_freeze_interval: int = 90      # every 90 frames inject an FFC event
    ffc_freeze_frames: int = 30        # 30 frozen frames per event (~0.5 s @ 60 Hz)

    # cam-temp drift (non-radiometric count drift)
    cam_temp_drift_rate_cts_per_frame: float = 0.6
    cam_temp_gain_drift_rate: float = 2e-5
    cam_temp_start_c: float = 25.0
    cam_temp_amplitude_c: float = 3.0
    cam_temp_period_frames: int = 600

    seed: int | None = 42


# ---------------------------------------------------------------------------
# Ground-truth record
# ---------------------------------------------------------------------------

@dataclass
class GroundTruth:
    """Per-frame ground truth from the synthetic scene generator.

    Attributes
    ----------
    frame_id:
        Zero-based frame index within the current ``generate()`` call.
    target_centroid_px:
        True sub-pixel centroid ``(x, y)`` of the target in the image.
    target_area_px:
        Area of the target spot at the 50 % peak-height contour, in pixels.
        Analytically: ``pi * (sigma * sqrt(2*ln(2))) ** 2`` ≈ ``pi * (1.177 * sigma) ** 2``.
    ffc_state:
        ``"READY"`` | ``"FREEZE"`` | ``"RECOVERING"``.
    cam_temp_c:
        Camera housing temperature for this frame (°C).
    star_positions_px:
        List of ``(x, y)`` positions of the static star sources.
    is_target_visible:
        False during FFC-freeze frames (the target is in a frozen copy of the
        previous frame, so the centroid is frozen too but the data is stale).
    """

    frame_id: int
    target_centroid_px: tuple[float, float]
    target_area_px: float
    ffc_state: str
    cam_temp_c: float
    star_positions_px: list[tuple[float, float]]
    is_target_visible: bool = True


# ---------------------------------------------------------------------------
# Trajectory helpers
# ---------------------------------------------------------------------------

# A trajectory function maps (frame_id: int) -> (x_px: float, y_px: float)
TrajectoryFn = Callable[[int], tuple[float, float]]


def linear_trajectory(
    *,
    x0: float,
    y0: float,
    vx_px_per_frame: float = 0.3,
    vy_px_per_frame: float = 0.15,
) -> TrajectoryFn:
    """Return a constant-velocity trajectory function."""
    def _fn(frame_id: int) -> tuple[float, float]:
        return (x0 + vx_px_per_frame * frame_id, y0 + vy_px_per_frame * frame_id)
    return _fn


def sinusoidal_trajectory(
    *,
    x0: float,
    y0: float,
    ax: float = 20.0,
    ay: float = 15.0,
    period_frames: float = 120.0,
) -> TrajectoryFn:
    """Return a sinusoidal (evasive) trajectory function."""
    def _fn(frame_id: int) -> tuple[float, float]:
        phase = 2.0 * math.pi * frame_id / period_frames
        return (x0 + ax * math.sin(phase), y0 + ay * math.cos(phase * 0.7))
    return _fn


# ---------------------------------------------------------------------------
# Core simulator
# ---------------------------------------------------------------------------

class ThermalSimulator:
    """Deterministic synthetic thermal scene generator.

    Parameters
    ----------
    config:
        Scene configuration.  All parameters are frozen at construction time.
    trajectory_fn:
        A callable ``(frame_id: int) -> (x_px, y_px)`` giving the true sub-pixel
        centroid of the target for each frame.  Defaults to a slow linear
        drift starting from the image centre.
    ego_drift_fn:
        Optional callable ``(frame_id: int) -> (dx_px, dy_px)`` modelling
        global image shift due to platform motion.  This shift is applied to
        BOTH stars and the target (rigid whole-image translation).  Defaults
        to no ego drift.
    """

    def __init__(
        self,
        config: ThermalSceneConfig | None = None,
        *,
        trajectory_fn: TrajectoryFn | None = None,
        ego_drift_fn: Callable[[int], tuple[float, float]] | None = None,
    ) -> None:
        self.cfg = config or ThermalSceneConfig()
        self._rng = np.random.default_rng(self.cfg.seed)

        cfg = self.cfg
        # Default trajectory: slow linear drift from image centre
        if trajectory_fn is None:
            self._trajectory_fn: TrajectoryFn = linear_trajectory(
                x0=cfg.width / 2.0,
                y0=cfg.height / 2.0,
                vx_px_per_frame=0.3,
                vy_px_per_frame=0.15,
            )
        else:
            self._trajectory_fn = trajectory_fn

        self._ego_drift_fn = ego_drift_fn

        # Pre-compute static sky gradient (low-frequency warm blob at bottom)
        self._sky_gradient = self._make_sky_gradient()

        # Pre-place star positions (fixed in image coordinates)
        self._star_positions = self._place_stars()

    # ── public API ────────────────────────────────────────────────────────────

    def generate(
        self, n_frames: int
    ) -> list[tuple[npt.NDArray[np.uint16], GroundTruth]]:
        """Generate ``n_frames`` synthetic frames.

        Returns
        -------
        list of (frame_u16, ground_truth)
            ``frame_u16`` is a ``(H, W)`` uint16 array.
            ``ground_truth`` contains the true target centroid and metadata.
        """
        results: list[tuple[npt.NDArray[np.uint16], GroundTruth]] = []

        # Mutable per-run state
        cam_temp_c = self.cfg.cam_temp_start_c
        additive_drift: float = 0.0
        gain_drift: float = 1.0        # accumulated, mirrors additive_drift
        drift_direction: float = 1.0  # reverses to prevent runaway

        last_valid_frame: npt.NDArray[np.float64] | None = None
        freeze_countdown: int = 0
        ffc_state: str = "READY"

        # Frame counter relative to this generate() call
        for frame_id in range(n_frames):
            # ── cam-temp model (sinusoidal oscillation) ───────────────────
            phase = 2.0 * math.pi * frame_id / self.cfg.cam_temp_period_frames
            cam_temp_c = (
                self.cfg.cam_temp_start_c
                + self.cfg.cam_temp_amplitude_c * math.sin(phase)
            )

            # Additive drift that reverses every 300 frames to stay bounded
            if frame_id % 300 == 0 and frame_id > 0:
                drift_direction *= -1.0
            additive_drift += drift_direction * self.cfg.cam_temp_drift_rate_cts_per_frame
            # Gain drift: accumulated per-frame (smooth, continuous reversal)
            # Clamped to [0.95, 1.05] to stay bounded.
            gain_drift = max(0.95, min(1.05,
                gain_drift + drift_direction * self.cfg.cam_temp_gain_drift_rate))

            # ── FFC freeze logic ──────────────────────────────────────────
            ffc_interval = self.cfg.ffc_freeze_interval
            if ffc_interval > 0 and frame_id > 0 and frame_id % ffc_interval == 0:
                freeze_countdown = self.cfg.ffc_freeze_frames

            if freeze_countdown > 0:
                freeze_countdown -= 1
                # Emit stale frame
                if last_valid_frame is not None:
                    frozen = last_valid_frame.copy()
                else:
                    frozen = self._empty_sky(additive_drift, gain_drift)

                # First half of freeze = FREEZE, second half = RECOVERING
                if freeze_countdown > self.cfg.ffc_freeze_frames // 2:
                    ffc_state = "FREEZE"
                else:
                    ffc_state = "RECOVERING"

                # Target centroid is stale during freeze (use last valid)
                target_xy = self._trajectory_fn(frame_id)
                frame_u16 = _float64_to_u16(frozen)
                gt = GroundTruth(
                    frame_id=frame_id,
                    target_centroid_px=target_xy,
                    target_area_px=self._target_area(),
                    ffc_state=ffc_state,
                    cam_temp_c=cam_temp_c,
                    star_positions_px=list(self._star_positions),
                    is_target_visible=False,
                )
                results.append((frame_u16, gt))
                continue

            ffc_state = "READY"

            # ── ego drift ─────────────────────────────────────────────────
            dx_ego, dy_ego = (0.0, 0.0)
            if self._ego_drift_fn is not None:
                dx_ego, dy_ego = self._ego_drift_fn(frame_id)

            # ── target centroid ───────────────────────────────────────────
            tx_base, ty_base = self._trajectory_fn(frame_id)
            target_x = tx_base + dx_ego
            target_y = ty_base + dy_ego

            # ── render frame ──────────────────────────────────────────────
            frame_f64 = self._render_frame(
                target_x=target_x,
                target_y=target_y,
                additive_drift=additive_drift,
                gain_drift=gain_drift,
                dx_ego=dx_ego,
                dy_ego=dy_ego,
            )

            last_valid_frame = frame_f64.copy()

            frame_u16 = _float64_to_u16(frame_f64)
            gt = GroundTruth(
                frame_id=frame_id,
                target_centroid_px=(target_x, target_y),
                target_area_px=self._target_area(),
                ffc_state=ffc_state,
                cam_temp_c=cam_temp_c,
                star_positions_px=list(self._star_positions),
                is_target_visible=True,
            )
            results.append((frame_u16, gt))

        return results

    # ── private helpers ───────────────────────────────────────────────────────

    def _make_sky_gradient(self) -> npt.NDArray[np.float64]:
        """Low-frequency warm-ground / cold-sky gradient background."""
        cfg = self.cfg
        yy = np.linspace(0.0, 1.0, cfg.height)[:, np.newaxis]
        xx = np.linspace(0.0, 1.0, cfg.width)[np.newaxis, :]
        # Warm bottom edge (ground radiation) + slight horizontal variation
        grad = cfg.sky_gradient_amplitude * (
            0.6 * yy + 0.3 * np.sin(2.0 * math.pi * xx) * yy + 0.1 * np.cos(math.pi * xx)
        )
        return grad.astype(np.float64)

    def _place_stars(self) -> list[tuple[float, float]]:
        """Randomly place ``n_stars`` point-sources (fixed across the run)."""
        cfg = self.cfg
        margin = 20
        xs = self._rng.uniform(margin, cfg.width - margin, size=cfg.n_stars).tolist()
        ys = self._rng.uniform(margin, cfg.height - margin, size=cfg.n_stars).tolist()
        return list(zip(xs, ys))

    def _target_area(self) -> float:
        """Theoretical 50%-contour area of the Gaussian spot."""
        sigma = self.cfg.target_sigma_px
        fwhm = 2.355 * sigma   # full-width half-maximum
        return math.pi * (fwhm / 2.0) ** 2

    def _empty_sky(
        self, additive_drift: float, gain_drift: float
    ) -> npt.NDArray[np.float64]:
        """Sky-only frame (no target, no stars) — used as freeze seed before first valid frame."""
        cfg = self.cfg
        base = float(cfg.sky_base_counts) + self._sky_gradient + additive_drift
        base *= gain_drift
        noise = self._rng.normal(0.0, cfg.read_noise_sigma, size=(cfg.height, cfg.width))
        return base + noise

    def _render_frame(
        self,
        *,
        target_x: float,
        target_y: float,
        additive_drift: float,
        gain_drift: float,
        dx_ego: float,
        dy_ego: float,
    ) -> npt.NDArray[np.float64]:
        """Render one complete synthetic frame as float64."""
        cfg = self.cfg
        H, W = cfg.height, cfg.width

        # Cold sky background + gradient + read noise
        base = float(cfg.sky_base_counts) + self._sky_gradient + additive_drift
        base = base * gain_drift
        noise = self._rng.normal(0.0, cfg.read_noise_sigma, size=(H, W))
        frame = base + noise

        # Pixel coordinate grids
        yy_idx = np.arange(H, dtype=np.float64)[:, np.newaxis]
        xx_idx = np.arange(W, dtype=np.float64)[np.newaxis, :]

        # HOT TARGET — 2-D Gaussian PSF
        frame += _gaussian2d(xx_idx, yy_idx, target_x, target_y, cfg.target_sigma_px,
                             cfg.target_peak_above_bg)

        # STARS — static point sources (sub-pixel Gaussian, thinner PSF)
        star_peak = cfg.target_peak_above_bg * cfg.star_peak_fraction
        star_sigma = max(0.8, cfg.target_sigma_px * 0.8)  # stars slightly narrower
        for sx, sy in self._star_positions:
            # Apply ego drift to stars (rigid whole-image shift)
            sx_shifted = sx + dx_ego
            sy_shifted = sy + dy_ego
            frame += _gaussian2d(xx_idx, yy_idx, sx_shifted, sy_shifted, star_sigma,
                                 star_peak)

        return frame


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _gaussian2d(
    xx: npt.NDArray[np.float64],
    yy: npt.NDArray[np.float64],
    cx: float,
    cy: float,
    sigma: float,
    peak: float,
) -> npt.NDArray[np.float64]:
    """Evaluate a 2-D circularly-symmetric Gaussian on a pixel grid."""
    dx = xx - cx
    dy = yy - cy
    r2 = dx * dx + dy * dy
    return peak * np.exp(-r2 / (2.0 * sigma * sigma))


def _float64_to_u16(frame_f64: npt.NDArray[np.float64]) -> npt.NDArray[np.uint16]:
    """Clip to 14-bit range and cast to uint16."""
    clipped = np.clip(frame_f64, 0.0, 16383.0)
    return clipped.astype(np.uint16)
