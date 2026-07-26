> **[REFERENCE]** — status as of 2026-07-19. Durable estimation/observability science. Note it references the learned classifier, which was deleted 2026-07-11.
>
> **`docs/CHECKPOINT.md` is the source of truth.** Where this document disagrees with it, CHECKPOINT wins.

<!-- Generated 2026-06-19 by a multi-agent study of published bearings-only target-motion-analysis,
visual-inertial-odometry observability, strapdown-seeker LOS-rate reconstruction, and Kalman-filter
consistency/validation methodology, mapped onto this repo's estimation code. Scope: software (estimation
and test-methodology) only — NO warhead/propellant/fuze-lethality, no munition uplift. -->

# STATE ESTIMATION & OBSERVABILITY BRIEFING — Block-03 Thermal Counter-UAS Interceptor
## The Honest, CPU-Feasible Estimator for a Passive Monocular Thermal-Bearing + FC-IMU Interceptor

**Audience:** Block-03 engineering team · **Author:** Chief estimation/observability architect · **Scope:** software only (state estimation, observability, test methodology; no lethality/fuze engineering, no munition uplift) · **Platform:** RPi5 CPU + FT640 / Boson-640 8-bit AGC analog thermal, passive monocular, **body-fixed (strapdown) seeker**, FC-IMU (gyro + accel).

> **Read `GUIDANCE_DOCTRINE_BRIEFING.md` and `FIRE_AND_FORGET_AUTONOMY_BRIEFING.md` first.** This document **builds on them and does not repeat them.** The guidance briefing settled the coherence-tracker + PN back-half and the τ/Vc honesty (§4–§5). The autonomy briefing settled the LOBL state machine, the AI discrimination slot, and the commit/abort safety spine. **This briefing sits UNDERNEATH both:** it is about the *numbers that feed them* — the ego-motion estimate that makes `λ̇` real, the IMM/Kalman that filters it, and the deep **observability** question of what a single passive station can and cannot know about range and closing speed. The design baseline (`BLOCK03_THERMAL_INTERCEPTOR_DESIGN.md` §3.2–§3.3) already states the headline result — *no range/Vc without own-maneuver parallax*. **Here we prove it, quantify it, and turn it into an estimator architecture and a validation pyramid.**

---

## 0. THE ONE-PAGE THESIS

The interceptor's estimation stack answers three questions of decreasing observability:

1. **"Where is the target, in angle?"** — fully observable from one passive station. Our `los.py` + `imm.py` already do this. *Solved; the work is calibration and consistency, not architecture.*
2. **"How fast is the LOS rotating?"** — observable **only after ego-rotation is removed correctly.** This is the single most failure-prone number in the whole system, because a strapdown seeker mixes 100–1000 °/s of body rate into every pixel. *Mostly built (gyro de-rotation); the gaps are time-sync, soft-mount, scale/bias, and online gyro-error estimation — all calibration, all measurable.*
3. **"How far, and how fast closing?"** — **fundamentally UNOBSERVABLE from a single passive station holding a non-accelerating bearing.** This is not a CPU limit, not a sensor-quality limit, not an algorithm we haven't found yet — it is a **rank deficiency of the Fisher information matrix.** No filter, no neural net, and no amount of cleverness manufactures range from a straight-line bearing history. The design baseline's "bearing-rate nuller, not PN" is the *correct surrender* to this theorem.

**The three load-bearing consequences:**

1. **Keep the target filter in MODIFIED POLAR coordinates, not Cartesian.** The published TMA literature is unambiguous: modified-polar (MP) coordinates **automatically decouple the observable subspace (bearing, bearing-rate, and range-normalized closing rate) from the unobservable one (absolute range), preventing the covariance ill-conditioning that is the #1 cause of bearings-only filter divergence.** Our IMM state `[az, el, az_rate, el_rate]` is *already* a reduced MP-style state that carries only observable quantities — this is accidentally correct and must be made *deliberately* correct, with the unobservable range explicitly excluded rather than silently assumed.

2. **Range becomes observable ONLY if the interceptor out-accelerates the target's contribution to the bearing history — and we can exploit that, carefully.** Own-maneuver / accelerated triangulation is the *only* passive range recovery mechanism. A homing interceptor under PN *does* maneuver, so a *weak, late, heavily-gated* range estimate is recoverable in principle. But the same PN that nulls `λ̇` drives the geometry toward the **degenerate, unobservable** case (constant bearing = collision triangle = zero parallax). **Range observability and good guidance are in direct tension on a homing round.** Treat any recovered range as a bonus cross-check, never as a guidance input — exactly as the design baseline already treats τ.

