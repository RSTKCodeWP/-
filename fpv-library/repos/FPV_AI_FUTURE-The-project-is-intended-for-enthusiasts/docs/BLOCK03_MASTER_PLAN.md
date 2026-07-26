> **[HISTORICAL]** — status as of 2026-07-19. 2026-06-19 consolidation of the three doctrine briefings, all three of which are now superseded. A record of the plan at that date.
>
> **`docs/CHECKPOINT.md` is the source of truth.** Where this document disagrees with it, CHECKPOINT wins.

<!-- Block-03 thermal counter-UAS interceptor — single master plan / TZ.
Consolidates the three doctrine briefings into staged work with gates and metrics.
Sources: docs/GUIDANCE_DOCTRINE_BRIEFING.md, docs/FIRE_AND_FORGET_AUTONOMY_BRIEFING.md, docs/BODY_AND_VV_BRIEFING.md
Authored 2026-06-19. Scope: software / controls / estimation / test only. -->

# BLOCK-03 THERMAL INTERCEPTOR — MASTER PLAN (TZ)

One sequenced plan that folds the three briefings (brain → autonomy → body/proof) into workstreams,
a phased roadmap, gates and metrics. **The guidance brain is already doctrinally correct; the work is
the perception front-half, the tracker association, the F&F autonomy/safety re-architecture, the honest
envelope, and the validation ladder.**

---

## 0. INVARIANTS (code-review law — violating any of these fails review)

1. **Range never touches the PN gain.** `Vc` stays scheduled (`SpeedPolicy`); any inverse-range observer feeds diagnostics / t_go / commit-gate / `Vc_eff` blend ONLY.
2. **AI never touches centroid / LOS / tracker.** A learned ensemble writes only to lock-quality and the engage-permission gate. Discrimination on top of a classical tracker+PN spine.
3. **Abort is a PASS, a wrong hit is a HARD FAIL.** Asymmetric scoring everywhere; default-deny on doubt.
4. **The IMM angular state `[az, el, az_rate, el_rate]` is modified-polar and correct.** Forbid a Cartesian 6-state rewrite (ill-conditioned toward unobservable range).
5. **Every command stays inside the body envelope:** ≤ 0.84 g lateral (θ_max 40°), inside FOV (±~20°), and corrections completed before the last ~1.0–1.4 s ("ten-tau" wall).
6. **Hard-mount the camera.** The soft-mount transfer function corrupts the most safety-critical signal (strapdown λ̇).
7. **Post-commit, acquiring a NEW track is FORBIDDEN.** F&F re-acquires only the SAME committed track within a hard-capped basket.

## 0.1 HONEST ENVELOPE (what we are building, stated plainly)

- **Targets:** non-/mildly-maneuvering (< ~0.28 g), near-head-on aspect, within the achievable forward capture cone.
- **Detection range (FT640 optics, Johnson): DETECT ~115–190 m, ID ~18–30 m.** "1.1 km" is struck from every budget.
- **Range/Vc are unobservable** (passive monocular, CRLB→∞). The bearing-rate-nuller is the correct surrender.
- **Mode:** LOBL (operator confirms + commits); post-launch is autonomous track-maintenance only.
- **Sensor ceiling:** single 8-bit AGC band — fundamentally weaker discrimination; mitigated, never solved, by kinematics + temporal + structure.

---

## 1. WORKSTREAMS

| # | Workstream | Owns | Primary files |
|---|---|---|---|
| WS-T | Tracker & association | lock persistence, anti-pull-off, basket, multi-track | `seeker/track.py`, `guidance/pipeline.py` |
| WS-P | Perception (look-down) | local-contrast, region-CFAR, MTI, motion gate | `seeker/detect.py`, `seeker/egomotion.py` |
| WS-G | Guidance honesty | t_go, g-budget, ten-tau, APN, N_eff | `guidance/bearing_rate.py`, `guidance/command_map.py`, `control/speed.py` |
| WS-E | Estimation | online gyro calib, S-covariance, NIS/NEES, inverse-range observer | `seeker/imm.py`, `seeker/egomotion.py` |
| WS-A | Autonomy & safety | acquire→confirm→commit→terminal→abort FSM, COMMIT_GATE, onboard abort authority | `betaflight_link/arming.py`, `failsafe.py`, `hwkill.py` |
| WS-C | Classifier/data | ensemble + abstain, FT640 data campaign | new `seeker/classify/`, dataset tooling |
| WS-S | Sensor roadmap | radiometric Y16 core, terminal ToF ranger | hardware spec + `sensor/` |
| WS-V | V&V | Monte-Carlo honesty, R3 HWIL, R5 captive, ladder | `guidance/closed_loop.py`, new `bench/hwil/`, `V_AND_V.md` |

