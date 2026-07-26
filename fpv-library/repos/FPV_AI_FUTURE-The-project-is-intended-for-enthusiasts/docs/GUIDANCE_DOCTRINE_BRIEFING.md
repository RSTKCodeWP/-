> **[SUPERSEDED]** — status as of 2026-07-19. 2026-06-19. Describes a classifier in the engage path and a pre-doctrine target. The learned classifier was DELETED 2026-07-11 and the machine no longer classifies target type at all. Kept as the record of how the guidance doctrine was reasoned.
>
> **`docs/CHECKPOINT.md` is the source of truth.** Where this document disagrees with it, CHECKPOINT wins.

<!-- Generated 2026-06-19 by a multi-agent study of published IR-seeker / missile guidance
doctrine, mapped onto this repo's seeker/guidance code. Scope: software (sense-and-guide) only. -->

# GUIDANCE ARCHITECTURE BRIEFING — Block-03 Thermal Counter-UAS Interceptor
## Adopting Published Seeker/Guidance Doctrine into Our Look-Down Tracking & Guidance Software

**Audience:** Block-03 engineering team · **Author:** Chief guidance architect · **Scope:** software only (sense-and-guide; no lethality/fuze engineering) · **Platform:** RPi5 CPU + FT640 8-bit AGC analog thermal (CVBS), passive monocular.

---

## 1. THE DOCTRINE IN ONE PAGE

**The core philosophy of every real seeker is the opposite of "recognize the object every frame."** Across five generations of hardware — spin-scan reticle, con-scan, rosette, two-colour, staring imaging IR — the throughline is one principle:

> **Discriminate on the features where a SMALL, COMPACT, KINEMATICALLY-COHERENT target differs from a LARGE, STRUCTURED, INCOHERENT background — never on "which pixel is hottest."**

Real seekers separate the problem into two decoupled halves and never let them bleed:

1. **Detection/discrimination** = multi-feature *gating* inside a *confined* angular window (size, contrast-vs-local-surround, spectral ratio, motion coherence, track persistence).
2. **Guidance** = *nulling the line-of-sight rotation rate* (Proportional Navigation) on an already-confirmed centroid — converting a good track into a collision triangle.

**Why this beats "YOLO classify every frame":**

| "Classify every frame" (per-frame recognition) | Track + PN + IRCCM doctrine (what we adopt) |
|---|---|
| Each frame is an independent decision; one bad frame = one bad lock. | A track integrates evidence over time; a single anomalous frame neither breaks nor steals the lock (M-of-N, log-likelihood score). |
| Picks the most "drone-looking" / brightest blob. Under look-down AGC, hot clutter outscores a small cool drone. | Picks the blob that is **kinematically coherent** after ego-motion compensation. World-fixed clutter is rejected because its apparent motion is fully explained by our own motion. |
| No notion of *where the target should be next* → no clutter rejection, no occlusion survival. | Innovation-covariance gate predicts where the target must appear; clutter outside the ellipse is rejected for free; occlusion is survived by coasting. |
| Needs a trained net + GPU; brittle to the FT640's per-frame AGC re-normalization. | Classical, CPU-only, **relative/local-contrast** features that survive AGC by construction. |
| Recognition gives you a label, not a **collision course**. | PN gives you `a = N·Vc·λ̇` — provably ZEM-optimal against a non-maneuvering target, needs only LOS-rate + closing speed. |

The reticle seekers teach this in hardware: a fine chopper turns a point target into high-frequency harmonics while leaving extended background nearly unmodulated — clutter rejection in the **spatial-frequency domain, by design**, not by brightness. Con-scan teaches the guidance corollary: *trust the kinematically-coherent modulated track, not the brightest pixel*. Our FT640 is a staring imaging seeker with none of these analog discriminants, so **we must rebuild every one of them in software**: morphology/local-contrast for the reticle's spatial high-pass, per-region CFAR for the IRST threshold, and our existing IMM for con-scan's kinematic coherence.