3. **The estimator that is HONEST and CPU-feasible is a two-tier filter:** (a) a body-frame **MP-IMM** on `[az, el, az_rate, el_rate]` (what we have, hardened) producing the guidance `λ̇`; and (b) an **optional, gated, single-state range-observer** (an EKF/UKF on inverse-range or a one-dimensional looming+own-accel fusion) that runs *only* when an observability index says the geometry currently supports it, and whose output feeds *only* diagnostics, `t_go` shaping, and the commit gate — **never the PN gain.** Everything fits in microseconds on the Pi; the cost is calibration discipline and Monte-Carlo consistency testing, not FLOPs.

**Honest bottom line up front:** our angular estimation is sound and the remaining work is *metrology* (time-sync, soft-mount, gyro scale/bias, filter tuning proven by NEES/NIS). Our range/closing-speed estimation is *bounded by a theorem we cannot beat*, and the only honest move is to (a) keep it out of the guidance gain, (b) recover a weak range cross-check from own-maneuver when the geometry allows, and (c) buy the missing observability with hardware (a terminal active ranger) *if and only if* a timed effect ever requires it — which the guidance briefing §4 already flagged. Anyone who claims a monocular passive seeker "estimates range with a good Kalman filter" on a constant bearing is contradicting the Cramér-Rao bound.

---

## 1. THE OBSERVABILITY PROBLEM — STATED, PROVEN, QUANTIFIED

### 1.1 Why a single passive station cannot see range (the theorem, not a vibe)

A bearings-only observer measures the **angle** to the target, never the range along that angle. Two targets — one near and slow, one far and fast — that produce the **identical bearing time-history** are **mathematically indistinguishable** to the filter. The formal statement: the system is **observable** (range is uniquely recoverable from the bearing history) **if and only if the observer's motion provides bearing-rate information that a single rigid translation of the target cannot explain.** The published TMA result is precise and counter-intuitive:

> **A non-maneuvering observer can NEVER estimate the range of a constant-velocity target from bearings alone** — the Fisher information matrix is rank-deficient and the Cramér-Rao lower bound on range is **infinite**. Range observability requires the **observer to maneuver** (accelerate), and even then **certain observer maneuvers leave the system unobservable even when the bearing rate is nonzero** — a subtlety routinely missed in heuristic discussions.

The deep machinery: the **Fisher Information Matrix (FIM)** for the estimation problem is rank-deficient in the range direction unless observer acceleration enters the bearing measurement equation. The **CRLB = FIM⁻¹** then has an infinite eigenvalue along range. Optimal-observer-trajectory work maximizes `det(FIM)` (or minimizes `trace(CRLB)`) precisely because that is the knob that lifts range out of the unobservable subspace. **No estimator beats the CRLB; if the FIM is rank-deficient, no estimator on Earth recovers range.**

This is why the design baseline's surrender is *correct physics*, not timidity: "одна камера без собственного манёвра-параллакса **не видит ни дальности, ни скорости сближения**" is the FIM rank-deficiency theorem, restated.

### 1.2 What own-maneuver / accelerated triangulation recovers (and the cruel catch)

Own-maneuver works by **baseline synthesis**: as the observer accelerates laterally, it sweeps out a baseline, and the differential bearing across that baseline triangulates range — the passive analogue of stereo, with the stereo baseline grown over *time* by *your own motion*. The classic recipe is the **"S-maneuver"**: a lateral weave on the line of sight that maximizes the synthesized baseline perpendicular to the LOS. FIM intuition: **information toward range grows with the component of observer acceleration perpendicular to the LOS, integrated over the observation window.**

**The cruel catch for a homing interceptor — observability and guidance fight each other:**

- **PN nulls `λ̇` → drives toward constant bearing → collision triangle → ZERO parallax → range goes UNOBSERVABLE exactly as you close.** The better your guidance, the blinder your ranging. This is the geometric dual of the looming degeneracy the guidance briefing already noted (crossing: `dA/dt → 0`).
- **A range-recovering S-maneuver is a guidance-DEGRADING maneuver** — it deliberately *un-nulls* `λ̇` to grow the baseline, costing energy and miss-distance, on a platform the design baseline already flags as tilt-/g-limited (§ weight/agility).
- The **commit maneuver itself** (the body rotating to apply lateral g, autonomy briefing §1.3a) *does* inject a brief baseline — so a **transient, opportunistic** range observation is recoverable from the natural homing maneuver **without** a dedicated S-weave. This is the only "free" range information we get, and it is weak, late, and noisy.

