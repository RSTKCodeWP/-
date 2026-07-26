> **[SUPERSEDED]** — status as of 2026-07-19. 2026-06-19. Predates the HUMAN AUTHORITY doctrine (2026-07-10): the operator confirms the target with two presses, and no code or hardware permits or denies a strike on its own judgement. Kept as the record of the autonomy study.
>
> **`docs/CHECKPOINT.md` is the source of truth.** Where this document disagrees with it, CHECKPOINT wins.

<!-- Generated 2026-06-19 by a multi-agent study of published fire-and-forget weapon autonomy,
AI-in-seekers, night thermal classification, and autonomous-weapon safety/ROE doctrine, mapped
onto this repo's seeker/guidance/safety code. Scope: software (sense-and-decide) only — NO
warhead/propellant/fuze-lethality engineering, NO uplift toward building a munition. -->

# FIRE-AND-FORGET AUTONOMY BRIEFING — Block-03 Thermal Counter-UAS Interceptor
## The Onboard Autonomy, AI-Discrimination, Night-Classification & Autonomous-Safety Doctrine for a No-Datalink, Operator-Committed Night Interceptor

**Audience:** Block-03 engineering team · **Author:** Chief autonomy architect · **Scope:** software only (sense-and-decide; no lethality/fuze/propellant engineering, no real-munition uplift) · **Platform:** RPi5 CPU + FT640 8-bit AGC analog thermal (CVBS), passive monocular, body-fixed seeker.

> **Read `GUIDANCE_DOCTRINE_BRIEFING.md` first.** This document **builds on it and does not repeat it.** That briefing already settled: the coherence-tracker philosophy (track + PN, never per-frame recognition), the decoupling of detection from guidance, the look-down perception cascade (A1–A3, B1–B5, C1–C5), the terminal endgame (centroid-wander, predicted-lead handover), and the "what does not transfer" list (single-band, AGC, no range observability). **Everything here sits ABOVE that:** the autonomy state machine that wraps the tracker+PN, the precise slot for a learned discrimination layer, the honest night-classification verdict and data plan, and the autonomous decide/abort/ROE safety spine that makes "fire-and-forget" not be "fire-and-hope."

---

## 0. THE ONE-PAGE THESIS

Removing the post-launch datalink does **not** make the round smarter — it makes the **operator's COMMIT the last human act** and forces every decision after it onboard. The published reference weapons (Javelin, Spike, Hellfire, NLAW, Brimstone) teach one skeleton: **fire-and-forget = "no external intervention after launch," realised as a small, deterministic finite-state machine that holds ONE pre-confirmed track through a coast and a maneuver — not as onboard target recognition.**

Three load-bearing consequences for us:

1. **We are, and must stay, a LOBL (lock-on-before-launch) system — the Javelin pattern.** The operator builds and confirms the track; that confirmed track is what we commit and prosecute. Post-launch autonomy is **track-maintenance only**: re-acquire the *same* committed track after a blink, never acquire a *new* one. True LOAL (autonomous target *selection* in a basket) crosses the positive-ID line our safety spine deliberately holds — we reject it.

2. **AI belongs in exactly one slot: a learned DISCRIMINATION GATE on top of the classical tracker+PN — never the tracker, never the aimpoint, never the guidance.** It writes only to lock-quality and the engage-permission gate, and it must be allowed to **ABSTAIN**. With no human to catch a bad call, a calibrated "refuse on doubt" is the single most valuable thing AI buys us. It buys us essentially **nothing** in raw target ID on one 8-bit band.

3. **The genuine gap is not perception — it is the autonomous COMMIT/ABORT brain.** Our guidance back-half is doctrinally done (prior briefing); our perception front-half has a plan (prior briefing). What is missing is the small, *verified* safety monitor that decides whether the PN loop is even *allowed* to drive toward impact, re-validates the target at a late commit gate, and self-safes by default on any doubt — and that the current `failsafe.py`/`hwkill.py` **link/beacon tether directly contradicts a no-datalink round** and must be re-architected to an onboard self-contained abort authority before this is a fire-and-forget system at all.

**Honest bottom line up front:** on a single-band 8-bit passive thermal seeker, autonomy buys us **survivability** ("shoot and relocate," the round holds its one track alone) and a **disciplined bias toward aborting on doubt** — both real and valuable. It does **not** buy us discrimination certainty, autonomous target selection, or any free lunch around the missing second spectral band and the missing range observability. Anyone who claims "fire-and-forget AI picks the right target by itself" on this hardware is wrong, and saying so is part of the job.

---

## 1. FIRE-AND-FORGET ARCHITECTURE — The Onboard Autonomy State Machine

### 1.1 LOBL vs LOAL — settled: we are LOBL, and that is correct

| | **LOBL** (lock-on-before-launch) | **LOAL** (lock-on-after-launch) |
|---|---|---|
| Who closes acquisition, when | Seeker locks **before** launch; missile is a track-holder afterward | Missile flies inertial midcourse to a **basket**, then activates and **acquires autonomously** near the target |
| Canonical weapons | **Javelin** (infantry-class F&F) | Spike, Hellfire, JASSM, Brimstone |
| Why it exists | Operator has positive ID and LOS | Beats seeker range/FOV limits or obstructed launch geometry |
| **For us** | **This is our pattern.** Operator builds track on the LAUNCH console, confirms, commits | **Rejected.** "Acquire autonomously in a basket" = autonomous target *selection* = crosses our positive-ID/ROE line |