**One sentence to take to the team:** We are not building a drone *recognizer*; we are building a **coherence tracker that nulls LOS rate** — discrimination is multi-cue gating in a confined window, guidance is PN, and the two stay decoupled.

---

## 2. WHAT WE ADOPT — Prioritised Plan Mapped to Our Code

Our **guidance back-half is already doctrinally correct** and validated by the literature. Our **perception front-half and tracker association logic are the gaps.** Adoption items below are ordered by leverage-per-effort.

### Tier A — Highest leverage, defends the core look-down failure (do first)

**A1. Combined-cost association to replace pure nearest-neighbour.** `seeker/track.py :: _associate()`
- **What:** Replace min-pixel-distance scoring with `cost = w1·kinematic + w2·appearance + w3·intensity_consistency`. Veto a blob if any single term is grossly out of family *even when it is the nearest/brightest.*
- **Why:** Today a hotter building/vehicle/person entering the fixed 48 px gate **becomes the new nearest valid blob and the lock walks onto it** — `min_snr=2.0` actively *favours* the hotter intruder. This is the documented centroid/NN break-lock failure and is our #1 look-down risk.
- **Where:** Single function. The FSM/coast/reacquire/FFC machinery already around it is sound.

**A2. Local-contrast / region-aware background suppression front-end.** `seeker/detect.py`
- **What:** Add a Multiscale Patch-based Contrast Measure (MPCM) stage and make the existing percentile+k·MAD threshold **region-aware** (sky / horizon / ground zones with `k_horizon < k_sky < k_ground`), plus a directional row/column median to kill linear ground structure (roads, rooflines).
- **Why:** We already have white top-hat + relative MAD threshold (a CFAR cousin) — good — but it is **global**. In look-down the drone sits against the *ground zone*; a per-region SCR threshold and local-contrast scoring is the reticle/IRST lesson and survives the FT640 AGC (which destroys absolute radiometry).
- **Where:** Extend `detect_frame()` and `ThresholdState`; the relative-threshold philosophy is already there.

**A3. Dual-interval temporal-motion gate + image-domain ego-motion comp.** `seeker/egomotion.py` + `seeker/detect.py`
- **What:** Add ORB-keypoint + RANSAC **homography** registration (frame-to-frame) to complement the existing gyro/KLT; warp previous frame into current; difference at **two intervals** (Δt=1 *and* Δt=5) and **intersect** the thresholded masks. Require a candidate to be **both** locally salient **and** showing compensated motion before it enters the tracker.
- **Why:** Our ego-motion is **inertial-first** (gyro base, optional sparse-LK). The literature uses image-domain homography because it captures translation/parallax the gyro cannot and yields a residual-motion mask for free. Dual-interval intersection is the cheapest, highest-leverage anti-clutter/anti-parallax filter on a Pi.
- **Where:** New homography path in `egomotion.py` (fallback to gyro-only when inlier count is low); motion-mask gate in `detect.py`.

### Tier B — Hardens the tracker, completes the IRCCM stack

**B1. Mahalanobis/χ² innovation-covariance gate** replacing the fixed 48 px circle — wire `imm.py` covariance `S` into `track.py` so the gate tightens on straight flight (rejects distractors) and widens on maneuver. Retires the hand-tuned `reacquire_expansion_factor`.

**B2. Appearance/structure template + freeze-on-interference rule.** Keep a lightweight target template (size px, aspect, intensity variance, gray-level histogram-vs-local-background). Score candidates by match. **Mandatory discipline:** the moment a second strong blob merges into the gate or occlusion is suspected, **stop updating the template and velocity, coast, and require a positive template match to re-lock.** An unfrozen template adapts onto hot clutter within a few frames.

**B3. Temporal rise-time veto.** Track per-blob intensity history; down-weight/veto any blob whose brightness jumps sharply or exceeds the locked target's recent envelope (flare/AGC-bloom/glint signature) — relative to local frame stats, gated off during FFC.