**Doctrine: never command a maneuver for the *purpose* of ranging on a kinetic run.** Harvest range opportunistically from maneuvers commanded for *guidance*, treat the result as a gated cross-check, and accept that in the cleanest collision geometry (the one you want) range is *least* observable.

### 1.3 The numbers — how bad is "weak"?

The VIO literature quantifies the *same* observability physics for the ego-motion problem and gives us a transferable scale (Section 2). For the **target-range** problem the published bearings-only results are blunt: with realistic bearing noise (sub-degree) and a non-aggressive observer, **range error of tens of percent is typical and the estimate often does not converge until late in the engagement, if at all.** Two-observer or range-aided geometries collapse the error by an order of magnitude — which is exactly why the guidance briefing §4 and autonomy briefing §5 both land on "fuse one short-range active ranger in the terminal window" as the *only principled* way to actually *know* range. **The honest planning number: assume range/Vc are NOT available to guidance, ever, on the passive-only configuration. Any passive range estimate is a sign-and-order-of-magnitude sanity check, nothing more.**

---

## 2. EGO-MOTION & VIO — THE SAME OBSERVABILITY THEOREM, ON OUR OWN MOTION

The target-range observability gap has an exact mirror in **our own** state: a monocular camera cannot recover **metric scale** of its own translation without inertial help, and even *with* an IMU, scale is observable **only under acceleration excitation.** This is not a tangent — it is why our ego-motion stack is **gyro-de-rotation-only and deliberately does NOT attempt translational VIO.** That choice is correct, and the literature tells us exactly why.

### 2.1 Metric scale needs acceleration — Fisher information ∝ squared acceleration

The published result (directly transferable):

> **Monocular VIO cannot recover metric scale from vision alone; scale is resolved only through inertial measurements, and the Fisher information toward scale is proportional to the SQUARED translational acceleration.** Without accelerometer excitation, monocular VIO **cannot observe scale and suffers severe drift.** Reported scale errors by trajectory: **straight-line ≈ 9.2%, circular ≈ 6.4%, figure-eight ≈ 4.8%** — i.e. richer acceleration content monotonically improves scale, spanning four orders of magnitude of excitation. Constant-velocity (zero-acceleration) motion is **immediately un-initializable** — the gravity/acceleration asymmetry the accelerometer relies on vanishes.

**Why this kills translational VIO for our terminal:** a homing interceptor on a clean collision course is approximately **constant-velocity along a straight LOS** — the *worst possible* excitation for scale. Against a **textureless night sky** (design §3.2: "небо бестекстурно") there are also no visual features to anchor structure-from-motion. So translational VIO would be **doubly degenerate** (no excitation + no texture) precisely in our operating regime. **The gyro-only base is not a poor-man's VIO — it is the theoretically-correct choice given our excitation and texture conditions.** Attempting full VIO would burn CPU to produce a confidently-wrong scaled translation that corrupts the LOS rate.

### 2.2 What gyro de-rotation gives us, and what it cannot (the strapdown LOS-rate problem)

`egomotion.gyro_derotation()` predicts the scene shift from body rate and `los.py` subtracts it — this is the **strapdown seeker LOS-rate reconstruction** problem, and the published seeker literature names every failure mode we must respect:

> A strapdown seeker has **no mechanical isolation** between sensing frame and body, so the guidance signal "tends to get corrupted by a non-negligible fraction of the platform motion despite subtraction of body motion using rate gyros and decoupling loops." The residual after subtraction drives a **guidance parasitic loop** that can destabilize PN. The dominant residual sources are **(a) gyro scale-factor / bias error** ("nonconformity between the calibrated scales" of the rate source and the angle source induces a LOS-rate error) and **(b) timing/decoupling error.** LOS-rate accuracy "is influenced by bearing-LOS-angle accuracy and the bias stability of the gyro."

This is *exactly* the residual our IMM `ego_gate_radps` mechanism (imm.py §"INNOVATION GATING") is built to catch — but the gate is a *symptom suppressor*; the *cure* is calibration. Three residual sources, three cures, all measurable on a turntable (design S0):