The published definition of fire-and-forget — *"no further external intervention after launch"* — is **exactly the no-datalink constraint the task imposes**, and the infantry-class realisation (Javelin) is **LOBL-only**: the gunner adjusts tracking gates into a box around the target and a crosshair on center-of-mass; when the imaging-IR seeker achieves track the gates+crosshair go **solid = lock confirmed**; *then* the round fires. **Our console-locks-then-commits flow is a faithful instance of this.** State it as the doctrinal anchor rather than leaving it implicit.

**The one quantitative idea worth importing from LOAL — the re-acquisition basket — without importing LOAL's target-selection.** LOAL math: propagate aimpoint position uncertainty through the inertial-coast interval, build a 2D search box by extending the predicted point by accumulated navigation+track error, search only that box, collapse to a tight gate on lock. We apply this to **re-acquiring the SAME committed track after a blink** (FFC shutter, brief occlusion), never to finding a new one.

### 1.2 The five-state onboard autonomy machine

This is the **missing organizing spine** — it labels and sequences machinery the repo already owns (`lock.py` FSM, `imm.py`, `looming.py`, `bearing_rate.py`, `arming.py`), threading them into one explicit, testable sequence.

```
 ┌──────────┐  operator builds & holds track (console)
 │ ACQUIRE  │  pre-launch · operator-assisted · seeker building track
 └────┬─────┘  (maps to lock.py: NO_TARGET → CANDIDATE → LOCKED)
      │ stable LOCKED ≥ N frames  AND  ID-grade pixels  AND  kinematics-consistent
 ┌────▼─────┐
 │ CONFIRM  │  commit PRECONDITION  (= Javelin "gates + crosshair go solid")
 └────┬─────┘  the learned discrimination gate + track-score (B4) must pass here
      │ operator dual-key (ARM + FIRE)  AND  inverted verifier pass
 ┌────▼─────┐  ── THE LAST HUMAN ACT ──
 │ COMMIT   │  lock & target template FROZEN at this instant · Ed25519 authorization signed
 └────┬─────┘  (maps to arming.py committed-authorization → ARMED_IDLE)
      │ autonomous from here · no datalink · no man-in-loop
 ┌────▼─────┐
 │ TERMINAL │  body-frame bearing-rate homing · FOV-constrained · endgame aimpoint switch
 └────┬─────┘  (prior briefing §4 endgame; PN sees CLASSICAL centroid only)
      │ impact  OR  any abort condition
 ┌────▼─────┐  reachable from EVERY state
 │  ABORT   │  → SELF_SAFE: break lock · level · fly-to-surveyed-ditch · independent HW-kill · LATCHED
 └──────────┘
```

**The intelligence is in robust track maintenance and gated transitions — not target recognition.** Every reference weapon runs an explicit go/no-go sequence of exactly this shape (Javelin: cooldown→SEEK→gates frame target→solid=lock→launch; the LOAL patent family: midcourse→start-range→acquire→match→lock→track). No new files are required for the skeleton; this is labeling and sequencing.

### 1.3 Two hard constraints the prior briefing did not name

**(a) Strapdown narrow-FOV "target swings out of frame during the commit maneuver."** Because our Boson is **body-fixed (no gimbal)**, the body must rotate to apply lateral g, and the seeker rotates with it — a published, named failure mode for strapdown seekers. A target forcing a large commit maneuver can be swung **out of the FOV** by the maneuver itself. The literature's fix is **FOV-constrained / look-angle-limited guidance**: cap commanded look angle so the rotation needed to apply g cannot eject the target from frame. This is a **hard new constraint on TERMINAL**, complementing (not replacing) the energy/g clamp the prior briefing already noted, and it is the *autonomy-specific* reason to keep boresight near the velocity vector.

**(b) The re-acquisition basket must be covariance-sized AND hard-capped against lock-theft.** Re-derive the REACQUIRE search crop from **IMM covariance `S` and time-since-lock** (the LOAL basket rule), retiring the hand-tuned `reacquire_expansion_factor` (also flagged as B1 in the prior briefing). Add a **geometric hard cap**: the basket may never grow large enough to admit a second strong blob. If it would, declare **HARD_LOST and ABORT** rather than risk acquiring a different object. This makes the anti-lock-theft invariant geometric and closes the lock-theft hole.

### 1.4 Mapping to the LAUNCH console + Ed25519 handoff

The repo already implements the right primitives — the autonomy machine slots onto them:

- **ACQUIRE/CONFIRM** = the operator's work on the LAUNCH console (build track box, confirm). CONFIRM's precondition is the existing **stable-LOCKED + ID-grade-pixel + kinematics gate**.
- **COMMIT** = the existing `ArmingAuthorization` flow in `arming.py`: the FIRE keypress is **data inside the dual-signed authorization** (`keypress_recorded` + `keypress_ts` within `[issued_at_s, expires_at_s]`), verifier-passed, non-synthetic for a live engagement. This is the cryptographic realisation of "the last human act." The lock template and IMM state are frozen at this instant.
- **TERMINAL** = `AI_ACTIVE` in `arming.py` driving the body-frame bearing-rate nuller, now wrapped in FOV-constrained commanded tilt.
- **ABORT** = `arming.py::abort()` → sticky `KILLED`, plus the independent HW-kill. **But the *trigger* for abort must move onboard (Section 4) — today it is tethered to a link/beacon that fire-and-forget removes.**