**B4. Track-score lifecycle.** Replace raw consecutive-frame counters with an M-of-N + log-likelihood-ratio score for confirm/coast/delete. Gives guidance a calibrated **lock-quality** signal.

**B5. Drone-vs-bird kinematic classifier** over a ~3 s (~100-frame) IMM track window: trajectory smoothness, turn rate, lateral-accel bound, velocity-fluctuation variance, heading jitter. Start with hand-crafted features + gradient-boosted trees (LightGBM-class); bi-LSTM is the upgrade path. Bird = irregular flapping jitter + sharp turns; rotary drone = smooth, bank/turn-radius-constrained, steady speed.

### Tier C — Guidance-law refinements (back-half is already correct; these are upgrades it leaves on the table)

Our `guidance/bearing_rate.py` **is** True PN (`a = N·Vc_sched·λ̇`, separate az/el, N=3), honestly relabeled as a bearing-rate nuller because Vc is *scheduled, not observed*. The literature validates every choice (N≤3 under >25 ms delay, pursuit-blend on low `tau_confidence`, high-crossing abort). Upgrades:

**C1. Compute and carry `t_go` explicitly.** `t_go = tau` when `tau_confidence` high, else `range_assumed/Vc_sched`. Unlocks ZEM shaping, the correct APN coefficient, and endgame scheduling. Add `t_go_s` + `t_go_source` to `GuidanceCommand`.

**C2. Make the APN term dimensionally consistent instead of hard-zeroing it.** `apn_active` currently logs `True` with **zero effect** because the team (correctly) refused a range-blind term. But `Vc_sched` already carries the same range-equivalence: estimate `a_T ≈ Vc_sched · d(λ)/dt²`, add `(N/2)·a_T`, keep the existing strict gate (IMM `maneuver_detected` AND `mode_prob ≥ threshold` AND `apn_accel_cap_mps2` clamp). Re-enables maneuver compensation *honestly*.

**C3. Confidence-blend the closing speed itself.** Replace binary `Vc_override/Vc_sched` with `Vc_eff = w·Vc_loom + (1−w)·Vc_sched`, `w = tau_confidence`. Trustworthy looming sharpens the gain; always falls back to the scheduled floor.

**C4. Reframe the pursuit↔BRN blend as a continuous effective-N slide.** Pure pursuit ≈ N′=1, PN = N·Vm/Vc. Expose `N_effective = blend·N + (1−blend)·1` (the field already exists — currently just echoes `cfg.N`) so the blend reads as "how much lead are we applying" and the lag-robustness argument applies continuously.

**C5. Annotate the high-crossing ROE abort with N′ theory in-code.** A crosser drives required-g toward the unbounded-terminal-acceleration regime (N′≤2). The abort is the *physically correct* response, not just a safety convenience — annotate so reviewers trust it.

---

## 3. LOOK-DOWN PERCEPTION PIPELINE (the converged recipe for a small UAV on hot ground)

This is the front-half we are missing. A **CPU-only cascade**, ordered by execution:

1. **Ego-motion compensation (image-domain).** ORB keypoints in frame *t* and *t−k* → match → RANSAC homography (RANSAC rejects the moving target as an outlier) → warp historical frame into *t* → build a **valid-region mask** for warped borders. **Fallback to gyro-only** when inlier count / reprojection error fails (textureless night sky, repetitive scene). Cascade short homographies by matrix multiply for the long interval to stay O(1).

2. **Background suppression on the current frame.** White top-hat (have it) **+ MPCM local-contrast** so a small drone pops relative to its *local surround* and large hot regions (roads, roofs, sunlit walls) flatten. **Region-adaptive**: segment sky / horizon / ground, separate background model + CFAR threshold per zone (the interceptor is *above* the target, so work the ground zone hard).

3. **Motion extraction (dual-interval).** Difference compensated frames at **Δt=1** (fast targets, low threshold) and **Δt=5** (slow-target accumulation, strict threshold + morphological opening), then **INTERSECT**. Closing on the fused mask.

