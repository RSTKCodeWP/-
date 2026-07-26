<!-- Block-03 checkpoint: the single entry point and source of truth. Update this when reality changes. -->

# BLOCK-03 — CHECKPOINT 2026-07-19

> **Verification state:** full suite (system-level tests included) **735 passed, 3 xfailed, 0 failed**,
> 32:27, run 2026-07-20 against this tree. Fast gate: 665 passed. Every number in this document is from
> that tree.

**Read this first.** The project has 24 documents written across a month, during which the doctrine changed
several times. Individual documents are snapshots of what we believed *then*. **This file is what we believe
now**, with the evidence for each claim named. Where a document contradicts this file, this file wins.

Governing rule for everything below: **Наука во главе — a claim is worth exactly its evidence.** Several
things we once called "proven" are listed in §7 as retracted. That ledger is deliberate: it is how we keep
the rest of the claims trustworthy.

---

## 1. What the system is

A **body-to-body kinetic counter-UAS interceptor**. A quad FPV airframe carries a thermal seeker and a
companion computer; the operator acquires and authorizes; the interceptor closes and destroys the target by
**physical contact**.

| | |
|---|---|
| **Target** | weakly-maneuvering **winged UAV** (not a quad — see §3) |
| **Kill mechanism** | **airframe contact. NO warhead.** Kill criterion is `CPA ≤ 1.5 m` (contact radius) |
| **Authority** | **human, two presses** (lock, then commit). The machine never decides *whether* to strike |
| **Seeker** | Foxeer **FT640(LM) V2** LWIR, 640×512, **analog CVBS 8-bit — no Y16 radiometry** |
| **Computer** | **Raspberry Pi 5** now (Python prototype) → **Zynq-7020** target (Pi misses real-time 9–48×) |
| **Flight controller** | SpeedyBee F405 V4, Betaflight 4.4.3 fork, MSP over USB `/dev/ttyACM0` |
| **Plant limit** | `a_lat = g·tan(θ)`, θ≤40° → **0.84 g** — but see §5.0: the *usable* figure on a strapdown mount is **0.36 g** |

---

## 2. Honest capability statement

This is the section to read before describing the system to anyone outside the project.

### Proven on real hardware
- **Perception on a live FT640.** Detector deployed on a Pi 5, live stream, systemd service, recording,
  web UI. Measured: 16.9 fps, 6.5 s cold start.
- **The operator chain end to end**: designate → lock → two-press Ed25519 dual-signature → arming reaches
  `AI_ACTIVE`. Load-bearing negative test: **without the two presses the system never arms and never hits.**
  The crypto authority is real, not decorative.
- **MSP override link** to the flight controller, with the pilot holding a manual backup (transmitter
  toggle; release or Pi-loss returns control to the RX). Bench-verified; **not yet flown.**

### Proven in simulation only
- **Autonomous closure with a REAL gimbal — 10/10.** The full `ProductionRuntime` (perception → mission FSM
  → authority → arming) flies a from-below intercept to contact, `CPA ≈ 1.23 m` (1.11–1.44), lock 90%,
  arming 10/10, across 10 seeds. This is a *real* 2-axis gimbal — `fpv.gimbal.plant` servo slew limit
  (500 °/s) and lag (0.01 s), steering on the centroid **the seeker itself reports** (a closed perception
  loop, never truth), holding inertial attitude when unlocked. It still requires the two-press (negative
  control passes). See §5.0d.
- **The same intercept on a STRAPDOWN head — 0/5.** `CPA ≈ 2.4 m` against a 1.5 m contact radius, on the
  identical harness. This is the doctrine-specified mount, and it is the binding problem (§5.0).
- **MARCH protocol**: reacquisition of a target that left the field of view by 99°, via inertial trajectory
  estimate + slew-to-cue; tracks the prediction within ~2°.
- **Formal `COMMITTED`** now closes on **4 of 5 seeds** — but only with abort persistence enabled, which is
  **off by default** for the reason in §6.1.