**Adopt (Section 1):**
1. Make the 5-state machine explicit in `gates/lock.py` + `guidance/pipeline.py`: ACQUIRE→CONFIRM→COMMIT→TERMINAL→ABORT, ABORT reachable from any state and latched. No new files for the skeleton.
2. Re-derive REACQUIRE from IMM `S` + time-since-lock with a hard anti-second-blob cap (→ HARD_LOST/ABORT if violated).
3. Add a FOV/look-angle clamp on commanded tilt in TERMINAL (strapdown-seeker FOV-constrained guidance).
4. Treat any post-COMMIT seeker blink as a **bounded inertial-coast-then-reacquire-the-SAME-track** event (gyro+IMM `PREDICTIVE_TRACK`, ~300–500 ms coast / 1.5 s reacquire ladder — values already in `lock.py`), re-lock REQUIRES a positive frozen-template match, **forbid acquiring any new track post-COMMIT.**
5. Document the LOBL anchor and the autonomy boundary in `BLOCK03_THERMAL_INTERCEPTOR_DESIGN.md`: we are a Javelin-class LOBL F&F system; the operator's final authority is at COMMIT; post-launch autonomy is track-maintenance-only.

---

## 2. WHERE AI BELONGS (AND WHERE IT DOES NOT)

### 2.1 The single legitimate slot

The prior briefing already names a kinematic classifier as item **B5** ("start with trees"). This dimension **upgrades B5 from a single classifier to a calibrated, decision-level ENSEMBLE with an explicit reject option** — which is precisely what fire-and-forget needs, because the autonomy must be able to **refuse** rather than force a bad engage with no human to catch it.