4. **Multi-cue fusion by gating.** A candidate survives only if it is **both** locally salient (contrast map) **AND** moving (intersected motion mask). Treat motion as a *soft spatial attention weight* over contrast candidates — not an independent detector. When one cue fades (drone crosses a hot road, contrast vanishes), the other carries it.

5. **Trajectory-continuity confirmation (the primary false-alarm killer).** Feed survivors to the IMM/Kalman as a Long-Term-Trajectory-Continuity gate (M-of-N + plausibility). Only a continuous, kinematically valid track over N frames is declared a target. **This is what separates coherently-translating real targets from spatially-anchored parallax residuals** — the #1 look-down false-alarm source, which homography *mitigates but cannot eliminate* on a 3D urban scene.

6. **Classification (once a stable track exists).** ~3 s kinematic-signature window → drone vs bird/vehicle/person (Item B5).

**Hard caveats baked into the design:**
- **Parallax is never solved by homography alone** — depth (buildings, poles, relief) leaves residuals that mimic targets. Trajectory continuity is the backstop, not the homography.
- **Hovering/slow drones produce near-zero compensated motion** and can be erased with the background — the *long-interval difference + local-contrast cue* must carry these; pure-MTI gating alone misses a hoverer.
- **AGC makes intensity registration noisy** — register on **structure/gradient, not raw gray levels.**
- **Point-target ISTD breaks as the drone resolves into an extended blob near impact** — hand off to the endgame pipeline (Section 4).

---

## 4. TERMINAL ENDGAME ARCHITECTURE (last seconds / large subtense / high closing speed)

We own all the primitives (`looming.py` saturation flag, `imm.py` propagatable state, `track.py` `PREDICTIVE_TRACK` coast) but have **no explicit endgame mode.** Everything sequences off **`t_go` and ZEM, not frame count.**

**Trigger:** add an explicit `ENDGAME` state to the FSM, entered when **target subtense** (`blob_area_px` / FOV fraction) crosses a threshold **AND/OR** `looming.saturation_factor` collapses `tau_confidence → 0`. That saturation flag already exists and is the natural, free trigger — today it only blends to pure pursuit; it should *also* freeze the aimpoint and arm pure-lead.

**On entering ENDGAME, three things change in lockstep:**

1. **Aimpoint switch — stability over correctness.** The intensity-weighted centroid (excellent for a 1–3 px point) **wanders** once the target fills the frame (centroid migrates to the hottest motor/battery sub-region; shape changes with aspect; scintillation moves it frame-to-frame). This is the documented **spin-scan center-null analogue** — a *real* failure mode. **Switch from whole-blob centroid to a stabilized extended-target aimpoint**: low-pass/hold the centroid, or lock a persistent sub-feature (hottest sub-region or fixed geometric offset). A jittery aimpoint injects high-frequency noise into `λ̇` exactly when `N·Vc` gain is highest — **aimpoint stability beats aimpoint correctness** in the last fraction of a second.

2. **Guidance handover — measured-LOS → predicted-lead fly-out.** When measured LOS rate is noise-dominated and the target may overfill or exit the FOV, **stop closed-loop homing and fly a predicted-intercept trajectory propagated from the last high-confidence IMM state** (reuse `PREDICTIVE_TRACK` machinery). With our >25 ms delay and large endgame subtense, delay-induced miss worsens — **lean on prediction, never on cranking N up.** Handover must be **late and hysteretic** (it is only correct if the last track state was high-confidence and the target does not hard-maneuver inside the coast window).

3. **Sequence off `t_go`/ZEM.** Compute `t_go`, expose ZEM, gate the aimpoint switch and the homing→pure-lead handover on `t_go` — a small addition to `pipeline.py`. Make every threshold hysteretic so the switch cannot **chatter and inject a transient `λ̇` spike at minimum `t_go`** (the worst possible moment).