| Residual source | Effect on `λ̇` | Cure (measurable, CPU-cheap) |
|---|---|---|
| **Cam↔IMU time offset** | Under high body **angular acceleration**, a constant time offset makes the de-rotation subtract the wrong-instant body rate → transient `λ̇` spike that mimics a target jink. Published VIO result: the error scales with **angular acceleration × offset**, so it is worst exactly during the commit snap. | Measure offset to **<1 ms** on a turntable (design S0, already gating); then **estimate the residual offset ONLINE** as a state (the Kalibr / online-temporal-calibration approach: add `t_d` to the filter state, correct continuously). Sub-ms is the design's own gate; online estimation removes the slow drift. |
| **Gyro scale-factor & bias** | A scale error multiplies the *largest* body rates → largest `λ̇` corruption during the fastest rotation (commit, recovery). The "scale nonconformity → parasitic loop" failure. | Turntable scale/bias calibration (design S0) **+ online scale/bias as filter states** (the strapdown decoupling-loop standard). This is the single highest-leverage calibration on the platform. |
| **Soft-mount transfer function** | Boson on gel isolation moves *relative to* the hard-mounted FC gyro → the gyro literally does not measure the camera's true angular motion → an un-modellable de-rotation residual (design §3.2, flagged critical). | **Either** characterize the soft-mount transfer function and map gyro→camera motion, **OR hard-mount the camera and isolate the frame elsewhere** (design's own two options). **Recommendation: hard-mount the camera.** A characterized transfer function is a frequency-dependent, temperature-dependent, aging liability in the single most safety-critical signal; removing it by construction is worth the vibration penalty. This is an *estimation-integrity* argument the design flags but does not resolve — **resolve it toward hard-mount.** |

### 2.3 The KLT residual is a cross-check, never a base — and that is correct

`sparse_lk_residual()` returns `None` on textureless sky (< 12 inliers) and falls back to gyro-only. This is doctrinally right: on a night sky there is **no structure to do visual ego-motion against**, and even where there is (ground in the FOV during look-down), the recovered shift is a **translation+parallax** estimate with **unobservable metric scale** (§2.1). Use KLT/homography exactly as the guidance briefing A3 proposes — as a **residual-motion mask and a gyro cross-check** — and **never** promote it to a metric velocity. The `EgoEstimate.quality` field is the right place to down-weight the IMM's trust in the de-rotation when inliers are low; wire it into the measurement noise `R`, not just diagnostics.

---

## 3. THE HONEST ESTIMATOR ARCHITECTURE — TWO TIERS, MP COORDINATES, OBSERVABILITY-GATED

### 3.1 Tier 1 — the body-frame MP-IMM (what we have, made deliberately correct)

Our `imm.py` runs an IMM on `x = [az, el, az_rate, el_rate]`. **This is already a reduced modified-polar state** — it carries the **observable** quantities (bearing and bearing-rate in two planes) and **excludes the unobservable absolute range by construction.** That is the textbook-correct structure for single-station passive tracking, and we should *name* it as such and defend it:

- **Why MP and not Cartesian (the published reason):** "MP coordinates are well-suited for bearings-only TMA because they **automatically decouple observable and unobservable components**, preventing covariance ill-conditioning — the primary cause of filter instability." A Cartesian `[x,y,z,vx,vy,vz]` target filter on one passive station has an **unobservable direction in its covariance** that grows without bound and eventually **wrecks the conditioning of the whole matrix**, corrupting even the observable bearing states. By keeping the state angular, we never form that ill-conditioned covariance. **Do not "upgrade" the IMM to a Cartesian target state — that is a downgrade.**
- **EKF vs UKF vs PF for this state (published comparison):** for the mildly-nonlinear angular dynamics we have, **EKF and UKF give near-identical accuracy; UKF improves convergence rate and consistency; PF only earns its cost in heavy clutter / strong multimodality.** Our regime (one confirmed track, gated association) does **not** justify a particle filter's CPU. The current **linear-KF-per-mode IMM is appropriate**; if consistency testing (Section 4) shows the small `atan2` nonlinearity in the rate conversion biases the filter, the cheapest honest upgrade is **UKF sigma-points per mode**, not a PF. Budget: UKF is ~2–3× the KF cost — still microseconds.
- **The `q_cv_rate` / `q_maneuver_rate` split is the right maneuver model**, but the IMM literature's standard **Singer / coordinated-turn** mode is worth considering as the maneuver mode if the kinematic classifier (guidance briefing B5) ever needs a turn-rate state. Keep the two-mode bank; do not balloon to a five-model bank (autonomy briefing already rejects the CPU cost).

**Hardening items for Tier 1 (all small, all in `imm.py`/`los.py`):**

1. **Feed `EgoEstimate.quality` into the measurement noise `R`**, not just logs: inflate `sigma_meas_az_rate/el_rate` when ego quality drops (KLT lost, gyro flagged), so the filter automatically distrusts `λ̇` when de-rotation is shaky. Today `R` is fixed.
2. **Add online gyro scale/bias and cam↔IMU time-offset as augmented states** (or a parallel lightweight estimator) — Section 2.2. This converts the `ego_gate` from a blunt damper into a *corrector*. The gate stays as the backstop.
3. **Replace the fixed `ego_gate_radps` threshold with a covariance-derived gate** — the same Mahalanobis/χ² innovation gate the guidance briefing B1 already wants. The threshold then *adapts* to the current rate uncertainty instead of a hand-tuned constant.
4. **Expose the innovation covariance `S` as the calibrated lock-quality / search-box source** — feeds the autonomy briefing's covariance-sized reacquire basket (§1.3b) and the commit gate. `S` is computed every frame already; publish it.