**Hard architectural rule, enforced in code:**
> The learned layer writes ONLY to (a) lock-quality / track-score (B4) and (b) the autonomous engage-permission gate. **It never modifies the centroid/aimpoint or the LOS rate. PN sees the classical centroid exclusively.** Discrimination and guidance stay decoupled (the prior briefing's throughline).

### 2.2 The CPU-only ensemble — a reject-early cascade keyed off the FSM

```
 Stage 0  EVERY frame · classical · (prior briefing front-end)        NO AI
          top-hat + region-CFAR + dual-interval motion gate
          → combined-cost NN association + IMM gate → confirmed track
            │
 Stage 1  per confirmed track · ~2 Hz · KINEMATIC EXPERT              cheap
          hand-crafted features over rolling ~3 s IMM window
          (turn rate, max lateral accel, speed variance, heading
          jitter, smoothness) → gradient-boosted trees (LightGBM-class)
          sub-ms · APPEARANCE-INVARIANT → the ensemble's robustness anchor
            │
 Stage 2  per confirmed track · ~2–5 Hz · APPEARANCE EXPERT           cheap
          features on the tracker's chip (subtense, aspect, intensity
          variance, local SCR, top-hat peak ratio) → small tree/logistic
            │
 Stage 3  per confirmed track ONLY · every Nth frame · SMALL CNN      the one
          32–48 px thermal chip · 2–4 conv-block / MobileNet-tiny      expensive
          class · INT8-quantized · CLASSIFIES the chip the tracker     member
          already centered — it does NOT detect or localize
            │
 FUSION   calibrated stacker (logistic / weighted log-LR) →
          one drone-confidence  +  one OOD/novelty score
          → feeds track lifecycle (B4) and the engage-permission gate
          → with an explicit ABSTAIN band (Section 2.4)
```

**Why this fits the RPi5 CPU budget honestly.** Tiny INT8 nets on a Pi 5 with active cooling are affordable — published numbers: MobileNetV2-INT8 ~25 ms, YOLOv4-Tiny-INT8 ~28 ms, purpose-built tiny classifiers ~9.2 ms; PTQ costs ~2% accuracy, QAT recovers most. The CNN fits **only because** it runs on a **32–48 px chip**, on the **1–3 live confirmed tracks**, **every Nth frame** — not full-frame, not every frame. A naive full-frame per-frame CNN **busts the >25 ms loop budget and worsens the guidance-delay miss term** (prior briefing §5).

### 2.3 Why decision-level fusion, not pixel/feature fusion

Three **heterogeneous, loosely-independent** experts (kinematics / appearance / small-CNN) combined by **late** fusion, with the **kinematic expert holding veto authority** because it is sensor-appearance-invariant and survives the AGC domain gap that bites the CNN. Explainability of a CNN vote is genuinely weak; the hand-crafted experts must carry the veto and the CNN is **one vote among heterogeneous experts, never the decider.**

### 2.4 The ABSTAIN band — the fire-and-forget safety substitute for the absent human

Calibrate the fused score (temperature-scaling) and add a novelty/OOD score. Then:
- **Abstain band** → force **coast-and-reconfirm**, not engage.
- **High-confidence but low track-evidence** → treat as suspicious; do **not** auto-engage.

This matters because **the dangerous DNN failure in a no-human loop is silent OVERCONFIDENCE**: DNNs assign high confidence to out-of-distribution inputs (decoys, novel airframes, unseen scenes) and can be pushed there naturally or adversarially. Without calibration + abstain, the ensemble will **confidently authorize the wrong engagement** — the worst possible failure with no human in the loop.

### 2.5 The explicit "do NOT put AI here" list

| Zone | Why AI must not go here |
|---|---|
| **The tracker / the box you fly on** | A learned detector picks the most "drone-looking" blob; under look-down AGC that is often hot clutter, and one bad frame = one bad lock. The classical tracker's evidence integration is strictly safer. AI is a **track-level gate only.** |
| **The aimpoint / centroid / LOS rate** | PN must see the classical centroid. A learned aimpoint injects per-frame brittleness into `λ̇` exactly where `N·Vc` gain is highest. |
| **Target SELECTION (acquiring a new target post-launch)** | This is LOAL autonomous selection — crosses the positive-ID/ROE line. The human selects at COMMIT; the round only prosecutes that one track. |
| **Range/Vc estimation** | We are passive-monocular; no learned net manufactures range observability that the optics do not contain (prior briefing §4/§5). |
| **Multi-band/RGB+IR accuracy budgeting** | Most published ATR "breakthroughs" ride on RGB+IR or multi-band fusion. Those gains do **not** transfer to one 8-bit AGC channel (fused MOTA ~91% vs thermal-only ~86% — we are on the lower line). Do not plan for accuracy we cannot reach. |
| **Event-camera / SNN / neuromorphic** | A different **sensor** (DVS, µs latency, no blur) and stack — not retrofittable to the FT640 CVBS stream. Honest future-block option, not a Block-03 deliverable. |
| **Rotor micro-Doppler "drone signature"** | The radar community's best discriminant — 50–100 Hz blade modulation — **aliases away** at CVBS frame rates and is unobservable on our imager (Section 3.4). |

**Adopt (Section 2):** reframe B5 as the decision-level ensemble; implement as the reject-early cascade keyed off the FSM; wire the fused score to B4 + engage-permission **only**; add the calibrated abstain/OOD band; train on AGC-survivable relative-contrast chips with heavy domain randomization + synthetic-IR/CycleGAN bootstrap but **validate only on held-out real look-down 8-bit thermal**; INT8-quantize (PTQ→QAT) and budget per-track/every-Nth-frame; add a **Gate-L sim case measuring real amortized loop latency with the ensemble live**; log the single-band ceiling as a hard limit in the design doc.

---

## 3. NIGHT CLASSIFICATION — The Honest Verdict, Feature Set, and Data Plan

### 3.1 The honest verdict on "night silhouette is simple": it is FALSE as stated for our hardware

The claim silently assumes (a) the target is **resolved** (>~8–13 px), (b) you have shape/aspect, and (c) calibrated contrast. **On an FT640 8-bit AGC single-band seeker, none of those hold for most of an engagement.** Two reasons:

**(a) Resolution governs everything (Johnson/NVESD criteria).** ~2 px across the critical dimension = DETECT, ~8 px = RECOGNIZE (drone-vs-bird class), ~13 px = IDENTIFY (fixed-wing vs rotary type), at P50 — and **automatic ATR needs ~1.5–2× more** than a trained human. For a 0.3–0.5 m drone on an FT640-class LWIR seeker with a modest lens, those pixel counts only exist in the **last few hundred meters**. Published reference: a FLIR-Boson set caps useful drone range at ~200 m; a Lepton-on-Pi study reached only ~100 m. **For most of an intercept the target is a 1–3 px blob with NO usable silhouette.** The silhouette-classification problem is unsolvable there not because the classifier is weak but because **the information is not on the sensor.**

**(b) Sky (look-up) vs ground (look-down) are different problems.** Look-UP against cold sky is the **easy, high-contrast** geometry — and it is what most flashy public numbers (~92–95% drone-vs-bird) are measured on. We operate **look-DOWN against hot ground**: low/inverted contrast, the regime where the silhouette assumption breaks. A small electric UAV is a near-ambient body with a small warm motor patch — a **positive (bright) blob against cold sky, a negative (dark) blob or vanishing blob against hot ground**, with a crossover where it disappears. **Features must be relative/local-contrast and POLARITY-AGNOSTIC (`|contrast|`, not sign)** or they fail at the horizon.

> **Verdict:** "Detecting a coherent small warm/cold blob" is tractable (prior briefing front-end). "Coarse bird-vs-powered-flyer from multi-second **kinematics**" is tractable. **"Fixed-wing-vs-rotary silhouette ID at standoff" is NOT** — it is an endgame-only tie-breaker, not the workhorse.

### 3.2 Kinematics carries the load; appearance is an endgame bonus

The strongest published night drone-vs-bird results lean on **trajectory, not shape**: ~92% acc / 0.98 AUC from CNN+iTransformer/BiLSTM over ~48-frame trajectory sequences on targets that are "11×11 px or smaller" — i.e. appearance is nearly gone and **dynamics do the work.** This confirms B5 (the ~3 s IMM kinematic classifier) is the **right primary discriminant**, and shape is a bonus that switches on only in the endgame.

### 3.3 The resolution-staged feature cascade

| Stage | Subtense | What discriminates | Notes |
|---|---|---|---|
| **FAR/SMALL** | 1–5 px (most of flight) | **NO appearance** — kinematics only: smoothness, turn-rate, lateral-accel bound, heading-jitter variance, speed steadiness | bird = flap-jitter + sharp/darting turns + speed variance; powered UAV = smooth, bank/turn-radius-constrained, steady speed. Hand-crafted features + GB-trees (B5). |
| **MID** | ~6–12 px | appearance as **soft evidence**: blob elongation/aspect (fixed-wing high, multirotor compact, bird intermediate & time-varying); **hot-spot count/arrangement** (1 warm point = fixed-wing/bird; symmetric N-cluster = multirotor; diffuse core = bird) | relative-contrast peaks inside the blob, polarity-agnostic. **Abstains** below ~8–10 px. |
| **NEAR/ENDGAME** | >12 px | silhouette/aspect + motor-cluster geometry now real; **micro-motion periodicity** (autocorrelation of blob area/intensity at ~4–10 Hz = flapping bird; rigid drone = none) | cheap, CPU-only, independent of the other cues. |

**Fusion:** late **log-likelihood-ratio** of the three loosely-independent streams (kinematics always-on/primary; signature/hot-spot range-gated; appearance+micro-motion endgame-only), each with an explicit **"insufficient resolution → abstain"** state, combined into one class posterior **with hysteresis** so one bad frame cannot flip the label. The label is **advisory to the operator-confirmed lock, never a per-frame re-acquire trigger** (decoupling rule).

### 3.4 The micro-motion subtlety (a real but bounded cue)

Birds flap at ~4–10 Hz (a strong quasi-periodic area/intensity oscillation); rotary/fixed-wing bodies are rigid; rotor blade-flash is ~50–100 Hz. **Critically: 50–100 Hz blade modulation is far above the FT640 CVBS frame rate and aliases away — invisible.** So **micro-Doppler-style rotor detection (radar's best discriminant) does NOT transfer to our imager.** Only the slow ~5 Hz bird flap is observable, and only when the bird is large/close enough to modulate the blob. **Micro-motion is a weak-but-real BIRD-detector, not a drone-type classifier.** Do not attempt rotor blade-flash detection.

### 3.5 The DATA PLAN — what the 117 GB must contain (the project's biggest classification risk)

**No public dataset matches our regime: a moving, vibrating, AGC'd 8-bit single-band seeker looking air-to-air at another aircraft at night.** Public sets are mostly **look-UP/ground-based** (Halmstad FLIR-Boson 320×256, SIRST-UAVB, LAT-BirdDrone turntable); BIRDSAI is aerial-thermal **look-DOWN but at animals/humans, ~75% synthetic, no UAVs.** A net trained on existing public data **will NOT generalize to our seeker out-of-the-box.** Therefore a **self-collected FT640 campaign is on the critical path** and the 117 GB must be structured to cover:

1. **Our own seeker, with live AGC and platform vibration present** — not a clean lab camera. The AGC re-normalization, FFC/NUC artifacts, and seeker jitter are part of the signal and must be in the training distribution.
2. **Both geometries:** cold-sky **look-UP** AND hot-ground **look-DOWN** (the hard, under-represented one).
3. **All classes + hard negatives:** fixed-wing + multirotor + **birds at matched size/kinematics** (hovering quad vs soaring bird; jinking drone vs darting bird) + **ground clutter** (chimneys, vehicles, sun-warmed structures, animals, people, thermals) + **AGC-bloom/FFC artifacts.**
4. **Staged ranges spanning the 1–3 px → resolved transition** — so the resolution-gated abstain logic is trained and measured across the regime where appearance switches on.
5. **Hard negatives over-represented** to measure the **real false-alarm ceiling** on the two acknowledged-unsolved edge cases.

**Synthetic data / sim-to-real (be honest):** synthetic LWIR + CycleGAN style-transfer + pseudo-IR semi-labeling **narrow but do not close** the gap. The gap is **appearance** (texture/AGC/noise) **AND content** (scenes/poses). Synthetic IR **cannot fake** emissivity, contrast inversion, AGC re-normalization, atmospheric LWIR transmission, or seeker jitter. **Use synthetic for geometry/aspect augmentation only; pre-train/augment on public sets (Halmstad, SIRST-UAVB, LAT-BirdDrone; BIRDSAI for clutter hard-negatives); FINE-TUNE and VALIDATE on held-out real look-down FT640 data.** Keep the appearance-invariant kinematic expert as the robustness anchor for when the CNN's domain gap shows.

**Adopt (Section 3):** build B5 as the primary night classifier; add the resolution-gated, polarity-agnostic, abstain-by-default appearance stage; add the endgame micro-motion bird-detector (no rotor blade-flash); fuse by late LLR with hysteresis and per-stream abstain (advisory label only); stand up the dedicated FT640 data campaign as a first-class deliverable with the structure above; curate hard negatives explicitly.

---

## 4. AUTONOMOUS SAFETY — The Decide/Abort State Machine That Makes F&F Safe

This is the **genuine gap** and the most important change in this briefing. The prior briefing handled guidance; the repo handles arming/failsafe/hwkill — but **nothing re-checks, at the moment of commit, that the blob about to be hit is still the operator's confirmed track, and the existing failsafe/hwkill assume a live tether that fire-and-forget removes.**

### 4.1 The third decoupled layer: DECISION ≠ GUIDANCE

The prior briefing decoupled detection from guidance. This adds a **third decoupled layer ABOVE guidance: a small, conservative ENGAGEMENT-COMMIT/ABORT authority that decides whether the PN loop is even allowed to drive toward impact.** PN computes "how to hit"; the commit layer decides "are we **allowed** to, **right now**, **still**." The published frame is the **Simplex / runtime-assurance pattern**: an unverified complex chooser (tracker+classifier+PN) wrapped by a **small VERIFIED safety monitor** that can veto and force the safe action — mapping directly onto the repo's existing "inverted verifier" philosophy in `safety/verifier.py`.

### 4.2 Fire-and-forget is a point estimate that must be CONTINUOUSLY RE-EARNED

The operator's COMMIT authorizes engagement of a **specific track** under **specific constraints** — a "boxed autonomy" authorization (target-profile + geo/altitude box + time-window). Published **meaningful-human-control** criteria (predictability, reliability, traceability) require the round to hold the engagement **inside that box** and **self-terminate if it leaves it.** Autonomy is bounded by what the human could foresee at launch, not open-ended.

### 4.3 The COMMIT_GATE — terminal target re-validation (a published, patented mechanism)

The "munition with **integrity-gated go/no-go** decision" patent family defines **"weapon integrity" = a calculated confidence that an UNINTENDED engagement cannot occur**, evaluated at go/no-go points; below threshold → abort. Our **COMMIT_GATE** is a late, hysteretic go/no-go that fires **only if ALL hold**:

| Gate term | Source in repo / prior briefing |
|---|---|
| (a) **track-ID continuity unbroken** from the operator-confirmed track (no pull-off onto a hotter blob) | combined-cost association A1 + frozen template B2 |
| (b) **lock-quality / track-score above threshold** (= the patent's "integrity confidence") | M-of-N + log-LR score B4 |
| (c) **class still "air target, drone-plausible"** — NOT bird, NOT ground/human | ensemble B5 (Section 2/3) |
| (d) **geometry inside ROE** (a crosser drives required-g unbounded AND signals a likely wrong/maneuvering target) | high-crossing abort C5 |
| (e) **inside the geo/altitude/time box** | new boxed-authorization fields (Section 4.5) |
| (f) **sensor & clock healthy** (finite, fresh) | `failsafe.py` Watchdog + the NaN-clock→kill discipline already in `arming.py` |

**Any single FALSE → ABORT, not retry-forever.** Tune for **low false-COMMIT** (prefer a miss over a wrong hit). Default-deny on uncertainty.

### 4.4 The link/beacon contradiction — the single most important fix

The repo as-built **contradicts the no-datalink mandate** and would not function as a fire-and-forget round:

- `failsafe.py` treats **LINK-LOSS → ABORT** (`link_timeout_s=0.2`) — correct for a tethered round, but fire-and-forget has **no link to lose**; shipped unchanged the round **aborts immediately** post-launch.
- `hwkill.py` is **DEFAULT-DENY unless a permit BEACON is continuously received** (`beacon_timeout_s=0.5`) — shipped unchanged the round **can never stay armed** without a continuous operator beacon.

**The published reconciliation:** the abort **authority must move ONBOARD and become self-contained.**
1. Replace *"operator link must be alive"* with *"onboard self-checks + the boxed authorization must remain valid"* — the round aborts on **its own detected faults / box-breach / lost-track-confidence**, not on hearing the operator.
2. Keep an **OPTIONAL** short-range one-way permit/abort beacon **if RF reach allows** (a man-on-the-loop bonus) — but the round must self-safe correctly with **NO beacon**; beacon-present only **ADDS** an abort path, never **gates** normal operation.
3. The **independent HW-kill stays** as the physical backstop, but its enabling condition becomes **timed onboard arming/box logic**, not a continuous external tether. (Note the design's discipline that any powered cut occurs only over a **surveyed/cleared ground keep-out footprint** — the safe state must be a real, surveyed place.)

This keeps us in the defensible **"human pre-selected the specific target, round only prosecutes within a tight box, self-safes by default"** category (DoD 3000.09 "semi-autonomous / human-in-the-loop"), rather than drifting to "human-out-of-the-loop" for the abort function.

### 4.5 The boxed authorization, wrong-target veto, and the safe state

**Encode the authorization as onboard hard limits** — extend `ArmingAuthorization` (which today carries `issued_at_s`/`expires_at_s`/`mission_goal` but **no geo/altitude/target-profile box**) with: target-profile id, geo no-engage/keep-in polygon, **min/max engagement altitude (AGL air-domain gate)**, and time-window. **Self-terminate the instant any limit is breached** — the DoD-3000.09 "complete within timeframe/geography or self-terminate" clause made concrete.

**Wrong-target avoidance = the distinction obligation rendered as code** — a layered set of **negative gates** in COMMIT_GATE: bird-vs-drone kinematic gate (B5); **above-horizon + minimum-AGL air-domain gate** (a hot human/vehicle is **never** a valid air target); friendly/no-strike geo-exclusion + own-side track exclusion. Tune for **low false-commit**, accepting more no-commits (misses) than wrong-commits.

**The safe state must be a designed, real state — IEC 61508 discipline.** "Self-safe" is **NOT** "fly to last-known target and hope." It is **break lock / level out / fly to a pre-surveyed safe-ditch footprint / self-deactivate the effect**, then **latch**. Lost-lock, lost-track-confidence, mis-classification, sensor fault, NaN/clock fault, and out-of-box geometry **all resolve to ABORT**, not to coast-onto-the-brightest-blob. Without a surveyed ditch path, "abort" just means an armed round flying somewhere uncontrolled — **the safe STATE must be engineered, not assumed.**

### 4.6 Traceability — extend the signed-event journal to onboard decisions

Meaningful-human-control's tracing condition + DoD T&E require every commit/abort decision and the authorization it ran under to be **logged with enough state to reconstruct WHY.** The repo already has the right primitive — `safety/verifier.py`'s Ed25519-signed, JSONL-journaled, schema-verified events. **Emit the same signed, replayable record for every COMMIT and ABORT** with the authorization id + the gate's pass/fail vector, satisfying traceability and feeding Gate-L sim replay.

### 4.7 The decide/abort state machine (layered above guidance)

```
SAFE ─► AUTHORIZED ─► ARMED/RAMP ─► SEEK/TRACK_HOLD ─► COMMIT_GATE ─► TERMINAL_CLOSURE ─► IMPACT
  (operator confirms THIS track     (arming.py        (acquire &      (Section 4.3        (FOV-constrained,
   + signed boxed-authorization:     sequence)         confirm the     all-must-hold       predicted-lead;
   profile, geo/alt box, time-                         authorized      go/no-go)           prior briefing §4)
   window, ROE flags)                                  track)
                                                                            │
  ╔══════════════════════════════════════════════════════════════════════╗ │ any term FALSE
  ║  ABORT  (reachable from EVERY state) ─► SELF_SAFE ─► LATCHED            ║◄┘
  ║  break lock · level · fly-to-surveyed-ditch / deactivate-effect        ║
  ║  · independent HW-kill backstop (timed onboard logic, not a tether)    ║
  ╚══════════════════════════════════════════════════════════════════════╝
```

**Adopt (Section 4):**
1. Build an explicit COMMIT/ABORT state machine (e.g. `fpv/safety/engage_fsm.py`) layered ABOVE `guidance/pipeline.py`, feeding `arming.py::abort()` — pure CPU, deterministic, fully unit-testable.
2. Add the late, hysteretic COMMIT_GATE (terms a–f); any false → ABORT; tune for low false-commit.
3. **Re-architect `failsafe.py`/`hwkill.py` from a link/beacon tether to an onboard self-contained abort authority** — the prerequisite for being a fire-and-forget system at all. Optional beacon adds an abort path, never gates operation.
4. Extend `ArmingAuthorization` with target-profile + geo/alt polygon + min/max AGL + time-window; self-terminate on any breach.
5. Wire the non-combatant/wrong-target veto into COMMIT_GATE (bird gate, above-horizon/min-AGL air-domain gate, friendly/no-strike exclusion).
6. Extend `verifier.py` to journal signed, replayable COMMIT/ABORT decisions with the gate vector.
7. Add **Gate-L sim cases that PROVE the abort logic**: lost-lock at small t_go → SELF_SAFE (not coast-to-impact); classifier flips drone→bird mid-terminal → ABORT; target exits geo/alt box → self-terminate; second hotter blob enters gate at commit → no-commit; clock-NaN/sensor-stale at COMMIT_GATE → ABORT. **"Wrongly committed" is a hard test failure; "safely aborted a real target" is acceptable.**

---

## 5. HONEST LIMITS — What This Hardware Fundamentally Cannot Do for F&F

A single-band 8-bit AGC thermal seeker + RPi5 CPU + passive monocular, with no datalink, has **structural** limits that no software or AI removes:

1. **No reliable terminal re-validation on one 8-bit band.** Bird-vs-drone is "the algorithm's Achilles heel"; even good multi-feature **radar** trajectory work gets ~95% TP at <9% FP — and that is **radar**, not a 1–3 px look-down thermal blob under per-frame AGC. The COMMIT_GATE's class term will **sometimes pass a bird/clutter and sometimes veto a real drone.** The gate **reduces** wrong-commits; it does not make them rare enough to claim discrimination guarantees. **Its honest value is biasing errors toward MISSES, not toward correctness.**

2. **The freshest evidence is the LEAST trustworthy precisely when you most want it.** The prior briefing's own endgame analysis shows `t_go`/τ degenerate and the centroid wanders in the terminal window — exactly when COMMIT_GATE would fire. **Mitigation: commit EARLIER on a high-confidence pre-terminal track, then fly predicted-lead** — which weakens the "re-validate at the last instant" ideal. There is no clean way around this on a passive seeker.

3. **No post-launch human abort.** No datalink moves us toward "human-out-of-the-loop" for the abort function. We can argue "semi-autonomous: human pre-selected the specific track within a tight box," but the meaningful-human-control literature warns **"boxed autonomy" is insufficient unless the box is so tight that the outcome is reliably traceable to the human's launch decision.** On a passive-monocular round with seconds of flight and a wandering thermal lock, that box is hard to make tight enough to be fully defensible — a **genuine ethical/legal limit, not just engineering.**

4. **No range/Vc observability.** Passive monocular cannot observe range or closing speed without own-maneuver parallax (prior briefing §4/§5). The "basket" is **angular** (from IMM angle-rate covariance only) and degrades exactly when looming/τ degrades — at acquisition, crossing, and impact.

5. **Strapdown narrow-FOV bounds achievable geometry.** A target forcing a large commit maneuver can be lost out of frame; FOV-constrained guidance buys in-frame retention **at the cost of miss distance / achievable g**, compounding the energy limit (a 35–45° tilt-limited quad already cedes crossing/last-jink geometries).

6. **No rotor micro-Doppler.** The best radar drone-vs-bird discriminant aliases away at CVBS frame rates — unavailable to us.

7. **Software fail-safe is necessary but not sufficient.** A hung Pi cannot run COMMIT_GATE at all → the independent physical backstop is non-negotiable; but with no operator beacon that backstop is now a **timer/box-logic**, which can mis-fire safe (abort a good run) or, if mis-set, fail to abort a bad one.

8. **The gate cannot exceed the calibration of its inputs.** A confidently-wrong classifier defeats the whole gate, and **with one band there is no independent cross-check.**

### What would change the answer — minimal additions

| Addition | What it buys | Cost / caveat |
|---|---|---|
| **One short-range active ranger fused only in terminal** (ToF/lidar <100 m, or small Ka-band mmW) | Range + Vc → true ZEM/timed-effect; "angle steers, range triggers" | mmW = power/weight/cost; lidar = FOV/weather/eye-safety limited (prior briefing §4) |
| **A second spectral band (e.g. IR+UV or two-colour)** | The most powerful flare/decoy/clutter discriminant; lifts discrimination off the thermal-only line | New sensor; not the FT640 |
| **A short-range one-way ABORT-only beacon** | Restores a man-on-the-loop abort path (does not gate normal operation) | RF-reach-limited; optional by design |
| **A self-collected, seeker-matched look-down FT640 dataset** | The only thing that makes the classifier numbers real rather than optimistic | The biggest classification risk if under-funded (Section 3.5) |
| **Event-camera / SNN front-end** | µs latency, no motion blur, low power | Different sensor + stack; future block, not retrofittable to FT640 |

**None of these is a real-munition uplift** — they are sensing/data additions to a sense-and-decide problem.

---

## 6. SHORTLIST — Top 5 Next Moves Toward a Safe Fire-and-Forget Night Interceptor (ordered)

1. **Re-architect `failsafe.py` + `hwkill.py` to an onboard self-contained abort authority.** *Without this the round either never arms (no beacon) or aborts instantly (no link) — it is not a fire-and-forget system at all. The single hard prerequisite. Optional beacon adds an abort path; never gates operation. Keep the independent HW-kill as a timed-onboard-logic backstop over a surveyed ditch footprint.*

2. **Build the explicit decide/abort state machine + COMMIT_GATE** (`fpv/safety/engage_fsm.py` above `pipeline.py`; the 5-state ACQUIRE→CONFIRM→COMMIT→TERMINAL→ABORT spine; late hysteretic go/no-go on terms a–f; any-false→SELF_SAFE; extend `verifier.py` to journal signed COMMIT/ABORT decisions). *Turns "fire-and-forget" into "fire-and-forget-but-self-safe-on-doubt." Pure CPU, deterministic, fully testable — and it labels machinery we already own.*

3. **Stand up the seeker-matched look-down FT640 data campaign** (cold-sky look-up AND hot-ground look-down; fixed-wing+multirotor+birds+ground clutter; staged 1–3 px→resolved ranges; AGC/FFC/vibration present; hard negatives over-represented; synthetic-IR for geometry only; validate on held-out real). *No public dataset matches our seeker; this is the binding constraint on every classification number and the project's biggest classification risk. On the critical path.*

4. **Implement B5 as the calibrated decision-level ensemble with an ABSTAIN band** (kinematic-tree + appearance-tree + tiny-INT8-CNN-on-chip → log-LR stacker → B4 + engage-permission only; per-track/every-Nth-frame; PN sees the classical centroid exclusively; abstain → coast-and-reconfirm). *The one legitimate AI slot, with the reject option that substitutes for the absent human. Add a Gate-L case measuring amortized loop latency with the ensemble live.*

5. **Add FOV-constrained terminal guidance + the covariance-sized, hard-capped re-acquisition basket** (look-angle clamp on commanded tilt so the commit maneuver cannot swing the target out of the body-fixed Boson's FOV; REACQUIRE crop sized from IMM `S` + time-since-lock with a geometric anti-second-blob cap → HARD_LOST/ABORT if violated; forbid acquiring any new track post-COMMIT). *Closes the strapdown narrow-FOV failure mode and makes the anti-lock-theft / LOBL-not-LOAL invariant geometric.*

**Throughline for the team:** Move 1 makes us *actually* fire-and-forget; Move 2 makes fire-and-forget *safe*; Move 3 makes the perception numbers *real*; Move 4 puts AI in its *one legitimate slot with a reject option*; Move 5 closes the *body-fixed-seeker geometry* gap. **None requires a GPU, a second band, a datalink, or any weapons-construction work — all of it is classical, CPU-only, relative-feature, deterministic software on the RPi5 + FT640 reality.** And the honest ceiling stands: on this hardware, autonomy buys **survivability and a disciplined bias toward aborting on doubt** — not discrimination certainty, and not autonomous target selection.

---

**Files referenced (all verified present):**
- `/Volumes/Samsa/ai_v2.0/03-fpv/docs/GUIDANCE_DOCTRINE_BRIEFING.md` (the doctrine this builds on — coherence tracker, decoupling, A1–C5, endgame, what-does-not-transfer)
- `/Volumes/Samsa/ai_v2.0/03-fpv/docs/BLOCK03_THERMAL_INTERCEPTOR_DESIGN.md` (design baseline)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/fpv_ai/betaflight_link/arming.py` (SAFE→…→AI_ACTIVE→KILLED; `ArmingAuthorization` with keypress-in-window + `mission_goal`, but **no geo/alt/profile box**; `abort()`→sticky kill; NaN-clock fail-safe)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/fpv_ai/betaflight_link/failsafe.py` (**link-loss→ABORT @0.2s**; guidance HOLD_LAST@0.1s/ABORT@0.5s — the tether to re-architect)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/fpv_ai/betaflight_link/hwkill.py` (**default-deny unless permit beacon @0.5s** — the tether to re-architect; surveyed keep-out footprint discipline)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/fpv_ai/gates/lock.py` (FSM: NO_TARGET/CANDIDATE/LOCKED/DEGRADED/PREDICTIVE_TRACK@500ms/REACQUIRE@1500ms/HARD_LOST; currently a racing-gate tracker, "does not publish abort/failsafe decisions")
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/safety/verifier.py` (Ed25519-signed, schema-checked event journal — extend to onboard COMMIT/ABORT records)
- `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/bearing_rate.py`, `guidance/pipeline.py`, `seeker/{track,imm,looming,egomotion,detect}.py` (tracker+PN spine the autonomy machine wraps)