**Range/Vc honesty + the principled upgrade path:** We are passive-monocular and **cannot observe Vc or range** without own-maneuver parallax (documented in `bearing_rate.py`). Keep Vc scheduled for guidance. **If a timed effect or true hit-to-kill is ever required**, the literature's answer is **one short-range active ranger fused only in the terminal window** — ToF/lidar (<100 m, FOV/weather/eye-safety limited) or a small Ka-band mmW module (range+Vc, but power/weight/cost-heavy). **Angle channel steers, range channel triggers.** This is the documented terminal-sensor fusion architecture and the only principled way to close our range-observability gap.

**Effect/proximity logic (concept level only, per the sense-only boundary):** if an effect is ever in scope, the published decision logic is arm/trigger off **measured decreasing range + velocity-scheduled detection-to-effect delay + aspect** — we adopt the *decision logic*, never warhead/fuze hardware.

**Required Gate-L sim cases before any hardware:** (a) target-fills-frame centroid wander, (b) target exits FOV at small `t_go`, (c) look-down ground-clutter pass-through. Validate the aimpoint switch and pure-lead handover in sim first.

---

## 5. WHAT DOES NOT TRANSFER (honest list) — and our substitutes

| Military-seeker assumption | Why it fails for us | Our substitute |
|---|---|---|
| **Two-colour / multi-band spectral discrimination** (Stinger IR+UV, Igla-S/Verba multi-channel) — the *most powerful* flare/decoy/clutter discriminant. | FT640 is a **single 8-bit AGC analog channel**. No second band, period. | Over-invest in **kinematic (LOS-rate coherence after ego-comp) + temporal (rise-time) + appearance/structure** discrimination, all of which one thermal channel fully supports. Emulate spectral *intensity-invariance* with AGC-normalized relative/contrast features. **Accept this is fundamentally weaker** against a hot drone over hot clutter at low SNR. |
| **Calibrated absolute radiometry** (raw-DN CFAR, fixed thresholds). | AGC + 8-bit quantization **destroy absolute intensity** frame-to-frame; FFC distorts it further. | **Everything relative/local-contrast.** Per-region SCR, local-contrast measures, structure/gradient registration. Gate temporal features during FFC. |
| **Sky-background (look-UP) optimization** — spin-scan AM reticle. | We operate **look-DOWN against ground clutter** — the exact regime where AM/brightest-pixel seekers break (they chase the clutter). | Transfer the *philosophy* (multi-gate, FM/positional, size-filtered), **not** the legacy AM-reticle mechanism. |
| **Off-board midcourse cueing** (Coyote/Anvil hand the seeker a tiny acquisition basket above the horizon). | We may have **no off-board radar/EO/IR fusion** to shrink the search window. | Implement **cue-then-confine as a software prior**: horizon/sky-mask + predicted angular basket from midcourse, so the terminal tracker never searches the full cluttered frame. Pure software; no extra hardware. |
| **N = 3–5 with near-zero guidance lag.** | Our **>25 ms sensor+loop delay** means raising N amplifies LOS-rate noise and can **diverge**. | **Default N ≤ 3.** Only consider a brief endgame N-bump gated on *empirically measured* delay (B1) and `λ̇` SNR. Lean on prediction, not gain. |
| **APN/ZEM optimality** (assumes linearized constant-Vc, known step-maneuver target accel in metric units). | Passive monocular observes **neither range nor target accel** directly; a small jinking quad violates the step assumption. | APN re-enable rests on `Vc_sched` as an *explicitly-labeled stand-in* (Item C2); keep the strict IMM maneuver gate + accel cap. Never present scheduled Vc as measured. |
| **Looming τ as a reliable `t_go`.** | The only passive `t_go` source **degenerates exactly at acquisition (1–3 px), crossing (dA/dt→0 ⇒ τ→∞), and impact (FOV saturation)** — precisely when it is most tempting. | Fall back to scheduled `t_go` in those regimes; `tau_confidence`-weight every use. |
| **Heavy PDA/JPDA + full IMM bank + per-pixel ML.** | RPi5 CPU budget vs **>25 ms latency** plus an N-frame confirmation window — every added perception ms worsens the miss-distance delay term. | **Start with combined-cost hard-NN + ellipsoidal gate** before full PDA. Favour cheap separable filters (max-median, small-SE top-hat, ORB). Soften toward PDA-style soft update only once IMM covariance is wired and budget allows. |