### 3.2 Tier 2 — the OPTIONAL, OBSERVABILITY-GATED range observer (new, diagnostics-only)

Range is sometimes weakly observable (own-maneuver, §1.2) and the looming τ sometimes carries a sign/order cue (existing `looming.py`). Fuse them into a **single scalar range/closing observer that is gated on a live observability index** and feeds **only** `t_go`, diagnostics, and the commit gate:

```
INPUTS                          GATE (must pass to run)           OUTPUT (diagnostics/t_go/commit only)
─────────────────────────────   ───────────────────────────────   ──────────────────────────────────────
looming τ + τ_confidence        observability_index > θ_obs        range_estimate  (+ wide covariance)
own lateral accel (from FC)       where index ≈ ∫ (a_perp · dt)     Vc_estimate     (sign + order)
IMM az_rate/el_rate + S            / range_assumed   (the           t_go_passive    (cross-check vs t_go_sched)
                                   instantaneous FIM-toward-range)   observability_flag (for commit gate)
```

**Design rules (each one is the honest move):**
- **It is a 1-state filter on INVERSE range (`1/r`), not range.** Inverse-range (a.k.a. "modified-polar range" or the parallax parameter) is the quantity that stays bounded and near-Gaussian as `r → ∞`, and whose Fisher information is what own-maneuver actually delivers. Filtering `1/r` avoids the divergence a direct-range filter suffers when observability lapses.
- **The observability index is computed every frame and *published*.** It is essentially the instantaneous FIM-toward-range: large when own perpendicular acceleration is large relative to assumed range and `λ̇` is being changed by *our* motion; ~zero on a clean collision triangle. When it is low, the observer **coasts on prior with inflated covariance** and reports `observable=False`. **This is the estimator telling the truth about when it can and cannot see range** — the single most important honesty feature.
- **Output NEVER touches the PN gain.** `Vc_sched` from `SpeedPolicy` remains the guidance gain (design §3.3, guidance briefing C3). The Tier-2 `Vc_estimate` may *confidence-blend into* `Vc_eff` (guidance briefing C3 already proposes this with `w = tau_confidence`) — extend that weight to `w = min(tau_confidence, observability_confidence)` so the blend trusts looming *only when own-motion also supports it.*
- **It feeds the commit gate's geometry term** (autonomy briefing §4.3d): a high-crossing target shows up here as *high* `λ̇` with *low* range observability and *low* τ confidence — a coherent "this geometry is bad" signal that the commit gate can act on.

**CPU:** a 1-state EKF on `1/r` is arithmetic — single-digit microseconds. The whole Tier-2 observer is cheaper than one detection. **There is no FLOPs reason not to build it; the only reason to keep it diagnostics-only is the observability theorem, which we respect by construction.**

### 3.3 What we explicitly do NOT build (the honest "no" list)

| Tempting addition | Why it is wrong here |
|---|---|
| **Cartesian 6-state target EKF/UKF** | Forms the ill-conditioned covariance with an unobservable direction; the MP/angular state is the published-correct structure. A downgrade dressed as an upgrade. |
| **Translational monocular VIO for ego-motion** | Metric scale is unobservable without acceleration excitation (Fisher info ∝ a²); our terminal is near-constant-velocity against textureless sky — doubly degenerate. Gyro-only is correct. |
| **Particle filter for the LOS track** | PF earns its CPU only under heavy clutter/multimodality; our gated single-track regime does not. UKF is the ceiling if EKF consistency fails. |
| **"Deep-learned monocular depth" for range** | A learned net cannot manufacture observability the optics do not contain (autonomy briefing §2.5). Monocular-depth nets hallucinate metric scale from learned priors that **do not hold for a 1–3 px thermal blob against sky.** A confidently-wrong range is worse than an honest "unobservable." |
| **Trusting τ as range/Vc** | Degenerates at acquisition, crossing, impact (design §3.3; guidance briefing §5). Sign/order cross-check only. |
| **Range-for-guidance from own-maneuver** | Observable only by *un-nulling* `λ̇` — directly degrades guidance. Harvest opportunistically; never command a ranging maneuver on a kinetic run. |

---

