"""Tier-2 observability-gated inverse-range (rho = 1/r) observer — DIAGNOSTICS ONLY.

DOCTRINE (read before touching this file)
=========================================
This module implements the *Tier-2* range observer specified in
``docs/STATE_ESTIMATION_OBSERVABILITY_BRIEFING.md`` §3.2 and
``docs/BODY_AND_VV_BRIEFING.md``.  Its single, non-negotiable contract:

    The output of this observer feeds ONLY diagnostics, ``t_go`` shaping,
    the Vc_eff confidence blend, and the commit-gate geometry term.
    IT MUST NEVER TOUCH THE PN NAVIGATION GAIN.

The PN gain stays ``Vc_sched`` from ``SpeedPolicy`` (design §3.3, guidance
briefing C3).  This separation is the *correct surrender* to a theorem we
cannot beat — the Fisher-information-matrix (FIM) rank-deficiency toward range
for a single passive monocular station holding a non-accelerating bearing
(briefing §1.1).  No filter, neural net, or amount of cleverness manufactures
range from a straight-line bearing history; the CRLB on range is infinite there.

The API encodes the doctrine: every estimate carries an ``observability`` index
and a ``valid`` flag.  When the geometry does not currently support range
(no own-maneuver parallax), the observer reports ``valid=False`` and
``range_m=None`` — *the estimator telling the truth about when it cannot see
range.*  Consumers MUST honour ``valid`` and the (wide) ``range_sigma``.

THE PHYSICS — WHY THESE THREE INPUTS, AND WHAT EACH OBSERVES
=============================================================
State: ``rho = 1/r`` (inverse range, metres⁻¹).  Inverse-range is the
quantity that stays bounded and near-Gaussian as ``r → ∞`` and whose Fisher
information is exactly what own-maneuver delivers (briefing §3.2).  Filtering
``1/r`` avoids the divergence a direct-range filter suffers when observability
lapses.

(a) LOOMING / τ  — the area-growth relation.
    A blob of a fixed-size target subtends an angular size ∝ 1/r, so its pixel
    AREA A ∝ (1/r)² = rho².  Differentiating:

        A_dot / A = 2 · rho_dot / rho            (the area-growth relation)
    ⇒   rho_dot / rho = A_dot / (2·A) = 1 / (2·τ)    since  τ = A / A_dot.

    This measures the *fractional* inverse-range rate (= closing-rate / range,
    i.e. Vc·rho).  It is an OBSERVABLE-SUBSPACE quantity (range-normalised
    closing rate); on its own it does NOT pin absolute rho without a size prior
    or maneuver.  It is the weak, gated closing-SIGN/ORDER cue of ``looming.py``.

(b) OWN LATERAL ACCELERATION ⟂ LOS — the parallax that makes range observable.
    For an inertial (non-maneuvering) target, an observer perpendicular
    acceleration ``a_perp`` curves the line of sight.  To first order the LOS
    rate acquires a term

        lambda_dot_induced  ≈  - a_perp · rho / Vc          (rad/s)

    i.e. the *change* in measured LOS-rate that our OWN maneuver injects is
    proportional to ``rho`` (and inversely to closing speed Vc).  Measuring how
    much our commanded ``a_perp`` bends the LOS gives a direct pseudo-measurement
    of ``rho`` — this is accelerated triangulation / baseline synthesis, the
    only passive range-recovery mechanism (briefing §1.2).  On a clean collision
    triangle ``a_perp → 0`` (PN nulls λ̇), the term vanishes, and range goes
    UNOBSERVABLE exactly as you close — the cruel catch the doctrine respects.

(c) IMM LOS-RATE  — supplies the measured ``lambda_dot`` (and Vc-context) for (b),
    and its innovation covariance bounds how much of an observed LOS-rate change
    we can attribute to our own maneuver vs. noise.

OBSERVABILITY INDEX (published, every frame)
============================================
The index is the instantaneous FIM-toward-range, accumulated over a window:

        Phi = Σ_window ( |a_perp| · dt / sigma_lambda_dot ) · rho_assumed

It is large when our perpendicular acceleration is large relative to the
LOS-rate noise floor (the parallax actually shows up above noise), and ~zero on
a clean collision triangle (a_perp ≈ 0).  When ``Phi < theta_obs`` the observer
COASTS on prior with inflated covariance and reports ``valid=False``.  The
looming channel alone NEVER raises observability — it is fused for the fractional
``rho_dot/rho`` consistency cross-check, not promoted to absolute range.

CPU: a 1-state EKF is single-digit microseconds.  Cheaper than one detection.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Output contract  (the API that encodes the doctrine)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RangeEstimate:
    """Per-frame Tier-2 inverse-range estimate.  DIAGNOSTICS / t_go / commit ONLY.

    This estimate MUST NEVER feed the PN navigation gain.  Consumers must honour
    ``valid`` and the (wide) ``range_sigma``; treating a wide-covariance range as
    if it were tight is the failure mode the architecture forbids (briefing §5.6).

    Attributes
    ----------
    rho:
        Inverse-range estimate ``1/r`` in metres⁻¹.  Always populated (the filter
        state); but only meaningful when ``valid`` is True.
    range_m:
        Convenience ``1/rho`` in metres, or ``None`` when ``valid`` is False
        (range UNOBSERVABLE — the passive-monocular truth without maneuver/prior).
    range_sigma:
        1-sigma uncertainty on range (metres), propagated from the rho covariance.
        ``inf`` when unobservable.  ALWAYS wide on a passive station — honour it.
    rho_sigma:
        1-sigma uncertainty on the inverse-range state (metres⁻¹).
    observability:
        Published FIM-toward-range index (>= 0).  Range is reported only when this
        exceeds the configured threshold.  ~0 on a clean collision triangle.
    valid:
        True ⇔ ``observability`` cleared threshold this frame ⇒ a range may be
        read.  False ⇔ UNOBSERVABLE: coast on prior, ``range_m`` is None.
    closing_normalized:
        ``rho_dot / rho`` = Vc·rho = 1/(2·τ) from the looming channel — the
        observable-subspace fractional closing rate.  Sign/order cross-check only.
    frame_id:
        Frame index.
    """

    rho: float
    range_m: float | None
    range_sigma: float
    rho_sigma: float
    observability: float
    valid: bool
    closing_normalized: float = 0.0
    frame_id: int = 0


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RangeObserverConfig:
    """Configuration for the inverse-range observer.

    Attributes
    ----------
    rho_init:
        Initial inverse-range prior (m⁻¹).  Default 1/500 m — a deliberately
        weak, wide prior (we do not know range; this only seeds the filter).
    rho_init_sigma:
        Initial 1-sigma on rho (m⁻¹).  Wide by design.
    obs_threshold:
        Observability index threshold ``theta_obs``.  Below this, the observer
        reports ``valid=False`` (UNOBSERVABLE).  Dimensionless (accumulated
        |a_perp|·dt / sigma_lambda_dot · rho_assumed).
    obs_window_s:
        Sliding window (seconds) over which the observability index accumulates
        the perpendicular-acceleration parallax information.
    sigma_lambda_dot:
        LOS-rate measurement noise floor (rad/s) used both to scale the
        observability index and as the parallax pseudo-measurement noise.
    q_rho_rate:
        Process noise on rho per second (m⁻¹/√s)² — lets rho drift as we close.
    min_vc_mps:
        Floor on assumed closing speed (m/s) for the parallax model, to avoid a
        divide-by-zero when Vc is unknown/zero.
    min_a_perp_mps2:
        Minimum |a_perp| (m/s²) for a frame to contribute parallax information.
        Below this the maneuver is in the noise and is ignored for ranging.
    """

    rho_init: float = 1.0 / 500.0
    rho_init_sigma: float = 1.0 / 200.0
    obs_threshold: float = 1.0
    obs_window_s: float = 1.5
    sigma_lambda_dot: float = 0.005
    q_rho_rate: float = (1.0 / 2000.0) ** 2
    min_vc_mps: float = 1.0
    min_a_perp_mps2: float = 0.2


# ---------------------------------------------------------------------------
# Observer
# ---------------------------------------------------------------------------

class InverseRangeObserver:
    """1-state EKF on inverse-range ``rho = 1/r``, observability-gated.

    Diagnostics-only: the output feeds t_go / commit-gate / Vc_eff blend, NEVER
    the PN gain.  See module docstring.

    Usage
    -----
    ::

        obs = InverseRangeObserver()
        for frame:
            est = obs.update(
                a_perp_mps2 = <own lateral accel perpendicular to LOS, m/s²>,
                lambda_dot_radps = <IMM LOS-rate magnitude, rad/s>,
                vc_mps = <assumed/scheduled closing speed, m/s>,
                tau_s = <looming tau, s>  (optional),
                tau_confidence = <looming confidence in [0,1]> (optional),
                dt = <seconds>,
            )
            if est.valid:
                use_for_diagnostics(est.range_m, est.range_sigma)  # NOT for PN
    """

    def __init__(self, config: RangeObserverConfig | None = None) -> None:
        self._cfg = config or RangeObserverConfig()
        self._rho: float = self._cfg.rho_init
        self._P: float = self._cfg.rho_init_sigma ** 2
        # Sliding window of (info_increment, dt) for the observability index.
        self._info_hist: deque[tuple[float, float]] = deque()
        self._window_time: float = 0.0
        self._frame_id: int = 0

    def reset(self) -> None:
        """Reset state (e.g., after track loss)."""
        self._rho = self._cfg.rho_init
        self._P = self._cfg.rho_init_sigma ** 2
        self._info_hist.clear()
        self._window_time = 0.0
        self._frame_id = 0

    def update(
        self,
        *,
        a_perp_mps2: float,
        lambda_dot_radps: float,
        vc_mps: float,
        dt: float,
        tau_s: float | None = None,
        tau_confidence: float = 0.0,
    ) -> RangeEstimate:
        """Process one frame and return a gated inverse-range estimate.

        Parameters
        ----------
        a_perp_mps2:
            Own lateral acceleration PROJECTED PERPENDICULAR TO THE LOS (m/s²).
            This is the maneuver that makes range observable; on a clean
            collision triangle it is ~0 and range stays UNOBSERVABLE.
        lambda_dot_radps:
            Magnitude of the IMM-filtered LOS-rate this frame (rad/s).  Used as
            the parallax pseudo-measurement: how much our a_perp bent the LOS.
        vc_mps:
            Assumed/scheduled closing speed (m/s) — from SpeedPolicy.  Context
            for the parallax model only; NOT an observed quantity.
        dt:
            Elapsed time since previous frame (s).
        tau_s, tau_confidence:
            Optional looming output.  Supplies the fractional ``rho_dot/rho``
            consistency cross-check.  Looming NEVER raises observability or pins
            absolute range on its own (no size prior).
        """
        cfg = self._cfg
        dt = max(dt, 1e-6)
        self._frame_id += 1

        # ── EKF predict: rho drifts (process noise), mean roughly constant over dt
        #    plus the deterministic closing drift rho_dot = rho²·Vc when known.
        vc = max(abs(vc_mps), cfg.min_vc_mps)
        rho_dot_closing = self._rho * self._rho * vc      # d(1/r)/dt = Vc/r² = rho²·Vc
        self._rho = self._rho + rho_dot_closing * dt
        self._rho = max(self._rho, 1e-9)
        self._P = self._P + cfg.q_rho_rate * dt

        # ── Observability index: instantaneous FIM-toward-range, windowed ──────
        #    info ∝ (|a_perp|·dt / sigma_lambda_dot) · rho_assumed
        a_perp = abs(a_perp_mps2)
        if a_perp >= cfg.min_a_perp_mps2:
            info_inc = (a_perp * dt / max(cfg.sigma_lambda_dot, 1e-9)) * self._rho
        else:
            info_inc = 0.0
        self._info_hist.append((info_inc, dt))
        self._window_time += dt
        while self._window_time > cfg.obs_window_s and len(self._info_hist) > 1:
            old_inc, old_dt = self._info_hist.popleft()
            self._window_time -= old_dt
        observability = sum(inc for inc, _ in self._info_hist)

        # ── Looming cross-check: rho_dot/rho = 1/(2τ) (the area-growth relation)
        closing_normalized = 0.0
        if tau_s is not None and tau_confidence > 0.0 and math.isfinite(tau_s) and tau_s > 1e-6:
            closing_normalized = 1.0 / (2.0 * tau_s)

        # ── EKF measurement update — PARALLAX (the only absolute-range info) ────
        #    Model: lambda_dot_induced = -a_perp · rho / Vc.  Measurement is the
        #    LOS-rate magnitude attributable to our own maneuver.  We only apply
        #    it when a_perp is above the maneuver floor (otherwise H≈0, no info).
        if a_perp >= cfg.min_a_perp_mps2:
            # h(rho) = a_perp · rho / Vc  (predicted induced LOS-rate magnitude)
            H = a_perp / vc                      # ∂h/∂rho
            z = abs(lambda_dot_radps)            # measured induced LOS-rate (mag)
            h = H * self._rho
            R = cfg.sigma_lambda_dot ** 2
            S = H * self._P * H + R
            K = self._P * H / S if S > 0.0 else 0.0
            self._rho = self._rho + K * (z - h)
            self._rho = max(self._rho, 1e-9)
            self._P = (1.0 - K * H) * self._P

        rho_sigma = math.sqrt(max(self._P, 0.0))

        # ── Gate on the published observability index ──────────────────────────
        valid = observability >= cfg.obs_threshold
        if valid and self._rho > 1e-9:
            range_m: float | None = 1.0 / self._rho
            # σ_range = σ_rho / rho²  (delta method on r = 1/rho)
            range_sigma = rho_sigma / (self._rho * self._rho)
        else:
            range_m = None
            range_sigma = float("inf")

        return RangeEstimate(
            rho=float(self._rho),
            range_m=(float(range_m) if range_m is not None else None),
            range_sigma=float(range_sigma),
            rho_sigma=float(rho_sigma),
            observability=float(observability),
            valid=bool(valid),
            closing_normalized=float(closing_normalized),
            frame_id=self._frame_id,
        )