### NOT proven — two capability gaps measured 2026-07-20
- **Clutter / bad FT640 data breaks the intercept.** With a single confuser as bright as the target near its
  bearing, the naive tracker is pulled onto it and misses (1/5). The discrimination features
  (correlation / JPDA / consensus) exist but are UNTUNED for the synthetic clutter render — turned on, the
  target never locks at all. So **clutter robustness is genuinely unresolved and this sim cannot answer it**;
  it needs real thermal (`real_ingest` / HIL, GAP 2). Pinned by `test_clutter_and_side_aspect...`.
- **Side-aspect crossing target does not close — now g-wall-limited, not lock-limited.** A ground-cued winged
  UAV seen from the side is acquired and commits, but misses (CPA ~2 m at 18 m/s). **MARCH is now wired into
  the loop** (`launch_and_forget march=True`, and the real flight brain `GimbalFlightHead(march=True)`), and
  it does its job: lock retention rises **23% → 59%** (12 m/s) / 20% → 38% (25 m/s) — the target is no longer
  lost from frame. But the intercept still misses, and the attribution is now clear: it **ABORTS on the ROE
  g-envelope** (crossing demands more lateral g than the 0.84 g quad has) and coasts to a miss. So the
  crossing case is bounded by the **plant g-wall**, exactly as the 3-to-1 rule predicts — MARCH fixed the
  tracking, the airframe still cannot pull the turn. The design case (from-below, overhead) closes 10/10.

### NOT proven, and honestly out of reach today
- **Any intercept in flight.** Nothing in §2.2 has flown. The gap between a sim that closes and an airframe
  that closes is the whole remaining risk.
- **A maneuvering target.** Independent literature (Almaz-Antey) puts the demand at **10–30 g** for a
  maneuvering target. We have **0.84 g**. Measured boundary: target weave **≥0.4 g → miss**; ~0.2 g already
  marginal. This is a physics wall — no law, filter, or code change moves it. More g means a different
  airframe.
- **Passive range.** Bearings-only cannot measure range without a deliberate observability maneuver, and
  the maneuver competes with the intercept (§6.2).

---

## 3. Current doctrine (authoritative)

1. **Body-to-body, no warhead.** Kill = contact. Any document proposing a lethal-radius criterion is void
   (see `HARDWARE_BUILD_SPEC_2026-07-11.md` §2, struck).
2. **Human authority, two presses.** The operator confirms the target. **No code and no hardware ever
   permits or denies a strike on its own judgement** — the machine's only power is to *withhold*.
3. **The machine never classifies target type.** The learned drone-vs-bird classifier and its dataset were
   **deleted 2026-07-11** at the owner's direction. Any document describing a classifier in the engage path
   describes a system that no longer exists.
4. **Target is a weakly-maneuvering winged UAV**, not a quad. A winged UAV is inertial (it cannot pull 10 g),
   which is what makes a 0.84 g interceptor arguable at all.
5. **GIMBALLED seeker: FT640 on our 2-axis gimbal, camera up** (owner decision 2026-07-19). This supersedes
   the earlier strapdown mandate — the measurement decided it (strapdown 0/5, real gimbal 10/10; §5.0d). The
   flashing-ready code for this build is in `FLASH_AND_BRINGUP.md`.

---

## 4. Code structure

```
fpv/                  THE TRUNK — all work happens here (~18k lines)
  seeker/             detection, LOS, IMM/JPDA tracking, subtense range      (7.2k)
  guidance/           PN laws, command mapping, pipeline, passive range      (4.6k)
  fpv_ai/             mission runtime, production runtime, FC link, ops      (1.7k)
  fpv_ai/bench/       sims and experiments (honest 3D, launch-and-forget…)   (3.5k)
  gimbal/             2-axis gyro-stabilised head: controller, plant, bench  (0.6k)
seeker_core/          DIRECTION, not trunk — clean-room contracts + ports    (1.0k)
contracts/            typed cross-boundary contracts
```

