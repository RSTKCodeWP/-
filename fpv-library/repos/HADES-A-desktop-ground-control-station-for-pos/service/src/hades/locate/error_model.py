"""Sensor-error config — the shared schema (Task 4.1, research gate §3).

`SensorErrorModel` is the SINGLE SOURCE OF TRUTH for sensor error. It is consumed by BOTH:

- the geometric simulator (`geom_sim`, Task 4.2) — to *inject* noise into ground-truth
  poses, and
- the Monte Carlo uncertainty propagation (`uncertainty`, Task 4.4) — to *assume* the
  sigmas it propagates.

This is the anti-circularity discipline made structural (§4, Risk B): the two sides share
this **schema** (field names, units, conventions) but each receives its **own instance** —
they never share realized draws, and at least one coverage-validation mismatch (the
time-sync offset, §5) injects an error mode the MC schema cannot represent at all. That is
what keeps the coverage metric non-tautological.

**Which side reads which field (auditability, §3):**

- *Both* read every sigma — the sim to draw, the MC to propagate.
- The sim ALSO turns `t_sync_offset_ms` × the path velocity into a pose perturbation and
  draws `crab_angle_deg`/`gps_studentt_dof` per its `gps_dist`; the MC's matched instance
  carries `t_sync_offset_ms = 0` and `gps_dist = "gauss"` so a mismatch is detectable.

**The headline split (mandatory, §2):** heading sigma is THREE fields, never one —
`yaw_jitter_sigma_deg` (zero-mean, AVERAGES DOWN under fusion), `heading_bias_sigma_deg`
(systematic crab/COG offset, does NOT average down — it drives the bias floor), and
`crab_angle_deg` (the nominal mean crab). roll/pitch/yaw are likewise separate: yaw is an
order of magnitude looser (the system is heading-limited, no usable magnetometer). Defaults
are SOTA-grounded (M10-class GPS, no magnetometer, fixed O4 mount).

Conversion of fields into distributions/perturbations lives at each CONSUMER; this schema
is pure declarative params.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

_GPS_DISTS = frozenset({"gauss", "studentt"})


@dataclass(frozen=True)
class SensorErrorModel:
    """Declarative sensor-error parameters, shared (schema, not values) by sim and MC."""

    # --- GPS position (drone), per-axis, METERS ---
    gps_horiz_sigma_m: float = 2.5  # 1-sigma horizontal; M10 SBAS-class. Per E, N indep.
    gps_vert_sigma_m: float = 5.0  # 1-sigma vertical; GPS vertical ~1.5-2x horizontal.
    gps_dist: str = "gauss"  # "gauss" | "studentt" (the heavy-tail mismatch knob, §5)
    gps_studentt_dof: float = 4.0  # used only when gps_dist == "studentt"

    # --- Attitude, DEGREES — roll/pitch/yaw SEPARATE (they are NOT equal: the headline) ---
    roll_sigma_deg: float = 1.5  # FC AHRS w/ accel leveling: good.
    pitch_sigma_deg: float = 1.5  # same; the O4 mount-angle error folds in here.
    yaw_jitter_sigma_deg: float = 20.0  # zero-mean heading jitter; AVERAGES DOWN. (15-30)

    # --- Heading SYSTEMATIC error (does NOT average down; drives the bias floor §2) ---
    heading_bias_sigma_deg: float = 12.0  # 1-sigma of the crab/COG-vs-heading offset.
    crab_angle_deg: float = 8.0  # nominal mean wind-crab offset (5-40). A BIAS, per pass.
    crab_sign_random: bool = True  # crab sign varies with wind/leg; sampled per run.

    # --- Boresight (camera<->body mount alignment), DEGREES ---
    boresight_sigma_deg: float = 0.1  # cheap/calibratable; small on purpose.

    # --- Time sync (video frame <-> pose), MILLISECONDS ---
    t_sync_offset_ms: float = 0.0  # CONSTANT lag pose-behind-video. THE named MC-blind term.
    t_sync_jitter_ms: float = 15.0  # zero-mean per-frame jitter in the pairing.

    # --- Ground-plane elevation uncertainty, METERS ---
    sigma_h_m: float = 3.0  # operator flat-earth elevation error -> down-range error.

    # --- Pixel / detector foot, PIXELS ---
    pixel_sigma_px: float = 3.0  # box bottom-center jitter (detector localization noise).
    foot_bias_px: float = 0.0  # systematic feet-vs-box-bottom offset (prone-bias knob).

    def __post_init__(self) -> None:
        # A negative sigma is a config error, not a silent NaN/imaginary-draw source. The
        # bias *offset* fields (crab_angle_deg, foot_bias_px, t_sync_offset_ms) may be any
        # sign; only the dispersion (sigma/jitter/dof) fields must be non-negative.
        nonneg = (
            "gps_horiz_sigma_m",
            "gps_vert_sigma_m",
            "gps_studentt_dof",
            "roll_sigma_deg",
            "pitch_sigma_deg",
            "yaw_jitter_sigma_deg",
            "heading_bias_sigma_deg",
            "boresight_sigma_deg",
            "t_sync_jitter_ms",
            "sigma_h_m",
            "pixel_sigma_px",
        )
        for name in nonneg:
            if getattr(self, name) < 0.0:
                raise ValueError(
                    f"SensorErrorModel.{name} must be non-negative, got {getattr(self, name)}"
                )
        if self.gps_dist not in _GPS_DISTS:
            raise ValueError(
                f"SensorErrorModel.gps_dist must be one of {sorted(_GPS_DISTS)}, "
                f"got {self.gps_dist!r}"
            )
        # Student-t needs dof > 2 for a finite variance (the sigma scale is meaningless
        # otherwise). Only enforced on the heavy-tail path so the Gaussian default is free.
        if self.gps_dist == "studentt" and self.gps_studentt_dof <= 2.0:
            raise ValueError(
                f"gps_studentt_dof must be > 2 for finite variance, got {self.gps_studentt_dof}"
            )


def field_names() -> frozenset[str]:
    """The full field set (for the auditability check + sim/MC schema agreement)."""
    return frozenset(f.name for f in fields(SensorErrorModel))