## 4. VALIDATION — PROVE THE FILTER IS HONEST BEFORE IT FLIES

An estimator that *reports* a covariance it does not *earn* is more dangerous than no estimator, because the commit gate and the autonomy spine **believe the covariance.** A filter that is over-confident (covariance too small) will pass a commit gate it should fail; one that is under-confident will abort good runs. The published discipline for proving a filter "credible" is **consistency testing**, and it is the spine of our estimation validation pyramid.

### 4.1 NEES / NIS consistency — the non-negotiable filter acceptance test

> **Dynamic consistency requires:** the estimate is unbiased; the filter's reported covariance matches the *true* error covariance; and the innovations are zero-mean white with covariance matching the reported `S`. The **NEES** (Normalized Estimation Error Squared, needs ground truth) and **NIS** (Normalized Innovation Squared, no ground truth — works online) are χ²-distributed for a correctly-tuned filter. **Run N Monte-Carlo truth-model simulations, average NEES/NIS, and χ²-test against the theoretical bounds.** A filter whose NEES rides above the upper χ² bound is **over-confident** (the dangerous direction); below the lower bound is over-conservative.

**Concrete acceptance gates for our IMM (add to the test suite, run in `seeker_sim.py` / `quad_sim.py`):**
- **NEES gate:** over ≥100 Monte-Carlo runs with the truth-model target+ego, the time-averaged NEES of `[az, el, az_rate, el_rate]` must fall inside the 95% two-sided χ²₄ interval. **Failing high = over-confident covariance = commit-gate hazard.** This is a *release gate*, not a nice-to-have.
- **NIS gate (online, ships to the field):** the running NIS of the innovation must stay inside the χ² interval during flight; **a sustained NIS excursion is a live "my model is wrong" alarm** — wire it to lock-quality and (sustained) to ABORT. This is free filter self-diagnosis the autonomy spine should consume.
- **Caveat the literature insists on:** χ² consistency is **necessary, not sufficient** — a filter can be consistent and still mistuned. Pair NEES/NIS with **bias/whiteness checks** on the innovation sequence (zero-mean, no autocorrelation). Auto-tuning of `Q` (the process-noise split `q_cv_rate`/`q_maneuver_rate`) by *enforcing* χ² consistency is a published, cheap way to set those knobs honestly instead of by hand.

### 4.2 The estimation validation pyramid (climb it; never skip a tier)

This is the *estimation-specific* slice of the program's Gate ladder — the order in which the numbers earn trust:

```
 TIER 0  UNIT / ANALYTIC      gyro de-rotation sign chain (los.py docstring already does this);
                              pixel↔bearing round-trip; F/Q/H matrix algebra. Pure, deterministic.
   │
 TIER 1  TRUTH-MODEL MONTE    seeker_sim + quad_sim with KNOWN target+ego truth →
          CARLO (NEES/NIS)    NEES/NIS χ² gates (§4.1); observability-index validation:
                              CONFIRM range observer reports observable=False on a clean
                              collision triangle and True only under commanded baseline.
   │
 TIER 2  HARDWARE-IN-LOOP /   turntable: measure cam↔IMU offset <1 ms + gyro scale/bias (design S0);
          PIXEL-IN-LOOP       INJECT measured gyro errors into the sim → confirm ego_gate + online
                              scale/bias estimator suppress the parasitic λ̇ spike. Soft-mount
                              transfer function characterized OR camera hard-mounted (§2.2) — MEASURED.
   │
 TIER 3  CAPTIVE-CARRY        seeker + IMU recording on a real flying body vs a real cooperative
          (no commit)         target with INDEPENDENT truth (GPS/RTK on both, or survey) →
                              compute REAL NEES against truth; measure real λ̇ error budget;
                              confirm the night-sky gyro-only base holds. NO guidance authority.
   │
 TIER 4  CLOSED-LOOP TETHERED then FREE-FLIGHT NON-KINETIC (design F1) — guidance consumes the
                              estimator; verify miss-distance budget; high-crossing → honest abort.
   │
 TIER 5  LIVE (design F2)     only after every tier above is clean and repeatable; range-safety
                              spine (autonomy briefing §4) gates it. Estimator is FROZEN & versioned.
```

**Two estimation-specific release rules:**
1. **No filter parameter (`Q`, `R`, gate thresholds) is hand-tuned past Tier 1 without a re-run of the NEES/NIS gates.** Re-tuning silently breaks consistency; the χ² test catches it.
2. **The observability index and the NIS alarm are validated as first-class outputs in Tier 1**, because the *autonomy spine depends on them* (commit-gate geometry term, abort-on-model-mismatch). An untested observability flag is a lie the commit gate will believe.