**Note on `fpv/gimbal/`:** a working 2-axis gyro-stabilised head — controller, servo plant model, bench
runner, data logging, tests — already exists and is wired into `seeker_core` as a first-class stage. The
configuration that §5.0c shows is the one that closes the intercept is therefore **already largely built**,
not hypothetical. What it has never had is a measurement of the *whole* chain running on it.

**On `seeker_core`:** it is the *target architecture* (sensor-in → commands-out behind strict typed
contracts, the shape we want for the FPGA port), not a second implementation. **We are not migrating now**
and it is not dead either. Porting 18k proven lines behind new contracts costs weeks and buys structure, not
capability — and §6 shows we still have unresolved *physics*. Correct order: settle the physics, then let the
real FPGA port drive the migration. Until then `fpv/` is where code changes go.

### Running it

```bash
cd 03-fpv
PYTHONPATH=.:fpv python3 -m pytest fpv/ -q -m "not slow"   # fast gate: ~2:00, 665 pass (components only)
PYTHONPATH=.:fpv python3 -m fpv_ai.bench.launch_and_forget  # full autonomous closure
PYTHONPATH=.:fpv python3 -m fpv_ai.bench.passive_range_sim  # bearings-only observability
PYTHONPATH=.:fpv python3 -m fpv_ai.bench.march_sim          # MARCH reacquisition
PYTHONPATH=.:fpv python3 -m fpv_ai.bench.pn_law_compare     # PPN vs our perp-LOS law
```

### ⚠️ The gate does not test the system

`-m "not slow"` deselects **every system-level test there is**: `test_launch_and_forget`,
`test_gimbal_closed_loop`, `test_strapdown_honest_weaknesses`, all four S3/Mode-B acceptance suites,
`test_monte_carlo`, `test_high_speed_intercept`. The fast gate exercises **components**; the claims live in
the excluded set.

That is exactly how the ideal-gimbal fidelity defect survived: `launch_and_forget` modelled a stabilised
camera for months, and when its assumptions finally shifted, **6 of its 8 tests were failing invisibly**
because CI never ran them.

So: the fast gate is for iteration. **No capability claim may rest on it.** Before stating anything about
what the system does, run the full suite and say when it was last run:

```bash
PYTHONPATH=.:fpv python3 -m pytest fpv/ -q          # ~45-60 min, the one that tests the system
```

Do not run several full suites at once — they starve each other and look like hangs.

---

## 5. Where the real difficulty is

### 5.0 The "0.84 g wall" is a FIELD-OF-VIEW wall, not a thrust wall

A quad has no sideways thrusters. Every lateral force comes from tilting the thrust vector, while keeping
enough vertical component not to fall: `T·cos θ = mg`, `a_lat = T·sin θ/m` → **`a_lat = g·tan θ`**. At our
configured θ = 40° that is **0.84 g**, and the turn radius at 35 m/s is **149 m**. In the final 0.7 s (~24 m)
the largest lateral correction available is **2.0 m**; in the final 0.3 s, **37 cm**. Late correction is
physically impossible — the error has to be gone before then.

**But 40° is not a thrust limit.** Holding altitude at 40° needs thrust/weight of only `1/cos θ = 1.31`, and a
racing quad has 4–8. In general `T/W = √(1+n²)`, so even 3 g of lateral would need only T/W ≈ 3.2 — which we
have. The real limit is elsewhere:

**The FT640's half-VFOV is 19.9°. On a STRAPDOWN mount the boresight tilts with the body.** A target near the
centre of frame — which is exactly what a collision course produces — leaves the frame at about **20° of
bank**. So the lateral acceleration we can use *while still seeing the target* is:

| | tilt | a_lat |
|---|---|---|
| keeps a centred target in frame | ≤ 19.9° | **0.36 g** |
| our configured limit | 40° | 0.84 g — **but the target is gone** |