---

## 2. PHASED ROADMAP (each phase ends on a gate)

### PHASE A — Software hardening (no new hardware) · gate **G-A**
Highest leverage-per-effort, all pure software, all testable in sim+bench.

- **A1 (WS-T) Handover basket + ACQUIRE state.** Replace the full-frame `acquisition_box` default in `SeekerGuidancePipeline` with a required tight angular basket; add an explicit ACQUIRE/SEARCH state with benign low-gain settling before full PN. *Brief-3 §3.6 — single highest-leverage software change.*
- **A2 (WS-T) Combined-cost association.** Replace pure nearest-neighbour in `track.py::_associate()` with `cost = w_k·kinematic + w_a·appearance + w_i·intensity-consistency`, with a single-term veto. Stops the lock walking onto a hotter intruder. *Brief-1 #1.*
- **A3 (WS-G) Guidance honesty.** Compute & carry `t_go` + source; couple `SpeedPolicy` to the g-budget (hold a lateral-g reserve); add the **ten-tau commit cutoff** → predicted-lead; make APN dimensionally consistent (gated); expose continuous `N_effective`; log the high-crossing abort ceiling as `achievable_g/3`.
- **A4 (WS-E) Estimator harden.** Publish innovation covariance **S** as lock-quality + covariance-sized search box; replace fixed `ego_gate`/48 px gate with a Mahalanobis/χ² gate; feed `EgoEstimate.quality` into R; add **NIS live "model-wrong" abort alarm**.
- **A5 (WS-V) Honest Monte-Carlo.** Add per-frame latency jitter + randomized `attitude_tau`, drag, mass, `target_step_jink_g` (≤0.84 g), bearing noise to `run_monte_carlo`.

**Gate G-A (R1+R2 with the honest envelope):** head-on/quartering **p90 miss < capture_radius** (N=3, 30 ms+Smith, jittered delay); **high-crossing aborts > 95 %**; **zero spurious-near-miss false positives**; Mode-B CPA ≈ Mode-A; subpixel centroid < 0.1 px; NEES release gate green.

### PHASE B — Look-down perception · gate **G-B**
- **B1 (WS-P)** MPCM local-contrast stage + region-adaptive CFAR (sky/horizon/ground, `k_horizon<k_sky<k_ground`) + directional median.
- **B2 (WS-P/E)** Image-domain ego-motion: ORB+RANSAC homography (gyro-only fallback on low inliers); warp+difference at Δt=1 and Δt=5; **intersect** → motion mask.
- **B3 (WS-P/T)** Multi-cue gate: candidate must be locally salient **and** moving. Multi-track manager + **trajectory-continuity** confirmation (the parallax/false-alarm backstop).

**Gate G-B:** look-down ground-clutter pass-through case in R2 — no lock-on-clutter; hoverer (near-zero motion) still held by long-interval+contrast; FA-rate under threshold over a held-out FT640 clip.

### PHASE C — F&F autonomy & safety re-architecture · gate **G-C**  *(prerequisite for any autonomy beyond bench)*
- **C1 (WS-A) Onboard abort authority — the hard prerequisite.** Re-architect `failsafe.py` (link-loss→ABORT) and `hwkill.py` (default-deny-unless-permit-beacon) from a **tether** into a **self-contained onboard abort authority**; F&F removes the beacon, so the round must arm and self-safe on its own evidence (lock-quality, geo/alt/profile, dwell), not on an external permit.
- **C2 (WS-A)** Decide/abort FSM `ACQUIRE→CONFIRM→COMMIT→TERMINAL→ABORT` + **COMMIT_GATE** (integrity-gated go/no-go re-validation, default-deny) + **signed decision journal**.
- **C3 (WS-A)** Add geo / alt / engagement-profile box fields to `ArmingAuthorization`; terminal target re-validation; SELF_SAFE on lost-lock/mis-class/dwell-exceeded.