### 4.3 The data the truth-model must contain (estimation slice)

The autonomy briefing §3.5 owns the *classification* dataset; the *estimation* validation needs a **truth-instrumented** complement: every captive-carry and HIL recording must carry **synchronized independent ground truth** (RTK-GPS on interceptor and target, or surveyed geometry) so NEES (which *requires* truth) is computable. Without truth instrumentation you can only check NIS (consistency) and never NEES (correctness) — you would ship a filter you cannot prove is *right*, only that it is *self-consistent*. **Budget the truth instrumentation as a first-class test deliverable**, the estimation analogue of the FT640 data campaign.

---

## 5. HONEST LIMITS — WHAT THE PHYSICS FORBIDS, FOR ESTIMATION

A passive monocular thermal + FC-IMU interceptor on a Pi-class CPU has **structural estimation limits no software removes:**

1. **Range and closing speed are unobservable on the geometry guidance wants.** The FIM is rank-deficient toward range on a constant bearing; PN drives toward constant bearing. **You cannot have both clean homing and good passive ranging.** This is a theorem (CRLB), not a tuning problem.

2. **The one passive range source (own-maneuver parallax) is weakest exactly in the terminal endgame** — collision triangle = zero parallax, and the commit window is where you'd most want range. Mitigation is to **commit earlier on a high-confidence pre-terminal track and fly predicted-lead** (guidance briefing §4) — which trades away late re-validation. No clean escape on a passive seeker.

3. **Metric ego-velocity is unobservable in our regime.** Near-constant-velocity terminal + textureless sky = no scale excitation and no visual structure → translational VIO is doubly degenerate. We get **angular** ego-motion (gyro) only; absolute own-velocity comes from the FC's own GPS/baro/airspeed, not from the seeker.

4. **The LOS-rate is only as clean as the gyro calibration and the mount.** Strapdown LOS-rate reconstruction is corrupted by gyro scale/bias, cam↔IMU time-offset (worst under high angular acceleration — i.e. the commit snap), and the soft-mount transfer function. These are **measurable and correctable** (turntable + online estimation + hard-mount), but they are a **permanent calibration burden**, not a one-time fix — gyro bias drifts with temperature and age.

5. **A consistent filter is not a correct filter.** NIS (online) proves self-consistency, not correctness; only NEES against independent truth proves correctness, and that needs truth instrumentation we must build. Ship the filter only after NEES passes — a self-consistent-but-biased filter will **confidently** feed a wrong covariance to the commit gate.

6. **Any reported range/Vc carries a covariance the consumer MUST honor.** The danger is not the weak estimate; it is a **downstream consumer treating a wide-covariance range as if it were tight.** The architecture forbids this by keeping range out of the PN gain and gating its blend on the observability index — but it is a discipline that must be enforced in code review, not assumed.

### What would change the answer — minimal estimation additions

| Addition | What observability it BUYS | Cost / caveat |
|---|---|---|
| **One short-range active ranger fused only in terminal** (ToF/lidar <100 m, or small Ka-band mmW) | **Directly observes range AND range-rate** → lifts the FIM out of rank-deficiency → true ZEM, true `t_go`, true Vc. "Angle steers, range triggers." | mmW = power/weight/cost; lidar = FOV/weather/eye-safety limited (guidance briefing §4). The only *real* fix to the range theorem. |
| **A second passive station** (a wingman seeker, or a ground sensor cueing) | Two bearings triangulate range with **no own-maneuver needed** — collapses range error ~10×. | Requires a datalink/second platform; contradicts the no-datalink F&F constraint for the round itself, but viable as **launch cueing** (guidance briefing §5 "cue-then-confine"). |
| **Online gyro scale/bias + cam↔IMU time-offset estimation** | Removes the strapdown parasitic-loop residual → cleaner `λ̇` → tighter, more *honest* IMM covariance. | Pure software; a few extra filter states. **Do this regardless** — highest leverage per line of code. |
| **Hard-mounting the camera (vs soft-mount)** | Removes the un-modellable soft-mount transfer-function residual from the single most safety-critical signal. | Vibration penalty on the imager; a deliberate trade we recommend taking. |
| **Truth instrumentation (RTK on both craft) for captive-carry** | Makes **NEES** (correctness) computable, not just NIS (consistency) → lets us *prove* the filter is right. | A test-range/logistics cost; the estimation analogue of the data campaign. |

**None of these is a munition uplift** — every one is a sensing/estimation/test addition to a sense-and-estimate problem.

---

## 6. SHORTLIST — Top 5 Highest-Leverage Estimation Builds, Ordered

