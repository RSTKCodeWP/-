"""Subtense ranging — passive ABSOLUTE range from a resolved target of KNOWN class size.

WHY THIS EXISTS (read before touching)
======================================
The passive-monocular range wall is real: from a straight-line bearing history a single station
cannot observe range (the FIM is rank-deficient toward range — see ``range_observer.py``). The old
Tier-2 observer respected that wall by gating on OWN-MANEUVER parallax ``a_perp`` — but a proportional-
navigation interceptor NULLS the LOS rate, so ``a_perp → 0`` and range goes UNOBSERVABLE *exactly as
you close*. That is the cruel catch, and it left the range channel dead in production.

This module beats the wall from the OTHER side — not with geometry, with IDENTITY. The mature-doctrine
target is a **winged UAV of KNOWN class size** (span ~3-5 m), and at engagement range its silhouette is
**RESOLVED** (~11-24 px). Once the classifier has confirmed the class (and the operator has confirmed it
on the monitor, pre-launch — the enrollment step), the target's physical extent ``S`` is KNOWN. Then the
projected pixel extent ``w`` is a DIRECT measurement of range:

        w_px  =  f_px · S / R                    (pinhole subtense of a known-size object)

Invert for range, or better for inverse range ``rho = 1/R``:

        R    =  f_px · S / w                      (absolute range — no maneuver required)
        rho  =  1/R  =  w / (f_px · S)            (LINEAR in w, slope  H = f_px·S  is KNOWN)

This is the honest breakthrough: subtense gives a **linear, per-frame, absolute** measurement of ``rho``
with a known measurement matrix, available whenever the target is resolved — no own-maneuver, no parallax,
so it works through the terminal collision triangle where the parallax channel dies.

THE ONE HONEST CATCH — the SIZE-SCALE AMBIGUITY (do not paper over it)
=====================================================================
``w = f_px · S · rho`` is ONE equation in TWO unknowns (``S`` and ``rho``). Passively we cannot separate
them: a target twice as big at twice the range gives the same pixels. So subtense delivers range only up
to the fractional error in the assumed size ``S``. This splits the uncertainty into two physically
distinct parts that MUST be reported separately, because they behave oppositely:

  * RANDOM (extent-measurement noise ``σ_w``): the centroid/edge/extent jitter. It is white and
    **averages down** over frames — the recursive filter shrinks it. In metres it is
        σ_R,random = R · (σ_w / w)          → ∝ R²   (grows fast with range; small in the terminal)
  * SYSTEMATIC (size-prior error ``σ_S`` and focal calibration ``σ_f``): the assumed size is fixed for the
    whole engagement, so this error is a **constant fractional bias** that does NOT average away, no
    matter how many frames you integrate.
        σ_R,systematic = R · sqrt( (σ_S/S)² + (σ_f/f)² )    → ∝ R

Reporting a single shrinking σ (folding σ_S into a white R) would be a LIE — the filter would report
false precision it can never earn passively. So ``SubtenseRangeEstimate`` carries
``sigma_range_random_m`` and ``sigma_range_systematic_m`` separately, and only the random part is driven
down by the filter. This is the same intellectual-honesty contract the rest of the seeker holds itself to.

BREAKING THE AMBIGUITY — ToF self-calibration (Ось V)
=====================================================
A single trusted hard range fix (terminal ToF laser rangefinder) breaks the degeneracy: with a measured
``R_tof`` and the observed extent ``w`` we back out the TRUE effective projected size
        S_eff = w · R_tof / f_px
and tighten the size prior to the ToF-derived uncertainty. After ONE ToF return the passive channel is
self-calibrated — the systematic term collapses — and stays calibrated for the rest of the (seconds-long)
flight. So ToF is not on the critical path: absent it we run on the class-size prior; present it, it both
sharpens range AND teaches the passive channel the real size. Graceful degradation, both directions.

ADDING CLOSING VELOCITY — R(t) OBSERVED ⇒ Vc OBSERVED (the true-PN enabler)
===========================================================================
Because the extent gives ``R = f_px·S/w`` EVERY frame, the range *time-series* is observable, so its
derivative ``Vc = -dR/dt`` is observable too — by estimation, not assumption. :class:`SubtenseRangeRateFilter`
is a 2-state EKF on ``[R, Vc]`` (constant-closing dynamics ``R_dot = -Vc``, ``Vc_dot = white-accel``) fed by
the same subtense extent. It hands guidance a MEASURED ``Vc`` (replacing the scheduled Vc — the project's
deepest honesty gap) and a real ``t_go = R/Vc``. Both ``R`` and ``Vc`` inherit the systematic size fraction
(a size scale error scales range AND its rate identically), reported separately as before.

ANTI-FABRICATION (answering the audit) — and the honest line between coast and fabrication
==========================================================================================
The audit's sin in the old observer was a deterministic ``rho += rho²·Vc·dt`` predict that manufactured a
shrinking range from the *scheduled* (assumed, never-measured) Vc even with no measurement. The distinction
this module holds:
  * :class:`SubtenseRangeFilter` (1-state) uses a pure random walk — the mean NEVER moves on predict; a coast
    freezes the range and only GROWS covariance. Zero Vc-driven drift.
  * :class:`SubtenseRangeRateFilter` (2-state) DOES dead-reckon ``R`` forward on a coast — but with its OWN
    MEASURED ``Vc`` state, and with the covariance honestly inflating (Q). Propagating a *measured* state with
    growing uncertainty is legitimate dead-reckoning; injecting an *assumed* value as if known is fabrication.
    Before any extent is ever seen the filter sits at its wide prior (``Vc≈0``) and does NOT invent closing.

UNITS / SIGN
============
    extent_px, w      : pixels (the resolved silhouette's physical extent, e.g. wingspan-major-axis)
    target_size_m, S  : metres (the physical size the pixel extent corresponds to)
    f_px              : pixels (focal length; see geometry.CameraIntrinsics)
    R, range_m        : metres, > 0
    rho               : metres⁻¹, > 0
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .geometry import CameraIntrinsics


# ---------------------------------------------------------------------------
# Stateless algebraic core (the math, fully testable in isolation)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SubtenseSample:
    """One algebraic (memoryless) subtense range solution with honest error split.

    Attributes
    ----------
    range_m:
        Absolute range ``R = f_px·S/w`` (metres).
    rho:
        Inverse range ``1/R = w/(f_px·S)`` (metres⁻¹) — the LINEAR-in-``w`` state.
    sigma_range_random_m:
        1σ range error from the extent-measurement noise ``σ_w`` (metres).  White; averages down.
    sigma_range_systematic_m:
        1σ range error from the size-prior ``σ_S`` and focal ``σ_f`` (metres).  Fixed fractional bias;
        does NOT average down passively.
    sigma_range_total_m:
        Quadrature sum of the random and systematic parts (metres).
    sigma_rho_random, sigma_rho_systematic:
        The same two parts expressed on ``rho`` (metres⁻¹) — what a ``rho``-parameterised filter consumes.
    resolved:
        True iff the extent cleared the resolved-silhouette gate (enough pixels for the extent to mean
        anything).  A few-pixel blob is in the acquisition regime where the extent is noise.
    """

    range_m: float
    rho: float
    sigma_range_random_m: float
    sigma_range_systematic_m: float
    sigma_range_total_m: float
    sigma_rho_random: float
    sigma_rho_systematic: float
    resolved: bool


def range_from_subtense(
    extent_px: float,
    target_size_m: float,
    f_px: float,
    *,
    extent_sigma_px: float = 1.0,
    size_sigma_m: float = 0.0,
    f_sigma_px: float = 0.0,
    min_resolved_px: float = 6.0,
) -> SubtenseSample:
    """Solve absolute range from a resolved subtense, with the honest random/systematic split.

    ``R = f_px · S / w``.  First-order (delta-method) error propagation, keeping the size/focal
    (systematic, per-engagement) terms SEPARATE from the extent-noise (random, averaging) term:

        (σ_R,random / R)      = σ_w / w
        (σ_R,systematic / R)  = sqrt( (σ_S/S)² + (σ_f/f)² )

    The relative errors on ``R`` and ``rho`` are identical (``rho = 1/R``), so the same fractions scale
    ``rho``.  Raises ``ValueError`` on non-physical inputs so a bad extent can never silently fabricate a
    range.
    """
    if not (extent_px > 0.0 and target_size_m > 0.0 and f_px > 0.0):
        raise ValueError(
            f"subtense inputs must be positive: extent_px={extent_px}, "
            f"target_size_m={target_size_m}, f_px={f_px}")

    rho = extent_px / (f_px * target_size_m)          # LINEAR: w = (f·S)·rho
    range_m = 1.0 / rho

    frac_random = extent_sigma_px / extent_px
    frac_systematic = math.hypot(
        size_sigma_m / target_size_m,
        f_sigma_px / f_px,
    )

    return SubtenseSample(
        range_m=range_m,
        rho=rho,
        sigma_range_random_m=range_m * frac_random,
        sigma_range_systematic_m=range_m * frac_systematic,
        sigma_range_total_m=range_m * math.hypot(frac_random, frac_systematic),
        sigma_rho_random=rho * frac_random,
        sigma_rho_systematic=rho * frac_systematic,
        resolved=extent_px >= min_resolved_px,
    )


# ---------------------------------------------------------------------------
# Extent helpers — turn a detected blob into a physical-extent measurement
# ---------------------------------------------------------------------------

def bbox_major_extent_px(bbox: tuple[float, float, float, float]) -> float:
    """Major-axis pixel extent from a ``(left, top, width, height)`` bbox (max side).

    For a winged UAV seen near-broadside/head-on the major axis maps to the KNOWN wingspan — the most
    stable known-size feature.  The caller pairs this with ``target_size_m = wingspan_m``.
    """
    _, _, w, h = bbox
    return float(max(w, h))


def equiv_diameter_px(area_px: float) -> float:
    """Equivalent-disc diameter ``2·sqrt(A/π)`` from a blob area (rotation-invariant extent).

    Pair with ``target_size_m`` = the diameter of the equal-area disc of the target silhouette.  More
    robust than a bbox at low resolution; less tied to a nameable physical dimension than the span.
    """
    return 2.0 * math.sqrt(max(area_px, 0.0) / math.pi)


# ---------------------------------------------------------------------------
# Recursive filter — measurement-driven inverse-range, NO Vc fabrication
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SubtenseRangeConfig:
    """Configuration for :class:`SubtenseRangeFilter`.

    Attributes
    ----------
    rho_init:
        Initial inverse-range prior (m⁻¹).  Weak/wide by design (default 1/300 m).
    rho_init_sigma:
        Initial 1σ on ``rho`` (m⁻¹).  Wide by design.
    q_rho_walk_rate:
        Random-walk process-noise density on ``rho`` ((m⁻¹)²/s).  The mean is NEVER pushed by Vc; this
        just lets the estimate track a genuinely changing range and inflates covariance on a coast.
    min_resolved_px:
        Extent below which a frame is treated as UNRESOLVED — no measurement update (coast, covariance
        grows).  Keeps acquisition-regime pixel noise out of the range state.
    """

    rho_init: float = 1.0 / 300.0
    rho_init_sigma: float = 1.0 / 150.0
    q_rho_walk_rate: float = (1.0 / 4000.0) ** 2
    min_resolved_px: float = 6.0


@dataclass(frozen=True)
class SubtenseRangeEstimate:
    """Per-frame output of :class:`SubtenseRangeFilter`.

    ``sigma_random_m`` shrinks as the filter integrates extent measurements; ``sigma_systematic_m`` is
    the irreducible size/focal fractional error (until a ToF fix recalibrates the size).  Consumers that
    need a single number use ``sigma_total_m``; a ``rho``-parameterised tracker consumes ``rho`` /
    ``sigma_rho_random`` directly (its measurement is linear).
    """

    range_m: float
    rho: float
    sigma_random_m: float
    sigma_systematic_m: float
    sigma_total_m: float
    sigma_rho_random: float
    resolved: bool
    measurement_applied: bool
    frame_id: int


class SubtenseRangeFilter:
    """1-state Kalman filter on inverse range ``rho = 1/R`` driven by subtense extent measurements.

    The measurement is LINEAR — ``z = w = (f_px·S)·rho`` — so this is an exact linear KF for the passive
    channel (no EKF linearisation error).  The size/focal uncertainty is carried OUTSIDE the filter state
    as a systematic fractional term (it cannot be averaged down passively) and combined only at reporting.
    A hard range fix (ToF) both updates the state and RECALIBRATES the size prior.

    Process model: pure random walk (mean unchanged on predict).  There is deliberately NO Vc-driven mean
    drift — see the module's ANTI-FABRICATION note.
    """

    def __init__(
        self,
        target_size_m: float,
        intrinsics: CameraIntrinsics,
        *,
        size_sigma_m: float = 0.0,
        f_sigma_px: float = 0.0,
        config: SubtenseRangeConfig | None = None,
    ) -> None:
        if target_size_m <= 0.0:
            raise ValueError(f"target_size_m must be positive, got {target_size_m}")
        self._cfg = config or SubtenseRangeConfig()
        self._S = float(target_size_m)
        self._size_sigma = float(size_sigma_m)
        self._f = float(intrinsics.f_px)
        self._f_sigma = float(f_sigma_px)
        self._rho = float(self._cfg.rho_init)
        self._P = float(self._cfg.rho_init_sigma) ** 2   # RANDOM covariance only
        self._frame_id = 0

    # -- read-only introspection -------------------------------------------------
    @property
    def target_size_m(self) -> float:
        return self._S

    @property
    def size_sigma_m(self) -> float:
        return self._size_sigma

    def _systematic_frac(self) -> float:
        """Irreducible fractional error from size prior + focal calibration."""
        return math.hypot(self._size_sigma / self._S, self._f_sigma / self._f)

    def _emit(self, *, measurement_applied: bool, resolved: bool) -> SubtenseRangeEstimate:
        rho = max(self._rho, 1e-12)
        range_m = 1.0 / rho
        sigma_rho_random = math.sqrt(max(self._P, 0.0))
        sigma_random_m = sigma_rho_random / (rho * rho)       # delta method: σ_R = σ_rho/rho²
        sigma_systematic_m = range_m * self._systematic_frac()
        return SubtenseRangeEstimate(
            range_m=range_m,
            rho=rho,
            sigma_random_m=sigma_random_m,
            sigma_systematic_m=sigma_systematic_m,
            sigma_total_m=math.hypot(sigma_random_m, sigma_systematic_m),
            sigma_rho_random=sigma_rho_random,
            resolved=resolved,
            measurement_applied=measurement_applied,
            frame_id=self._frame_id,
        )

    def update(
        self,
        extent_px: float | None,
        dt: float,
        *,
        extent_sigma_px: float = 1.0,
    ) -> SubtenseRangeEstimate:
        """Predict (random-walk) then, if the target is resolved, apply the linear extent measurement.

        ``extent_px=None`` or below the resolved gate ⇒ COAST: mean frozen, covariance grows.  Never
        fabricates a range from motion — a coast makes the estimate LESS certain, not falsely closer.
        """
        cfg = self._cfg
        dt = max(dt, 1e-6)
        self._frame_id += 1

        # ── Predict: random walk (mean unchanged), covariance grows ──────────────
        self._P += cfg.q_rho_walk_rate * dt

        # ── Coast when unresolved ────────────────────────────────────────────────
        resolved = extent_px is not None and extent_px >= cfg.min_resolved_px
        if not resolved:
            return self._emit(measurement_applied=False, resolved=False)

        # ── Linear measurement update:  z = w,  h(rho) = (f·S)·rho ───────────────
        H = self._f * self._S                     # KNOWN, constant slope (no EKF error)
        z = float(extent_px)
        R_meas = float(extent_sigma_px) ** 2
        S_inn = H * self._P * H + R_meas
        K = (self._P * H / S_inn) if S_inn > 0.0 else 0.0
        self._rho = self._rho + K * (z - H * self._rho)
        self._rho = max(self._rho, 1e-12)
        self._P = (1.0 - K * H) * self._P
        return self._emit(measurement_applied=True, resolved=True)

    def fix_with_hard_range(
        self,
        range_m: float,
        sigma_m: float,
        extent_px: float,
    ) -> SubtenseRangeEstimate:
        """Fuse a trusted hard range (ToF) AND self-calibrate the size prior.

        Two effects:
          1. Hard ``rho`` update — ``z_rho = 1/R_tof`` with ``σ_rho = σ_tof/R_tof²`` — tightens the random
             covariance (a direct, high-information range measurement).
          2. Size self-calibration — back out the true projected size ``S_eff = w·R_tof/f`` and replace the
             (class-prior) size with it, collapsing the SYSTEMATIC term to the ToF-derived size error.

        After one good ToF return the passive channel is self-calibrated for the rest of the flight.
        """
        if not (range_m > 0.0 and extent_px > 0.0):
            raise ValueError(f"hard fix needs positive range and extent, got R={range_m}, w={extent_px}")
        self._frame_id += 1

        # (1) hard rho update (linear in rho, H=1).  CRUCIAL: the prior variance for THIS fusion is the
        #     TOTAL uncertainty (random P + the systematic size term), not P alone.  The passive rho is
        #     biased by the size-prior error, and that bias lives OUTSIDE P — so a naive P-only gain would
        #     let the filter cling to its biased estimate and ignore an authoritative ToF return.  Folding
        #     the systematic term in gives the ToF its rightful weight against the size bias.
        sys_sigma_rho = self._rho * self._systematic_frac()
        P_total = self._P + sys_sigma_rho * sys_sigma_rho
        z_rho = 1.0 / range_m
        sigma_rho = max(sigma_m, 0.0) / (range_m * range_m)   # delta method
        R_meas = sigma_rho * sigma_rho
        S_inn = P_total + R_meas
        K = (P_total / S_inn) if S_inn > 0.0 else 0.0
        self._rho = self._rho + K * (z_rho - self._rho)
        self._rho = max(self._rho, 1e-12)
        self._P = (1.0 - K) * P_total

        # (2) size self-calibration:  S_eff = w · R_tof / f
        s_eff = extent_px * range_m / self._f
        # σ_S_eff from the extent noise and the ToF range noise (relative errors add in quadrature).
        frac = math.hypot(1.0 / max(extent_px, 1e-9), sigma_m / range_m)   # ~1px extent floor
        self._S = s_eff
        self._size_sigma = s_eff * frac
        return self._emit(measurement_applied=True, resolved=True)


# ===========================================================================
# 2-state range+closing EKF  —  x = [R, Vc],  R_dot = -Vc,  measurement w = f·S/R
# ===========================================================================

@dataclass(frozen=True)
class RangeRateConfig:
    """Configuration for :class:`SubtenseRangeRateFilter`.

    Attributes
    ----------
    range_init_m, range_init_sigma_m:
        Prior on range before the first resolved extent (metres).  On the first resolved frame R is
        RE-INITIALISED directly from the extent (``R0 = f·S/w``) so the EKF never linearises far from truth.
    closing_init_mps, closing_init_sigma_mps:
        Prior on closing velocity ``Vc`` (m/s).  Default 0 ± wide — we do NOT assume closing; the extent
        time-series must reveal it.  This wide, zero-mean prior is why the filter cannot fabricate closing.
    sigma_accel_mps2:
        White-closing-acceleration process-noise density (m/s²).  Sizes the RIGOROUS dt-discretised Q
        ``σ_a²·[[dt³/3, -dt²/2], [-dt²/2, dt]]`` (continuous white-noise-acceleration; the proper
        discretisation the audit flagged as missing in imm.py).
    min_resolved_px:
        Extent below which a frame is UNRESOLVED — predict/coast only (dead-reckon on measured Vc, Q grows).
    min_range_m:
        Floor on the range state (m), guards the EKF measurement Jacobian ``-w/R`` near impact.
    """

    range_init_m: float = 250.0
    range_init_sigma_m: float = 150.0
    closing_init_mps: float = 0.0
    closing_init_sigma_mps: float = 120.0
    sigma_accel_mps2: float = 20.0
    min_resolved_px: float = 6.0
    min_range_m: float = 0.5


@dataclass(frozen=True)
class RangeRateEstimate:
    """Per-frame output of :class:`SubtenseRangeRateFilter`.

    Range AND closing velocity, each with the honest random/systematic split, plus a real time-to-go.
    A ``rho``-parameterised guidance law consumes ``closing_mps`` as the MEASURED PN scale (no more
    scheduled Vc) and ``t_go_s`` for terminal gating.
    """

    range_m: float
    closing_mps: float                 # Vc = -dR/dt; positive = closing
    t_go_s: float                      # R/Vc if closing, else inf (honest: opening/uncertain -> inf)
    sigma_range_random_m: float
    sigma_range_systematic_m: float
    sigma_range_total_m: float
    sigma_closing_random_mps: float
    sigma_closing_systematic_mps: float
    sigma_closing_total_mps: float
    rho: float
    resolved: bool
    measurement_applied: bool
    initialized: bool
    frame_id: int


class SubtenseRangeRateFilter:
    """2-state EKF on ``[R, Vc]`` driven by the subtense extent — makes range AND closing observable.

    Dynamics (constant-closing, the honest near-terminal model):
        R_{k+1}  = R_k - Vc_k·dt
        Vc_{k+1} = Vc_k + white-accel
    Measurement (EKF; the only nonlinearity, smooth and well-conditioned for R>0):
        w = f·S / R,     H = [∂w/∂R, ∂w/∂Vc] = [-f·S/R², 0] = [-w_pred/R, 0]

    The size/focal error is carried OUTSIDE the state as a systematic fractional term (it cannot be
    averaged down passively) and combined only at reporting — identical honesty contract to the 1-state
    filter.  A ToF hard fix updates R (linear) and self-calibrates the size prior.
    """

    def __init__(
        self,
        target_size_m: float,
        intrinsics: CameraIntrinsics,
        *,
        size_sigma_m: float = 0.0,
        f_sigma_px: float = 0.0,
        config: RangeRateConfig | None = None,
    ) -> None:
        if target_size_m <= 0.0:
            raise ValueError(f"target_size_m must be positive, got {target_size_m}")
        self._cfg = config or RangeRateConfig()
        self._S = float(target_size_m)
        self._size_sigma = float(size_sigma_m)
        self._f = float(intrinsics.f_px)
        self._f_sigma = float(f_sigma_px)
        self._x = np.array([self._cfg.range_init_m, self._cfg.closing_init_mps], dtype=np.float64)
        self._P = np.diag([self._cfg.range_init_sigma_m ** 2,
                           self._cfg.closing_init_sigma_mps ** 2]).astype(np.float64)
        self._initialized = False
        self._frame_id = 0

    # -- introspection -----------------------------------------------------------
    @property
    def target_size_m(self) -> float:
        return self._S

    @property
    def size_sigma_m(self) -> float:
        return self._size_sigma

    def _systematic_frac(self) -> float:
        return math.hypot(self._size_sigma / self._S, self._f_sigma / self._f)

    def covariance_random(self) -> np.ndarray:
        """2x2 RANDOM state covariance on ``[R, Vc]`` (m², m²/s², off-diag m²/s).

        The RANDOM (averaging) part only — the systematic size/focal term is reported separately per state.
        Exposed so a range-parameterised tracker / consistency test can use the full joint covariance.
        """
        return self._P.copy()

    def _emit(self, *, measurement_applied: bool, resolved: bool) -> RangeRateEstimate:
        R = max(float(self._x[0]), self._cfg.min_range_m)
        Vc = float(self._x[1])
        sig_R_rand = math.sqrt(max(float(self._P[0, 0]), 0.0))
        sig_Vc_rand = math.sqrt(max(float(self._P[1, 1]), 0.0))
        frac = self._systematic_frac()
        sig_R_sys = R * frac
        sig_Vc_sys = abs(Vc) * frac
        t_go = R / Vc if Vc > 1e-6 else float("inf")
        return RangeRateEstimate(
            range_m=R,
            closing_mps=Vc,
            t_go_s=t_go,
            sigma_range_random_m=sig_R_rand,
            sigma_range_systematic_m=sig_R_sys,
            sigma_range_total_m=math.hypot(sig_R_rand, sig_R_sys),
            sigma_closing_random_mps=sig_Vc_rand,
            sigma_closing_systematic_mps=sig_Vc_sys,
            sigma_closing_total_mps=math.hypot(sig_Vc_rand, sig_Vc_sys),
            rho=1.0 / R,
            resolved=resolved,
            measurement_applied=measurement_applied,
            initialized=self._initialized,
            frame_id=self._frame_id,
        )

    def _predict(self, dt: float) -> None:
        F = np.array([[1.0, -dt], [0.0, 1.0]], dtype=np.float64)
        self._x = F @ self._x
        self._x[0] = max(self._x[0], self._cfg.min_range_m)
        sa2 = self._cfg.sigma_accel_mps2 ** 2
        Q = sa2 * np.array([[dt ** 3 / 3.0, -dt ** 2 / 2.0],
                            [-dt ** 2 / 2.0, dt]], dtype=np.float64)   # discretised WNA
        self._P = F @ self._P @ F.T + Q

    def update(
        self,
        extent_px: float | None,
        dt: float,
        *,
        extent_sigma_px: float = 1.0,
    ) -> RangeRateEstimate:
        """Predict then, if the target is resolved, apply the EKF extent measurement.

        Coast (``extent_px`` None or below the gate): dead-reckon on the MEASURED Vc with Q inflating the
        covariance — legitimate because Vc is a filter state, not an assumed constant.  Before the first
        resolved frame the filter stays at its wide zero-closing prior and invents nothing.
        """
        cfg = self._cfg
        dt = max(dt, 1e-6)
        self._frame_id += 1
        resolved = extent_px is not None and extent_px >= cfg.min_resolved_px

        # First resolved extent -> initialise R directly from it (avoid EKF linearisation far from truth).
        if resolved and not self._initialized:
            w = float(extent_px)
            R0 = self._f * self._S / w
            self._x[0] = R0
            # range variance from the extent noise (delta method on R=f·S/w): σ_R = R·σ_w/w
            self._P[0, 0] = (R0 * extent_sigma_px / w) ** 2
            self._P[0, 1] = self._P[1, 0] = 0.0
            self._initialized = True
            return self._emit(measurement_applied=True, resolved=True)

        self._predict(dt)

        if not resolved:
            return self._emit(measurement_applied=False, resolved=False)

        # EKF measurement update:  w = f·S/R,  H = [-w_pred/R, 0]
        w = float(extent_px)
        R = max(float(self._x[0]), cfg.min_range_m)
        w_pred = self._f * self._S / R
        H = np.array([[-w_pred / R, 0.0]], dtype=np.float64)      # (1,2)
        R_meas = float(extent_sigma_px) ** 2
        S_inn = float((H @ self._P @ H.T)[0, 0]) + R_meas
        K = (self._P @ H.T) / S_inn if S_inn > 0.0 else np.zeros((2, 1))   # (2,1)
        self._x = self._x + (K.flatten() * (w - w_pred))
        self._x[0] = max(self._x[0], cfg.min_range_m)
        self._P = (np.eye(2) - K @ H) @ self._P
        return self._emit(measurement_applied=True, resolved=True)

    def fix_with_hard_range(self, range_m: float, sigma_m: float, extent_px: float) -> RangeRateEstimate:
        """Fuse a trusted hard range (ToF) into R (linear update) AND self-calibrate the size prior.

        Uses the TOTAL prior range variance (random P + systematic size term) so the authoritative ToF
        overrides the size-induced bias rather than being ignored by an over-tight P.  Then recalibrates
        ``S_eff = w·R_tof/f`` — collapsing the systematic term for the rest of the flight.
        """
        if not (range_m > 0.0 and extent_px > 0.0):
            raise ValueError(f"hard fix needs positive range and extent, got R={range_m}, w={extent_px}")
        self._frame_id += 1
        self._initialized = True

        # (1) linear R update with TOTAL prior variance (H = [1, 0]).
        sys_sigma_R = float(self._x[0]) * self._systematic_frac()
        P = self._P.copy()
        P[0, 0] += sys_sigma_R ** 2
        H = np.array([[1.0, 0.0]], dtype=np.float64)
        R_meas = max(sigma_m, 0.0) ** 2
        S_inn = float((H @ P @ H.T)[0, 0]) + R_meas
        K = (P @ H.T) / S_inn if S_inn > 0.0 else np.zeros((2, 1))
        self._x = self._x + (K.flatten() * (range_m - float(self._x[0])))
        self._x[0] = max(self._x[0], self._cfg.min_range_m)
        self._P = (np.eye(2) - K @ H) @ P

        # (2) size self-calibration:  S_eff = w·R_tof/f
        s_eff = extent_px * range_m / self._f
        frac = math.hypot(1.0 / max(extent_px, 1e-9), sigma_m / range_m)
        self._S = s_eff
        self._size_sigma = s_eff * frac
        return self._emit(measurement_applied=True, resolved=True)