**Gate G-C:** R0 — 100 % safety-FSM branch coverage + kill-chain invariant property tests; R4 props-off — the exact boolean in `V_AND_V.md §6`, every abort path disarms; F&F never arms without a confirmed same-track lock; **a logged refuse-to-fire** exists.

### PHASE D — HWIL + data + classifier · gate **G-D**
- **D1 (WS-V) R3 frame-injection HWIL** via the `FrameSource` seam: feed recorded/synthetic Y16 into the real RPi5 runtime, close the loop on real silicon. Gate: tracker == SIL reference; **p99 closed-loop latency < frame**; **measured latency ≤ R1 assumption** (back-propagates).
- **D2 (WS-C) FT640 data campaign** — self-collected, both geometries, hard-negatives (birds/clutter) over-represented, synthetic for geometry only, validate on held-out real.
- **D3 (WS-C) Ensemble classifier + abstain** — kinematic-tree + appearance-tree + tiny INT8 CNN on 32–48 px chip per confirmed track, every Nth frame → calibrated log-LR stacker → lock-quality + engage-permission, with a calibrated ABSTAIN band.

**Gate G-D:** R3 green; classifier ROC + abstain calibration on held-out real; drone-vs-bird AUC reported honestly (expect a residual gap).

### PHASE E — Sensor upgrades · gate **G-E**
- **E1 (WS-S)** Radiometric **Y16 16-bit core** (SWaP-neutral) — absolute CFAR path + frame stability; keep relative-contrast as fallback; confirm EAR-vs-ITAR + frame-rate ECCN before buy.
- **E2 (WS-S)** Single-point **ToF ranger**, terminal-only, behind a flag — real t_go/ZEM, dimensionally-valid APN, measured-decreasing-range commit; fused into IMM **only inside ENDGAME**, hysteretic.

**Gate G-E:** re-run R1–R3 with the new sensor; range observability index exercised; no terminal λ̇ spike from ranger fusion.

### PHASE F — Flight V&V ladder to first live intercept · gates **R5 → R6 → R7(F1) → R7(F2)**
- **R5 captive-carry** (seeker flies, no engagement auth): measure vibration spectrum / soft-mount transfer fn / real ego-motion; validate R3 against real recordings; harvest clutter/birds back into R1/R2.
- **R6 tethered props-on** (load-cell, both kill paths live): confirm real latency, λ̇-null on a real moving warm target under prop vibration, instant disarm under load.
- **R7 F1 non-kinetic** (inert/netted approach to standoff) → **F2 kinetic** (slow/non-jinking/near-head-on, surveyed footprint, external miss-distance instrumentation).

---

## 3. METRICS (the numbers each gate checks)

- Miss: **p90 < capture_radius**, p99 reported; capture volume = forward cone, not sphere.
- Abort: **high-crossing / over-g / lost-lock aborts > 95 %**; wrong-hit false-positives = **0**.
- Latency: **p99 closed-loop < one frame**; measured ≤ every software-rung assumption (auto-invalidate on violation).
- Perception: subpixel centroid < 0.1 px; FA-rate vs stars/clutter under threshold; threshold re-bases after FFC.
- Estimation: NEES within χ² bounds (release gate); NIS whiteness (live alarm); Q chi-square auto-tuned.
- Envelope: every commanded g ≤ 0.84; abort ceiling = `achievable_g/3` logged; no command ejects target from FOV.

## 4. EXECUTION ORDER (start here, do everything in this sequence)

1. **A1** handover basket + ACQUIRE  →  2. **A2** combined-cost association  →  3. **A3** guidance honesty
4. **A4** estimator harden  →  5. **A5** honest Monte-Carlo  →  **G-A**
6. **B1–B3** look-down perception  →  **G-B**
7. **C1** onboard abort authority  →  **C2–C3**  →  **G-C**
8. **D1** R3 HWIL  →  **D2** data  →  **D3** classifier  →  **G-D**
9. **E1** Y16 core  →  **E2** ToF  →  **G-E**
10. **R5 → R6 → R7(F1) → R7(F2)**

> Reality anchors the bottom rung. Every hardware-measured value back-propagates and re-tightens the model, so the one live shot is an audited consequence — not a hope. Every abort along the way is a pass.