So **the "0.84 g plant wall" and the "strapdown attitude↔seeker coupling" are the same wall**, and it is set
by the field of view. This is what the §6.1 measurement was showing: 100 ticks at saturated bank were 100
ticks with the target outside the frame, steering on a λ̇ our own maneuver had destroyed. It also means **more
g cannot be bought on a strapdown mount** — tilt harder and you blind yourself sooner. A gimbal is the only
thing that breaks this specific wall (the owner's QD115TB has ±180° of travel, far more than the ~±25° needed;
travel is not the constraint, slew rate is). Applying the 3-to-1 rule to 0.36 g puts the honest maximum target
maneuver at **~0.12 g**, not 0.28 g.

### 5.0b The harness was fixed, and the result changed the headline claim

`launch_and_forget` projected through `fwd = rel[2]` — the boresight nailed to world-up, never tilting with
the airframe. It was silently modelling an **ideal gimbal**, and every "launch-and-forget proven" number came
from that. Fixed 2026-07-19: the boresight is now the thrust direction (`normalize(ax, ay, az+g)` — exact,
since a quad's thrust and its strapdown camera share the body +z axis), plus a physical **0.10 s attitude
lag** (without it the camera teleports between commanded attitudes and reports 558 °/s body rates).

| camera model | hits | mean CPA |
|---|---|---|
| stabilised head (what was silently assumed) | **5/5** | 1.25 m |
| **strapdown, as the doctrine specifies** | **0/5** | **2.42 m** |
| strapdown + full 3-axis ego-compensation | 0/5 | 2.38 m |

**Mechanism, measured:** body rotation writes a huge apparent LOS rate into the seeker — λ̇ median **2.5 rad/s
strapdown vs 0.03 rad/s stabilised** — while the target sits comfortably inside the frame (offset ~0.7° against
a 19.9° half-FOV). *The airframe's own motion, not the target's, dominates what the seeker reports.* Note this
is **not** the FOV-exit effect of §5.0 and **not** simple ego-motion: three separate hypotheses (FOV loss,
uncompensated ego shift, camera↔world frame mismatch) were each tested and each moved the result by under 2 %.

### 5.0c Ego-compensation, settled properly (derived, not guessed)

The earlier note said the sign convention had been found by search and deserved a derivation. Done — and the
answer is layered, with each layer measured.

**1. The formula is correct.** For a camera rotating by `δ = ω·dt`, a point fixed in inertial space moves in
normalised image coordinates by

```
Δu = −δ_y(1+u²) + δ_x·u·v + δ_z·v
Δv = +δ_x(1+v²) − δ_y·u·v − δ_z·u
```

which near the boresight reduces to `Δpx = −f·ω_y·dt`, `Δpy = −f·ω_x·dt` — exactly what `los.py` implements.
Checked against exact reprojection: **1.4 % error even at a 7.3° per-frame rotation**.

**2. Where it is applied, it works almost perfectly.** Measured per frame in the live harness: actual image
shifts up to **±76 px**, predicted shift matches to a **0.17 px median residual (max 1.09)** — a 99.8 %
removal, leaving an apparent LOS rate of only 0.012 rad/s.

**3. But it is applied one stage too late.** The de-rotation happens in `los.py`, *after* the tracker. The
tracker associates blobs on **raw** pixels with a **48 px gate**, and the ego sweep reaches **48.7 px** — just
over. Traced frame by frame: the track survives a 17 px jump, survives 48.7 px, then drops to
`PREDICTIVE_TRACK` and **never recovers**. The compensation is downstream of the thing that actually breaks.

**4. Gyro-aided association helps, and does not rescue.** Feeding the same known shift into the tracker's gate
(`set_ego_shift_px`, standard seeker practice) improves mean CPA **2.42 → 2.07 m** and recovers **1 of 5**
seeds — against a stabilised head's 5 of 5.

**Verdict: ego-compensation is necessary but not sufficient.** With the formula derived, verified, and applied
at *both* stages, strapdown still closes 1 in 5 where a stabilised head closes 5 in 5. The reason is
physical rather than algorithmic: when the entire field of view sweeps ~100 px per frame against a 14 px
target, there is little left for downstream processing to rescue. This closes the question honestly — the
answer is **no**.

This **independently reproduces `sim3d_honest`'s 2026-07-05 result** (gimbal ~1.1 m vs strapdown ~10 m) in a
completely separate harness. Two independent simulations, built months apart, now agree.

### 5.0d The empty cell, filled: a REAL gimbal closes it

Five lines of evidence pointed at the gimbal configuration, but it had never been measured end to end. Now it
has. `mount="gimbal"` runs the real 2-axis head — `fpv.gimbal.plant` servo slew limit (500 °/s) and lag
(0.01 s) — steering on the centroid **the seeker itself reports** (a closed perception loop, never truth) and
holding inertial attitude when unlocked.

| mount | hits | mean CPA | lock |
|---|---|---|---|
| strapdown (doctrine) | 0/5 | 2.42 m | 30% |
| **real gimbal** | **10/10** | **1.23 m** | 90% |
| ideal gimbal (ceiling) | 5/5 | 1.25 m | 90% |

The real gimbal lands **at the ideal-gimbal ceiling** — the 500 °/s servo is fast enough that its dynamics
cost nothing here. And it still requires the two-press (negative control passes).

**The enabling insight, and it is not obvious:** a tracking gimbal makes full ego-compensation
*architecturally required*, not optional. The head rotates to hold the target centred, so image motion is
`(true LOS motion − head motion)` — the tracking cancels exactly the signal guidance needs. Feeding the head's
own inertial rate back in is what reconstructs the inertial LOS rate. Without it the same gimbal scores 0/5 at
CPA 2.52; with it, 10/10. `mount="gimbal"` enables it automatically. Pinned by
`test_a_real_gimbal_closes_the_intercept`.

---

Three walls, in order of how much they actually constrain us:

1. **The 0.84 g plant.** Binds everything. Both guidance laws saturate against any real target maneuver;
   the law is not the constraint, the airframe is.
2. **Passive monocular sensing.** No range, no closing velocity, without either an assumed target size
   (wrong by construction for an unknown target) or a deliberate observability maneuver.
3. **The terminal.** Our law blows up at `r→0` (§6.1). This is the newest and least explored of the three.

---

## 6. Open defects and contradictions

### 6.1 No explicit over-demand policy — OPEN, highest value
When guidance demands more g than the airframe has, what should we do? Today there is **no designed answer**
— the behaviour is a side effect of aborting, and it turns out to be load-bearing.

The closed loop's abort response **zeroes the lateral command**. Giving the g-abort proper persistence
(needed to fix the commit deadlock, §6.4) makes it ride through the over-demand and fly the **clamped**
command instead — which makes the miss **~2× worse on 6 of 6 seeds** (0.66→1.34, 0.84→2.67, 1.60→2.76,
0.49→1.60, 0.49→1.28, 0.72→1.32 m against a 0.75 m capture radius).

**Mechanism, measured:** riding through pins the airframe at saturated bank **8× longer** (100 vs 12 ticks
above 0.9 roll). On a **strapdown** seeker that is self-harming — full bank tilts the camera and corrupts the
very λ̇ guidance depends on (the same maneuver↔seeker coupling that made a gimbal win 9× in the honest 3D
sim), and thrust is diverted off the closing axis.

So `envelope_abort_persist_ticks` **ships at 0** until an explicit over-demand policy exists: *if the demand
is unreachable, do not fly a saturated version of it.* That policy is separable from the commit deadlock and
should be designed deliberately rather than inherited from an abort path.

> **Correction worth keeping.** This was first written up as a *terminal blow-up of our ⊥LOS law* — it fit
> the theory and was recorded before it was checked. The data refutes it: with persistence the terminal is
> **calmer**, not wilder (max |λ̇| 0.044 vs 0.127 rad/s). The damage is sustained saturation, and it is not
> specific to the terminal. This episode is therefore **not** evidence for PPN.

### 6.2 Passive range needs a maneuver that costs the intercept — OPEN
Own-maneuver parallax makes range observable (66% error → 28%), but **PN drives toward constant bearing,
which is exactly the trajectory that earns no parallax. The better the intercept, the less range you can
measure.** Also load-bearing: the EKF's own covariance **falsely converges** (claims 12% while 66% wrong), so
the range is released only against parallax earned from our own INS — never against the filter's confidence.

### 6.3 RESOLVED: mount and camera orientation
Owner decision 2026-07-19: **FT640 on our 2-axis gimbal, camera up (intercept from below).** This closes the
old strapdown-vs-gimbal question (decided by measurement, §5.0d) and the camera-orientation contradiction (the
`HARDWARE_BUILD_SPEC` §4 "boresight forward, 0° cant" line was for the strapdown build and no longer governs;
with a gimbal the head points itself). The flashing-ready code for this build exists (`FLASH_AND_BRINGUP.md`).

### 6.4 Fixed this checkpoint
- **Commit deadlock**: the abort fired on one tick and `ABORTED` is sticky, while the abort is disabled
  post-commit by design — so the abort prevented the commit that would have disabled it. Mechanism added
  (leaky accumulator), off by default per §6.1.
- **Assumed target span silently scaled range**: subtense range is `f·assumed_span/extent_px`; the harness
  rendered 2 m while the runtime assumed 4 m → range read **2× truth** and the commit gate could never fire.
  Nothing in the system noticed. In flight the true span is genuinely unknown, so **this error class is
  unavoidable for subtense.**

---

## 7. Retracted claims (the honesty ledger)

Things this project once recorded as proven, and what they actually were.

| Claim | Reality | Found |
|---|---|---|
| "Launch-and-forget proven — hits on all seeds" | Guidance was authorized only 0.14–1.20 s; the mission **ABORTED** at 1.22 s and the hit was a **post-abort ballistic coast**. The authorization chain was and remains real; the *guided committed terminal* was not | 2026-07-19 |
| "Strapdown is viable without a gimbal" | Rested entirely on assuming a warhead lethal radius. With body-to-body, CPA 2.6–5 m are **misses** and the conclusion is void; strapdown-vs-gimbal **reopens** | 2026-07-19 |
| "PPN is the fix for maneuvering targets" | ~13% less demand — real, but both laws saturate the 0.84 g wall. The plant binds, not the law. (PPN is back in favour for a *different* reason, §6.1) | 2026-07-18 |
| "Passive ranging is the biggest unlock" | Works, but coarse (28%) and needs a maneuver that costs intercept geometry | 2026-07-19 |
| "S3 acceptance green ⇒ system verified" | A large part of that suite tested the simulator's own assumptions (true LOS-rate fed to guidance; τ from true range) | 2026-06-20 audit |

---

## 8. Next work, in honest priority order

**Full assessment with effort and dependencies: `REMAINING_WORK.md`.** The short version, reordered after the
gimbal measurement (which made most of the old software items refinements rather than blockers):

1. **Owner decision on mount** (gimbal vs strapdown) and camera orientation (§6.3). Now a measured choice, not
   an argument: strapdown 0/5, real gimbal 10/10. Cheap, and everything physical depends on it.
2. **GAP 1 — build the real airframe** (`REMAINING_WORK.md`): re-flash the FC with the fork (MSP override +
   kill box — currently a stock manual quad), mount thermal seeker + Pi + kill-MCU, flash/bench the kill-MCU.
   Procurement-gated, ~1–2 weeks, and **everything real is downstream of it.**
3. **GAP 2 — first hardware-in-the-loop closure**: real seeker frames → real guidance, on a static stand then
   full HIL. Never done. This is where the sim's clean-rendered-thermal optimism meets real AGC/clutter — the
   biggest unknown, and the next milestone actually worth its cost.
4. **GAP 3 — first flight** with the MSP-override manual backup. Nothing in §2.2 is real until this happens.
5. **Refinements, now lower priority** (all were mostly attacking the strapdown failure the gimbal dissolves):
   guidance upgrade (`GUIDANCE_UPGRADE_PLAN.md` — ZEM/OGL, IRPL), over-demand policy (§6.1), passive range
   (§6.2). Worth doing for envelope width, but the 0.84 g plant wall caps the payoff.
6. Document hygiene (§9); reconsider `seeker_core` migration once GAP 2 informs it.

---

## 9. Document register

Status as of 2026-07-19. **CURRENT** = describes the system as it is · **REFERENCE** = durable science,
not a system description · **HISTORICAL** = a valid record of a past moment, not current ·
**SUPERSEDED** = describes a design we no longer have.

| Document | Status | Note |
|---|---|---|
| `CHECKPOINT.md` (this) | **CURRENT** | source of truth |
| `SYSTEM_SPEC.md` | **CURRENT** | correctly states body-to-body / no warhead |
| `REMAINING_WORK.md` | **CURRENT** | honest remaining-work assessment with effort + dependency order |
| `FLASH_AND_BRINGUP.md` | **CURRENT** | the flash & bring-up runbook for the chosen build (FT640-on-gimbal, up-camera) |
| `GUIDANCE_LAW_SCIENCE.md` | **CURRENT** | PN law analysis + the terminal finding |
| `GUIDANCE_UPGRADE_PLAN.md` | **CURRENT** | ZEM/OGL/IRPL plan — now a refinement, not a blocker (see §8) |
| `MARCH_PROTOCOL.md` | **CURRENT** | |
| `FLIGHT_TEST_OVERRIDE.md` | **CURRENT** | the flight-test path |
| `GIMBAL_BRINGUP.md`, `PI5_BENCH_SETUP.md`, `BENCH_BRINGUP_SEQUENCE.md` | **CURRENT** | hardware procedures |
| `FPGA_MIGRATION_ZYNQ7020_FT640LM.md` | **CURRENT** | target compute direction |
| `HARDWARE_BUILD_SPEC_2026-07-11.md` | **CURRENT, §2 struck** | §2 (lethal radius) void; §4 camera orientation contradicts §6.3 |
| `BLOCK03_MATURE_GSN_DOCTRINE.md` | **CURRENT, partial** | superseded on human authority (2026-07-10) and classifier removal |
| `SEEKER_SCIENCE_DEEP_DIVE.md` | **REFERENCE** | seeker physics; durable |
| `TASK1_TARGET_TRACK_TO_INTERCEPT.md` | **REFERENCE** | track-to-intercept science |
| `STATE_ESTIMATION_OBSERVABILITY_BRIEFING.md` | **REFERENCE, partial** | mentions the removed classifier |
| `FRONTIER_SOTA_SURVEY_2026-07-09.md` | **HISTORICAL** | survey at a date |
| `SCIENTIFIC_REPORT_MATH_PHYSICS_2026-07-09.md` | **HISTORICAL** | report at a date |
| `AUDIT_2026-06-25_MATH_PHYSICS_SYSTEMS.md` | **HISTORICAL** | audit at a date |
| `PROJECT_COMPLETION_PLAN.md` | **HISTORICAL** | 2026-06-20 plan; its central warning (green ≠ verified) still stands |
| `TASK1_CAMPAIGN_COMPLETE.md` | **HISTORICAL** | "verified through S3 acceptance" — see §7, last row |
| `TASK1_IMPLEMENTATION_SPEC.md` | **HISTORICAL** | spec as built in June |
| `BLOCK03_MASTER_PLAN.md` | **HISTORICAL** | 2026-06-19 consolidation of the three briefings |
| `GUIDANCE_DOCTRINE_BRIEFING.md` | **SUPERSEDED** | 2026-06-19; classifier in the engage path, pre-doctrine target |
| `FIRE_AND_FORGET_AUTONOMY_BRIEFING.md` | **SUPERSEDED** | 2026-06-19; predates human-authority doctrine |
| `BODY_AND_VV_BRIEFING.md` | **SUPERSEDED** | 2026-06-19; classifier + quad target |
| `BLOCK03_THERMAL_INTERCEPTOR_DESIGN.md` | **SUPERSEDED** | specifies FLIR Boson; the camera is FT640 |

Superseded documents are **kept, not deleted** — they are the record of how the design was reasoned, and
several were overturned by evidence we should be able to trace.
