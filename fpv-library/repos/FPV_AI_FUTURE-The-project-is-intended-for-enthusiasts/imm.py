"""Body-frame IMM (Interacting Multiple Model) filter for LOS tracking.

STATE VECTOR
------------
x = [az, el, az_rate, el_rate]  (4-D)
    az, el        — bearing in radians
    az_rate, el_rate — LOS angular rate in rad/s

TWO MODES
---------
Mode 0: CV (Constant Velocity)
    Target moves at constant angular velocity.
    Low process noise — trusts the prediction.
    Appropriate for steady approach geometry.

Mode 1: MANEUVER (Singer model / high process noise)
    Target may jink/manoeuvre.
    High process noise — trusts the measurement.
    Appropriate for evasive targets.

IMM ALGORITHM (standard formulation)
-------------------------------------
At each step:
    1. Mode-mixing: compute mixed initial conditions for each mode filter,
       using the current mode probability weights.
    2. Mode-matched Kalman update: run a separate Kalman prediction+update
       for each mode.
    3. Mode-probability update: update mode probabilities from the likelihood
       of each mode's innovation.
    4. Combined estimate: weighted sum of mode estimates (mean + covariance).

INNOVATION GATING (CRITICAL — read carefully)
----------------------------------------------
The design §3.2 states:
    «инновации гейтятся против гиро-предсказанного движения, чтобы ошибка
     деротации не выглядела как манёвр цели»

Implementation:
    The raw measured LOS-rate (az_rate_meas, el_rate_meas) from los.py has
    already had the ego-rotation subtracted.  However, there can be a residual
    ego error if the cam↔IMU time-sync is imperfect or the soft-mount transfers
    differently.

    We gate the INNOVATION (z - H·x_pred) against a threshold derived from:
        innovation_max = ego_uncertainty_radps   [rad/s]
    where ego_uncertainty_radps is a caller-supplied upper bound on the residual
    ego error (e.g. 0.05 rad/s for a 5 ms sync error at 10 rad/s body rate).

    If |innovation| > ego_gate_radps in EITHER az or el, the update weight
    for Mode 1 (MANEUVER) is NOT amplified by the innovation magnitude alone —
    instead the large innovation is interpreted as a potential ego residual, and
    the maneuver-probability update is DAMPED:
        likelihood_mode1 *= ego_gate_damping   (default 0.3)

    This prevents a time-sync spike from being misclassified as a target jink
    and wrongly raising the maneuver probability.

    HOWEVER: a REAL target maneuver produces a sustained innovation over
    multiple frames while an ego residual spike is transient (one or a few
    frames).  The sustained_maneuver_count tracks consecutive innovations that
    would raise the maneuver mode — only after N_SUSTAIN consecutive frames
    does the gate relaxation apply (i.e. after N_SUSTAIN frames we believe it's
    real maneuver).  This is the key temporal discriminator.

ALPHA-BETA FALLBACK (documented)
----------------------------------
A simple alpha-beta tracker is provided as a fallback when the full IMM is
considered over-engineered for a particular deployment.  It does NOT implement
mode mixing and has no maneuver detection.  Use it as a sanity check or for
resource-constrained situations.

    alpha = position gain (suggestion: 0.5 for smooth tracking)
    beta  = velocity gain  (suggestion: 0.1)

The fallback does NOT gate innovations against ego — use the full IMM for
production ego-rejection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import numpy.typing as npt

from .los import LOSObservation


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IMMEstimate:
    """Per-frame output of the IMM filter.

    Attributes
    ----------
    az_rad, el_rad:
        Filtered bearing estimate (radians).
    az_rate_radps, el_rate_radps:
        Filtered LOS-rate estimate (rad/s).
    mode_probs:
        Tuple (p_cv, p_maneuver) — mode probabilities summing to 1.
    maneuver_detected:
        True when mode_probs[1] (maneuver probability) exceeds 0.5 for at
        least N_SUSTAIN consecutive frames AND the innovation was NOT gated
        as a potential ego residual.
    frame_id:
        Frame index.
    innovation_az, innovation_el:
        Raw innovation (measurement residual) before gating (for diagnostics).
    ego_gate_active:
        True if the ego-residual gate was triggered this frame.
    """

    az_rad: float
    el_rad: float
    az_rate_radps: float
    el_rate_radps: float
    mode_probs: tuple[float, float]
    maneuver_detected: bool
    frame_id: int
    innovation_az: float = 0.0
    innovation_el: float = 0.0
    ego_gate_active: bool = False
    # A4 diagnostics (do NOT alter the filter): conservative NIS-proxy lock quality.
    nis: float = 0.0              # normalized innovation squared (rate channel, R-only scale)
    lock_quality: float = 1.0     # 1=consistent .. 0=model-wrong; 0.5 at the chi2 bound
    model_ok: bool = True         # False = "model-wrong" alarm (NIS above chi2 bound)
    # A4 estimator-hardening outputs:
    nis_true: float = 0.0         # TRUE NIS (rate channels) normalised by innovation covariance S
    model_wrong_alarm: bool = False  # SUSTAINED true-NIS exceedance -> live model-wrong alarm
    gate_sigma_az_rad: float = 0.0   # predicted 1-sigma az innovation (for a covariance-sized box)
    gate_sigma_el_rad: float = 0.0   # predicted 1-sigma el innovation


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IMMConfig:
    """Configuration for the IMM filter.

    Attributes
    ----------
    sigma_meas_az, sigma_meas_el:
        Measurement noise standard deviation for az and el (radians and rad/s).
        For az/el bearing: ~sub-pixel / f_px; for az_rate/el_rate: ~few mrad/s.
    q_cv_rate:
        Process noise on LOS-rate for CV mode (rad/s²).  Low = trusts constant
        velocity assumption.  Suggestion: 0.005 rad/s².
    q_maneuver_rate:
        Process noise on LOS-rate for MANEUVER mode (rad/s²).  High = allows
        large angular accelerations.  Suggestion: 0.5 rad/s².
    transition_prob_stay:
        Markov transition probability of staying in the same mode (0.95 = 5%
        chance of switching per frame).
    ego_gate_radps:
        Innovation magnitude (rad/s) above which a rate innovation is flagged
        as a potential ego residual.  Default 0.05 rad/s.  Represents the
        expected maximum residual ego error from a ~5 ms sync error at ~10 rad/s.
    ego_gate_damping:
        When ego gate is active, the maneuver-mode likelihood is multiplied by
        this factor.  0.3 = aggressively damp false maneuver detection.
    n_sustain_for_maneuver:
        Number of consecutive frames with maneuver-mode probability > 0.5
        before ``maneuver_detected`` is set True.
    init_mode_prob_cv:
        Initial probability for the CV mode.
    """

    # Measurement noise (1-sigma)
    sigma_meas_az: float = 5e-4       # rad (≈1 px at f=2000 px)
    sigma_meas_el: float = 5e-4       # rad
    sigma_meas_az_rate: float = 0.005  # rad/s  (only used by measurement_mode="diagonal_r")
    sigma_meas_el_rate: float = 0.005  # rad/s
    # Measurement model for the az/el RATE channels.
    #   "correlated_r" (default, CORRECT): the rate is a finite difference of the bearing, so its
    #     noise is ~2x the bearing noise scaled by 1/dt AND correlated with the bearing.  R is built
    #     per-frame as a per-axis block [[σ², σ²/dt],[σ²/dt, 2σ²/dt²]] from sigma_meas_az/el + dt.
    #     This removes the finite-diff DOUBLE-COUNT that made NIS≈2 and the posterior over-confident.
    #   "diagonal_r" (legacy): independent diagonal R using sigma_meas_*_rate (bit-identical to the
    #     pre-fix behaviour; kept for A/B comparison against the NEES/NIS consistency harness).
    measurement_mode: str = "correlated_r"

    # Process noise (LOS-rate acceleration)
    q_cv_rate: float = 0.005      # rad/s² — low, steady approach
    q_maneuver_rate: float = 0.5  # rad/s² — high, evasive jink

    # IMM transition matrix (Markov)
    transition_prob_stay: float = 0.95

    # Ego innovation gate
    ego_gate_radps: float = 0.05      # rad/s — flag potential ego residual
    ego_gate_damping: float = 0.3     # damp maneuver likelihood when gated
    n_sustain_for_maneuver: int = 3   # consecutive frames before maneuver_detected

    # Initial conditions
    init_mode_prob_cv: float = 0.9

    # A4: NIS-proxy "model-wrong" alarm bound (chi-square, 2 DOF: 5.99=95%, 9.21=99%)
    nis_chi2_bound: float = 9.21

    # A4 estimator hardening ------------------------------------------------------
    # Feed EgoEstimate.quality into R: when the ego-motion estimate is poor (quality<1),
    # the rate channels are less trustworthy, so inflate their measurement variance.
    # At quality=1 the factor is exactly 1.0 (a no-op -> nominal behaviour unchanged).
    ego_quality_r_inflation: float = 4.0   # R_rate *= 1 + this*(1-quality); 0 disables
    # TRUE NIS (rate channels, using the innovation covariance S, not R-only): a real
    # maneuver inflates S via the maneuver-mode P and stays bounded, so a SUSTAINED
    # exceedance is a genuine "model-wrong" event, not a jink.  This drives the live alarm.
    nis_gate_chi2: float = 9.21            # 2-DOF chi-square 99% bound for the true-NIS gate
    nis_sustain_for_alarm: int = 5         # consecutive true-NIS exceedances before the alarm
    # Covariance-sized association gate: chi-square scale on the predicted bearing innovation
    # std (sqrt of S diagonal) the pipeline turns into a px search box (replaces the fixed gate).
    gate_chi2_scale: float = 3.0           # ~3 sigma (chi ~ sqrt(9.21)) box half-width

    # R2 robust update (default-OFF -> bit-identical) -------------------------------
    # Huber-clip the STATE UPDATE for an in-gate tail innovation (glint), while the likelihood
    # stays RAW so the maneuver mode is never blinded; down-weights beyond huber_delta sigmas.
    huber_enabled: bool = False
    huber_delta: float = 3.0
    # Inflate the BEARING-channel R as the target's pixel extent grows (centroid/glint error
    # scales with the resolved footprint). r_extent_k default 0 = off (the magnitude is gated on
    # the V5 field measurement; only the mechanism ships now).
    r_extent_k: float = 0.0
    r_extent_ref_px: float = 100.0

    # Per-mode covariance carry (audit 2026-06-25 fix; default TRUE = correct IMM) -------------------
    # Standard IMM (Bar-Shalom) carries each mode's OWN updated covariance P_upd[j] into the next
    # cycle's mixing, so the CV mode stays TIGHT and the maneuver mode stays LOOSE -- that per-mode
    # spread is exactly what lets the predicted innovation covariance S adapt.  The legacy code
    # overwrote BOTH modes with the single COMBINED posterior (P[0]==P[1]), collapsing that
    # distinction and inflating the filter (conservative NEES/NIS).  TRUE restores per-mode carry;
    # FALSE reproduces the legacy overwrite bit-for-bit (kept for A/B against the consistency harness).
    # The combined posterior is always available on ``_P_combined`` for consumers/diagnostics.
    per_mode_covariance: bool = True

    # dt-discretised process noise (audit 2026-06-25; default FALSE = legacy, bit-identical) -----------
    # Legacy ``_make_Q`` puts a raw ``q_rate`` on the two RATE-diagonal entries only, with NO dt scaling
    # and NO position/cross terms -- so the injected process noise per frame is independent of the frame
    # rate and inflates the prior (a dominant driver of the conservative NEES/NIS).  When TRUE, Q is the
    # proper continuous-white-noise-acceleration discretisation per axis,
    #     Q_axis = q_c * [[dt^3/3, dt^2/2], [dt^2/2, dt]],
    # with ``q_cv_rate`` / ``q_maneuver_rate`` reinterpreted as the continuous PSD ``q_c`` (rad^2/s^3).
    # Kept behind a flag because it re-scales the effective Q by ~dt and thus needs a q_c re-tune +
    # closed-loop re-validation before it can flip the production default.
    q_dt_discretized: bool = False


# ---------------------------------------------------------------------------
# IMM filter
# ---------------------------------------------------------------------------

class IMMFilter:
    """Interacting Multiple Model filter on body-frame LOS state.

    See module docstring for full description of the algorithm and conventions.

    Parameters
    ----------
    config:
        IMMFilter configuration.
    """

    _N_MODES: int = 2   # 0=CV, 1=MANEUVER

    def __init__(self, config: IMMConfig | None = None) -> None:
        self._cfg = config or IMMConfig()
        cfg = self._cfg

        # Mode probabilities: [p_cv, p_maneuver]
        p0 = cfg.init_mode_prob_cv
        self._mode_probs: npt.NDArray[np.float64] = np.array(
            [p0, 1.0 - p0], dtype=np.float64
        )

        # Transition matrix (Markov)
        ps = cfg.transition_prob_stay
        self._trans: npt.NDArray[np.float64] = np.array(
            [[ps, 1.0 - ps],
             [1.0 - ps, ps]],
            dtype=np.float64,
        )

        # Per-mode state estimates (x: [az, el, az_rate, el_rate])
        self._x: list[npt.NDArray[np.float64]] = [
            np.zeros(4, dtype=np.float64),
            np.zeros(4, dtype=np.float64),
        ]

        # Per-mode covariance matrices (4x4)
        init_cov = np.diag([
            (0.01) ** 2,           # az (rad²)
            (0.01) ** 2,           # el
            (0.1) ** 2,            # az_rate (rad/s)²
            (0.1) ** 2,            # el_rate
        ])
        self._P: list[npt.NDArray[np.float64]] = [
            init_cov.copy(),
            init_cov.copy(),
        ]
        # Combined posterior covariance (Bar-Shalom & Li 11.6.6), always kept for consumers/tests.
        self._P_combined: npt.NDArray[np.float64] = init_cov.copy()

        # Build measurement matrix H: we measure all 4 states
        self._H = np.eye(4, dtype=np.float64)

        # Per-mode measurement noise covariances
        self._R = np.diag([
            cfg.sigma_meas_az ** 2,
            cfg.sigma_meas_el ** 2,
            cfg.sigma_meas_az_rate ** 2,
            cfg.sigma_meas_el_rate ** 2,
        ]).astype(np.float64)

        # Per-mode process noise covariances
        self._Q: list[npt.NDArray[np.float64]] = [
            self._make_Q(cfg.q_cv_rate),
            self._make_Q(cfg.q_maneuver_rate),
        ]

        self._initialized: bool = False
        self._sustain_count: int = 0   # consecutive frames with p_maneuver > 0.5
        self._nis_bad_count: int = 0   # consecutive frames with true-NIS above the chi2 gate (A4)

    @staticmethod
    def _make_Q(q_rate: float) -> npt.NDArray[np.float64]:
        """Build 4x4 process noise matrix.

        Models random angular acceleration (jerk on the LOS-rate):
            Q = [[0, 0, 0, 0],
                 [0, 0, 0, 0],
                 [0, 0, q_rate, 0],
                 [0, 0, 0, q_rate]]
        The bearing states are driven by the rate states, not by direct noise.
        """
        Q = np.zeros((4, 4), dtype=np.float64)
        Q[2, 2] = q_rate
        Q[3, 3] = q_rate
        return Q

    @staticmethod
    def _make_Q_disc(q_c: float, dt: float) -> npt.NDArray[np.float64]:
        """dt-discretised continuous-white-noise-acceleration process noise (per axis).

        For each independent axis the [position, rate] block is the exact integral of the WNA model
        (Bar-Shalom, Estimation with Applications, §6.3.2):
            Q_axis = q_c * [[dt^3/3, dt^2/2], [dt^2/2, dt]]
        so both the rate AND the position (and their cross-correlation) get physically-scaled noise, and
        the per-frame injection shrinks correctly with dt.  ``q_c`` is the continuous PSD (rad^2/s^3).
        """
        dt2 = dt * dt
        dt3 = dt2 * dt
        Q = np.zeros((4, 4), dtype=np.float64)
        # az (0) <-> az_rate (2)
        Q[0, 0] = q_c * dt3 / 3.0
        Q[0, 2] = Q[2, 0] = q_c * dt2 / 2.0
        Q[2, 2] = q_c * dt
        # el (1) <-> el_rate (3)
        Q[1, 1] = q_c * dt3 / 3.0
        Q[1, 3] = Q[3, 1] = q_c * dt2 / 2.0
        Q[3, 3] = q_c * dt
        return Q

    def _frame_Q(self, dt: float) -> list[npt.NDArray[np.float64]]:
        """Per-frame process-noise list: dt-discretised WNA when enabled, else the precomputed legacy Q."""
        if self._cfg.q_dt_discretized:
            return [self._make_Q_disc(self._cfg.q_cv_rate, dt),
                    self._make_Q_disc(self._cfg.q_maneuver_rate, dt)]
        return self._Q

    @staticmethod
    def _make_F(dt: float) -> npt.NDArray[np.float64]:
        """Build 4x4 constant-velocity state transition matrix.

        x_{k+1} = F · x_k
            az_{k+1}      = az_k      + az_rate_k · dt
            el_{k+1}      = el_k      + el_rate_k · dt
            az_rate_{k+1} = az_rate_k
            el_rate_{k+1} = el_rate_k
        """
        return np.array([
            [1.0, 0.0, dt,  0.0],
            [0.0, 1.0, 0.0, dt ],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ], dtype=np.float64)

    def initialize(self, los: LOSObservation) -> None:
        """Initialize the filter state from the first LOS observation."""
        x0 = np.array([los.az_rad, los.el_rad, los.az_rate_radps, los.el_rate_radps],
                      dtype=np.float64)
        for i in range(self._N_MODES):
            self._x[i] = x0.copy()
        self._initialized = True

    def update(self, los: LOSObservation, dt: float,
               pixel_extent_px: float | None = None) -> IMMEstimate:
        """Run one IMM step with a new LOS observation.

        Parameters
        ----------
        los:
            Ego-compensated LOS observation from los.py.
        dt:
            Elapsed time since the previous frame (seconds).

        Returns
        -------
        IMMEstimate
            Filtered state estimate + mode probabilities.
        """
        if not self._initialized:
            self.initialize(los)
            return IMMEstimate(
                az_rad=los.az_rad,
                el_rad=los.el_rad,
                az_rate_radps=los.az_rate_radps,
                el_rate_radps=los.el_rate_radps,
                mode_probs=(float(self._mode_probs[0]), float(self._mode_probs[1])),
                maneuver_detected=False,
                frame_id=los.frame_id,
            )

        dt = max(dt, 1e-6)

        # Measurement vector from the LOS observation
        z = np.array([los.az_rad, los.el_rad, los.az_rate_radps, los.el_rate_radps],
                     dtype=np.float64)

        # ── STEP 1: Mode mixing ───────────────────────────────────────────────
        # Compute mixed initial conditions for each mode
        # c_j = sum_i(p(M_j | M_i) * mu_i)  — predicted mode probability
        # mu_ij = p(M_j | M_i) * mu_i / c_j  — mixing probability
        c = self._trans.T @ self._mode_probs  # shape (2,)
        c = np.maximum(c, 1e-300)             # avoid division by zero

        x_mix: list[npt.NDArray[np.float64]] = []
        P_mix: list[npt.NDArray[np.float64]] = []

        for j in range(self._N_MODES):
            mu_mix = self._trans[:, j] * self._mode_probs / c[j]  # shape (2,)
            xm = np.zeros(4, dtype=np.float64)
            for i in range(self._N_MODES):
                xm += mu_mix[i] * self._x[i]
            x_mix.append(xm)

            Pm = np.zeros((4, 4), dtype=np.float64)
            for i in range(self._N_MODES):
                diff = self._x[i] - xm
                Pm += mu_mix[i] * (self._P[i] + np.outer(diff, diff))
            P_mix.append(Pm)

        # ── STEP 2: Mode-matched Kalman prediction + update ──────────────────
        F = self._make_F(dt)
        Q = self._frame_Q(dt)   # dt-discretised WNA when enabled, else the legacy precomputed Q

        # ── EGO GATE: compute a SINGLE gate decision from the combined prediction ─
        # Use x_pred_combined = Σ_j c[j]*x_mix[j] as the single best-effort
        # prediction for gating, so the gate decision is consistent and matches
        # the diagnostic output field ego_gate_active (Fix 4 — single gate flag).
        x_pred_combined_gate = np.zeros(4, dtype=np.float64)
        for j in range(self._N_MODES):
            x_pred_combined_gate += c[j] * x_mix[j]
        x_pred_combined_gate = F @ x_pred_combined_gate
        innov_gate = z - self._H @ x_pred_combined_gate
        ego_gate_active = (
            abs(innov_gate[2]) > self._cfg.ego_gate_radps
            or abs(innov_gate[3]) > self._cfg.ego_gate_radps
        )

        # ── A4: feed EgoEstimate.quality into R ───────────────────────────────
        # A poor ego-motion estimate corrupts the de-rotated rate measurement, so inflate the
        # RATE channels of R when los.ego_quality < 1.  At quality == 1 the factor is 1.0, so a
        # clean (gyro-only) frame is bit-identical to the previous behaviour.
        q_ego = min(max(float(los.ego_quality), 0.0), 1.0)
        r_infl = 1.0 + self._cfg.ego_quality_r_inflation * (1.0 - q_ego)
        # Base measurement-noise covariance for this frame.
        if self._cfg.measurement_mode == "correlated_r":
            # The az/el RATE "measurements" are finite differences of the bearing -> ~2x noisier
            # (scaled by 1/dt) AND correlated with the bearing.  Model the true per-axis covariance
            # [[σ², σ²/dt],[σ²/dt, 2σ²/dt²]] instead of pretending the rate is an independent,
            # over-precise measurement (the diagonal-R double-count that made NIS≈2).
            dt2 = dt * dt
            sb_az = self._cfg.sigma_meas_az ** 2
            sb_el = self._cfg.sigma_meas_el ** 2
            R_frame = np.zeros((4, 4), dtype=np.float64)
            R_frame[0, 0] = sb_az
            R_frame[1, 1] = sb_el
            R_frame[2, 2] = 2.0 * sb_az / dt2
            R_frame[3, 3] = 2.0 * sb_el / dt2
            R_frame[0, 2] = R_frame[2, 0] = sb_az / dt
            R_frame[1, 3] = R_frame[3, 1] = sb_el / dt
        else:  # "diagonal_r" — legacy independent-rate model (bit-identical to before)
            R_frame = self._R.copy()
        R_frame[2, 2] *= r_infl
        R_frame[3, 3] *= r_infl
        # R2: inflate the BEARING-channel measurement noise as the target's pixel extent grows
        # (a resolved/glinting target has a noisier centroid). r_extent_k=0 -> no-op.
        if self._cfg.r_extent_k > 0.0 and pixel_extent_px is not None and pixel_extent_px > 0.0:
            ext_infl = 1.0 + self._cfg.r_extent_k * max(
                float(pixel_extent_px) / max(self._cfg.r_extent_ref_px, 1e-9) - 1.0, 0.0)
            R_frame[0, 0] *= ext_infl
            R_frame[1, 1] *= ext_infl

        # ── A4: combined predicted innovation covariance S (for the TRUE NIS + covariance box) ─
        P_pred_combined = np.zeros((4, 4), dtype=np.float64)
        for j in range(self._N_MODES):
            P_pred_combined += c[j] * (F @ P_mix[j] @ F.T + Q[j])
        S_combined = self._H @ P_pred_combined @ self._H.T + R_frame

        x_upd: list[npt.NDArray[np.float64]] = []
        P_upd: list[npt.NDArray[np.float64]] = []
        log_likelihoods: list[float] = []

        for j in range(self._N_MODES):
            x_pred = F @ x_mix[j]
            P_pred = F @ P_mix[j] @ F.T + Q[j]

            # Innovation (per-mode, for Kalman update and likelihood)
            innov = z - self._H @ x_pred  # (4,)
            S = self._H @ P_pred @ self._H.T + R_frame  # (4, 4)

            # Kalman gain
            try:
                S_inv = np.linalg.inv(S)
            except np.linalg.LinAlgError:
                S_inv = np.linalg.pinv(S)

            K = P_pred @ self._H.T @ S_inv  # (4, 4)
            # R2 Huber: down-weight the STATE UPDATE for a large in-gate (tail-glint) innovation.
            # The likelihood below uses the RAW innovation, so the maneuver mode is NOT blinded.
            innov_upd = innov
            if self._cfg.huber_enabled:
                d = math.sqrt(max(float(innov @ S_inv @ innov), 0.0))
                if d > self._cfg.huber_delta:
                    innov_upd = innov * (self._cfg.huber_delta / d)
            x_new = x_pred + K @ innov_upd
            P_new = (np.eye(4) - K @ self._H) @ P_pred

            x_upd.append(x_new)
            P_upd.append(P_new)

            # Gaussian log-likelihood of the innovation under this mode.
            # Using log-space to avoid numerical underflow with large innovations.
            sign, logdet = np.linalg.slogdet(S)
            if sign <= 0:
                logdet = 30.0  # degenerate: assign low likelihood
            mahal = float(innov @ S_inv @ innov)
            log_like = -0.5 * (mahal + logdet + 4 * math.log(2 * math.pi))

            # EGO GATE: add a log-penalty to maneuver-mode log-likelihood
            # when the COMBINED-prediction innovation looks like an ego residual
            # AND the maneuver has NOT been sustained for N_SUSTAIN frames.
            # The gate flag is a SINGLE decision (computed above) — consistent
            # with the diagnostic output field and the live gating logic.
            # Using log-space: damping factor 0.3 → log(0.3) ≈ -1.20 penalty.
            if j == 1 and ego_gate_active and self._sustain_count < self._cfg.n_sustain_for_maneuver:
                log_like += math.log(max(self._cfg.ego_gate_damping, 1e-300))

            log_likelihoods.append(log_like)

        # ── STEP 3: Mode-probability update (log-space for numerical stability) ─
        # Compute log(c_j) = log(c[j]) + log_like[j], then normalise.
        log_c = np.log(np.maximum(c, 1e-300))
        log_c_prod = log_c + np.array(log_likelihoods, dtype=np.float64)

        # Subtract the max for numerical stability before exp
        log_c_prod_shifted = log_c_prod - np.max(log_c_prod)
        c_prod = np.exp(log_c_prod_shifted)
        total = float(np.sum(c_prod))
        if total < 1e-300:
            new_probs = self._mode_probs.copy()
        else:
            new_probs = c_prod / total

        # ── STEP 4: Combined estimate (Bar-Shalom & Li 1993, eq 11.6.6) ────────
        # Combined mean: weighted sum of per-mode updated states.
        x_combined = np.zeros(4, dtype=np.float64)
        for j in range(self._N_MODES):
            x_combined += new_probs[j] * x_upd[j]

        # Combined covariance: sum of per-mode covariances PLUS spread-of-means term.
        # P_combined = Σ_j μ_j * [P_upd[j] + (x_upd[j]-x_combined)⊗(x_upd[j]-x_combined)]
        # This prevents the next cycle's mixing from using an overconfident per-mode
        # posterior — the spread-of-means term inflates uncertainty appropriately
        # after a mode transition (e.g., post-maneuver back to CV).
        P_combined = np.zeros((4, 4), dtype=np.float64)
        for j in range(self._N_MODES):
            diff_j = x_upd[j] - x_combined
            P_combined += new_probs[j] * (P_upd[j] + np.outer(diff_j, diff_j))

        # Carry PER-MODE posteriors into the next cycle's mixing (correct IMM): the CV mode stays
        # tight, the maneuver mode stays loose, and the mixing step's spread-of-means term inflates
        # uncertainty at a transition on its own.  The combined posterior is kept separately for
        # consumers/diagnostics.  (per_mode_covariance=False reproduces the legacy overwrite.)
        self._x = x_upd
        self._P_combined = P_combined
        if self._cfg.per_mode_covariance:
            self._P = [P.copy() for P in P_upd]
        else:
            self._P = [P_combined.copy(), P_combined.copy()]
        self._mode_probs = new_probs

        # Track sustained maneuver detection
        p_maneuver = float(new_probs[1])
        if p_maneuver > 0.5:
            self._sustain_count += 1
        else:
            self._sustain_count = 0

        maneuver_detected = (
            p_maneuver > 0.5
            and self._sustain_count >= self._cfg.n_sustain_for_maneuver
        )

        # A4: conservative NIS-proxy lock-quality (DIAGNOSTIC ONLY -- never feeds the filter).
        # Normalize the rate innovation by the measurement noise R only (ignoring P), so it
        # OVER-estimates inconsistency -> fail-safe. A sustained large value is a "model-wrong"
        # alarm for the lock-quality / commit gate.  (True NIS using the prior covariance S is
        # a later refinement; the R-only proxy is strictly more conservative.)
        sa = max(self._cfg.sigma_meas_az_rate, 1e-9)
        se = max(self._cfg.sigma_meas_el_rate, 1e-9)
        nis = (float(innov_gate[2]) / sa) ** 2 + (float(innov_gate[3]) / se) ** 2
        if not np.isfinite(nis):
            nis = float("inf")
        model_ok = bool(nis <= self._cfg.nis_chi2_bound)
        lock_quality = 1.0 / (1.0 + nis / self._cfg.nis_chi2_bound)   # 1@0, 0.5@bound, ->0

        # A4: TRUE NIS on the rate channels using the innovation covariance S (not R-only).
        # S inflates during a real maneuver (maneuver-mode P grows), so a genuine jink does NOT
        # trip this -- only a SUSTAINED exceedance (measurements the filter cannot explain) does,
        # which is what the live "model-wrong" alarm flags for the engage-permission gate.
        ir = innov_gate[2:4]
        Srr = S_combined[2:4, 2:4]
        try:
            nis_true = float(ir @ np.linalg.inv(Srr) @ ir)
        except np.linalg.LinAlgError:
            nis_true = float(ir @ np.linalg.pinv(Srr) @ ir)
        if not np.isfinite(nis_true):
            nis_true = float("inf")
        if nis_true > self._cfg.nis_gate_chi2:
            self._nis_bad_count += 1
        else:
            self._nis_bad_count = 0
        model_wrong_alarm = self._nis_bad_count >= self._cfg.nis_sustain_for_alarm
        # Predicted bearing innovation std (sqrt of S diagonal) -> covariance-sized search box.
        gate_sigma_az = math.sqrt(max(float(S_combined[0, 0]), 0.0))
        gate_sigma_el = math.sqrt(max(float(S_combined[1, 1]), 0.0))

        # ego_gate_active is already computed above from the COMBINED prediction.
        # Use innov_gate (indices 2,3) for the diagnostic innovation fields so
        # the live gate flag and the reported innovation are from the same source.
        return IMMEstimate(
            az_rad=float(x_combined[0]),
            el_rad=float(x_combined[1]),
            az_rate_radps=float(x_combined[2]),
            el_rate_radps=float(x_combined[3]),
            mode_probs=(float(new_probs[0]), float(new_probs[1])),
            maneuver_detected=maneuver_detected,
            frame_id=los.frame_id,
            innovation_az=float(innov_gate[2]),
            innovation_el=float(innov_gate[3]),
            ego_gate_active=ego_gate_active,
            nis=float(nis),
            lock_quality=float(lock_quality),
            model_ok=model_ok,
            nis_true=float(nis_true),
            model_wrong_alarm=model_wrong_alarm,
            gate_sigma_az_rad=float(gate_sigma_az),
            gate_sigma_el_rad=float(gate_sigma_el),
        )


# ---------------------------------------------------------------------------
# Alpha-beta fallback tracker (documented simpler alternative)
# ---------------------------------------------------------------------------

@dataclass
class AlphaBetaState:
    """Mutable state for the alpha-beta tracker."""

    az: float = 0.0
    el: float = 0.0
    az_rate: float = 0.0
    el_rate: float = 0.0
    initialized: bool = False


class AlphaBetaTracker:
    """Simple alpha-beta tracker on body-frame LOS.

    Alpha-beta is a fixed-gain 2-state tracker:
        prediction:
            az_pred = az + az_rate * dt
            az_rate_pred = az_rate
        correction:
            az       += alpha * (z_az - az_pred)
            az_rate  += beta  * (z_az - az_pred) / dt
        (and analogously for el)

    This is the classical «g-h filter».  It has no mode switching, no ego gate,
    and no maneuver detection.  It is documented as a fallback when the full IMM
    is over-engineered.

    IMPORTANT: This tracker does NOT gate innovations against ego-residuals.
    For production ego-residual rejection, use IMMFilter.

    Suggested parameters (Benedikt, 1992):
        alpha = 0.5   — moderate smoothing
        beta  = 0.1   — slow rate adaptation
    Faster target: increase both.  Noisier measurement: decrease alpha.
    """

    def __init__(self, alpha: float = 0.5, beta: float = 0.1) -> None:
        if not (0.0 < alpha < 1.0):
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")
        if not (0.0 < beta < 1.0):
            raise ValueError(f"beta must be in (0, 1), got {beta}")
        self._alpha = alpha
        self._beta = beta
        self._state = AlphaBetaState()

    def reset(self) -> None:
        """Reset to uninitialized state."""
        self._state = AlphaBetaState()

    def update(self, los: LOSObservation, dt: float) -> tuple[float, float, float, float]:
        """Update the alpha-beta tracker.

        Returns
        -------
        (az_rad, el_rad, az_rate_radps, el_rate_radps)
        """
        dt = max(dt, 1e-6)
        s = self._state

        if not s.initialized:
            s.az = los.az_rad
            s.el = los.el_rad
            s.az_rate = los.az_rate_radps
            s.el_rate = los.el_rate_radps
            s.initialized = True
            return s.az, s.el, s.az_rate, s.el_rate

        # Prediction
        az_pred = s.az + s.az_rate * dt
        el_pred = s.el + s.el_rate * dt

        # Innovation
        res_az = los.az_rad - az_pred
        res_el = los.el_rad - el_pred

        # Correction
        s.az = az_pred + self._alpha * res_az
        s.el = el_pred + self._alpha * res_el
        s.az_rate = s.az_rate + self._beta * res_az / dt
        s.el_rate = s.el_rate + self._beta * res_el / dt

        return s.az, s.el, s.az_rate, s.el_rate