1. **Online gyro scale/bias + cam↔IMU time-offset estimation, feeding the IMM** (`egomotion.py` / `imm.py`). *The strapdown parasitic-loop residual is the #1 corruptor of the guidance `λ̇`; turntable calibration (design S0) sets the prior and online estimation removes the drift. Few states, microseconds, single highest-value estimation change. Also flips the `ego_gate` from a blunt damper into a corrector.*

2. **Name and harden the IMM as a modified-polar filter; wire `EgoEstimate.quality`→`R` and `S`→lock-quality/search-box** (`imm.py` / `los.py`). *The angular state is already the observability-correct structure — defend it (no Cartesian "upgrade"), make `R` ego-quality-adaptive, and publish the innovation covariance `S` that the autonomy spine's reacquire basket and commit gate already need (guidance B1, autonomy §1.3b/§4.3).* 

3. **Build the Tier-2 observability-gated inverse-range observer (diagnostics/`t_go`/commit only)** (new `seeker/range_observer.py`). *Fuses looming τ + own lateral accel + IMM rate into a 1-state `1/r` filter behind a published observability index that tells the truth about when range is and is not observable. Feeds `Vc_eff` blend (guidance C3, weight = min(τ_conf, obs_conf)) and the commit-gate geometry term — never the PN gain. Cheaper than one detection.*

4. **NEES/NIS consistency gates as release criteria + online NIS abort alarm** (`seeker/tests/`, `quad_sim.py`). *Monte-Carlo χ² NEES (needs truth) as a hard release gate against over-confident covariance; running NIS (no truth) shipped as a live "model-wrong" alarm wired to lock-quality and ABORT. χ²-consistency auto-tuning to set `Q` honestly instead of by hand. The discipline that makes the covariance the commit gate believes actually earned.*

5. **The estimation validation pyramid with truth instrumentation** (test plan + captive-carry RTK on both craft). *Climb Tier 0→5 in order; the captive-carry tier needs synchronized independent ground truth so NEES (correctness, not just NIS self-consistency) is computable. Resolve the soft-mount question toward hard-mounting the camera and MEASURE the result at the HIL tier. Budget truth instrumentation as a first-class deliverable — the estimation analogue of the FT640 data campaign.*

**Throughline for the team:** Items 1–2 make the **observable** part of the problem (angle + LOS-rate) as clean and honest as the hardware allows; Item 3 handles the **partially-observable** part (range under own-maneuver) without ever lying to guidance; Items 4–5 **prove** the filter is honest before it has authority. **None requires a GPU, a second band, a datalink, or any weapons-construction work** — all of it is classical estimation, microsecond-cheap on the RPi5, gated by an observability theorem we respect rather than fight. **The honest ceiling stands:** angle and LOS-rate we can estimate well; range and closing speed we cannot, on the geometry guidance wants — and the only real cure is a terminal active ranger or a second station, exactly as the guidance and autonomy briefings already concluded from their own directions.

---

**Files referenced (all verified present):**
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/imm.py` (body-frame IMM on `[az,el,az_rate,el_rate]` = reduced modified-polar state; fixed `R`; `ego_gate_radps` damper; `S` computed but not published)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/egomotion.py` (gyro de-rotation BASE + optional KLT residual; `EgoEstimate.quality` unused downstream; no online gyro scale/bias/time-offset)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/los.py` (strapdown LOS-rate reconstruction: raw pixel motion − ego rotation; cumulative roll handled exactly; the sign chain is the Tier-0 analytic test)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/looming.py` (τ = A/(dA/dt), confidence-gated; the only passive closing cue; Tier-2 observer input)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/geometry.py` (pinhole pixel↔bearing; Boson-640 intrinsics f_px≈2130)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/bearing_rate.py` (`a=N·Vc_sched·λ̇`; Vc scheduled NOT observed — the correct surrender to the FIM rank-deficiency)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/{pipeline,quad_sim}.py`, `seeker/seeker_sim.py` (closed-loop + truth-model sims = the Monte-Carlo NEES/NIS harness)
- `/Volumes/Samsa/ai_v2.0/03-fpv/docs/BLOCK03_THERMAL_INTERCEPTOR_DESIGN.md` (§3.2–§3.3 observability surrender; S0 turntable cam↔IMU sync + gyro scale/bias; soft-mount flagged critical)
- `/Volumes/Samsa/ai_v2.0/03-fpv/docs/GUIDANCE_DOCTRINE_BRIEFING.md`, `FIRE_AND_FORGET_AUTONOMY_BRIEFING.md` (the two prior briefings this builds beneath)