**Two convergent edge cases no transferable technique fully solves**, flagged honestly: (1) **birds vs small drones** can share size, shape *and* kinematics (hovering drone vs soaring bird; jinking drone vs darting bird) — compactness + CFAR alone will not separate them; needs the multi-second kinematic classifier *and* trajectory-plausibility gating, and still expect a sim-to-real gap (classifiers are validated on synthetic/radar data, not airborne look-down thermal). (2) **Parallax in 3D urban look-down** — mitigated, never solved.

---

## 6. SHORTLIST — Top 5 Highest-Leverage Builds, Ordered

1. **Combined-cost association in `track.py::_associate()`** (kinematic + appearance + intensity-consistency, with veto). *Single highest-value change against the hot-clutter pull-off that is our #1 look-down failure. One function. Pure software.*

2. **Look-down perception front-end in `detect.py`: MPCM local-contrast + region-adaptive (sky/horizon/ground) CFAR + directional median.** *Defeats the FT640 AGC and flattens roads/roofs; the reticle/IRST lesson made concrete. CPU-only.*

3. **Dual-interval temporal-motion gate + ORB/RANSAC image-domain ego-motion comp** (`egomotion.py` + `detect.py`, gyro-only fallback). *Cheapest, highest-leverage anti-clutter/anti-parallax filter; gives the motion mask that makes Item 1's kinematic term real. Trajectory-continuity gate on the existing IMM is the false-alarm backstop.*

4. **Explicit ENDGAME mode** (`track.py` FSM + `pipeline.py`): subtense/saturation trigger → **stabilized extended-target aimpoint** + **predicted-lead fly-out from last IMM state**, all sequenced off `t_go`, hysteretic. *Closes the documented center-null failure and the FOV-overfill miss. Reuses code we already own.*

5. **Guidance-law honesty upgrades** (`bearing_rate.py`): compute `t_go` (C1), make APN dimensionally consistent instead of zero-effect (C2), `Vc_eff` confidence-blend (C3), continuous `N_effective` slide (C4). *Low-risk, turns three already-present-but-inert fields into working physics and makes the collision-triangle state observable to operators and Gate-L sims.*

**Throughline for the team:** Items 1–3 build the **coherence-tracker front-half we are missing**; Item 4 fixes the **terminal failure mode** with code we already have; Item 5 **completes the guidance back-half** that is already doctrinally correct. None requires a GPU, a second spectral band, or weapons-construction work — all of it is **classical, CPU-only, relative-feature processing that fits the RPi5 + FT640 reality.**

---

**Files referenced (all verified present):**
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/bearing_rate.py` (True PN; `apn_active` inert; `blend_factor=tau_confidence`; `N_effective` field present)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/pipeline.py` (`SeekerGuidancePipeline.step()`; no `t_go`/endgame)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/track.py` (pure-NN, fixed `max_gate_px=48`, `min_snr=2.0`; FSM with `PREDICTIVE_TRACK`/`REACQUIRE`/FFC coast)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/detect.py` (top-hat + percentile+k·MAD relative threshold; **global**, no region/local-contrast/motion gate)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/looming.py` (`saturation_factor` → `tau_confidence` collapse = endgame trigger)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/egomotion.py` (gyro-first + optional sparse-LK; no image-domain homography)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/imm.py` (propagatable IMM state for trajectory gate + predicted-lead)
- `/Volumes/Samsa/ai_v2.0/03-fpv/docs/BLOCK03_THERMAL_INTERCEPTOR_DESIGN.md` (design baseline)
