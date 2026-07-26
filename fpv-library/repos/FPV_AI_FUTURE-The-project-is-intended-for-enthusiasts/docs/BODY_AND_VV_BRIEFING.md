> **[SUPERSEDED]** — status as of 2026-07-19. 2026-06-19. Assumes a quad target and a classifier, both since overturned (target is a weakly-maneuvering WINGED UAV per the 2026-07-04 doctrine; classifier deleted 2026-07-11). Its airframe-envelope numbers remain instructive.
>
> **`docs/CHECKPOINT.md` is the source of truth.** Where this document disagrees with it, CHECKPOINT wins.

<!-- Generated 2026-06-19 by a multi-agent study of airframe dynamics, estimation/observability,
midcourse, sensor physics and V&V, mapped onto this repo. Scope: software/controls/test only. -->

# BLOCK-03 THERMAL INTERCEPTOR — BODY & PROVING IT
## Systems Architect's Briefing #3: Airframe Envelope, Estimation, Midcourse, Sensor Roadmap, V&V

*Builds on GUIDANCE_DOCTRINE_BRIEFING (the seeker/PN/endgame "brain") and FIRE_AND_FORGET_AUTONOMY_BRIEFING (LOBL/LOAL, AI slot, autonomous abort). Those two settled the perception and guidance doctrine. This brief is about whether the **body** can fly what the brain commands, what the estimator can honestly know, and how we **prove** a first live intercept without losing hardware. Where the prior briefs gave doctrine, this one gives **numbers and limits**.*

---

## 0. THE ONE SENTENCE

We built a guidance law that can ask for 20–40 g; we bolted it to a body that delivers **0.84 g**, sees the world through **8 bits**, knows **no range at all**, and cannot correct an error in the **last 20–30 m**. Everything below is the engineering consequence of those four facts — and the test ladder that turns "we think it works" into "we proved it, cheaply, before props spun."

---

## 1. AIRFRAME ENVELOPE — What This Quad Can And Cannot Fly

### 1.1 The maneuver budget is a single number: 0.84 g

A multirotor is not a missile. Its only way to accelerate sideways is to **tilt the whole thrust vector**: `a_lateral = g·tan(θ)`. The code already encodes this honestly:

| Tilt θ | Lateral g | TWR needed to hold altitude (1/cosθ) |
|---|---|---|
| 30° | 0.58 g | 1.15 |
| **40° (our cap)** | **0.84 g** | **1.31** |
| 45° | 1.00 g | 1.41 |
| 60° | 1.73 g | 2.00 |

θ_max = 40° gives **0.84 g — that is the entire lateral maneuver budget**, ~20–40× less than the True-PN missile the guidance doctrine assumes. Every other limit in this section is a corollary of this one fact.

### 1.2 The 3-to-1 overmatch rule sets the threat envelope — by physics, not policy

Canonical ProNav result: an interceptor needs ~**3× the lateral-g capability of its target** to reliably intercept. Inverted for us:

> **a_target,max ≈ achievable_g / 3 ≈ 0.84 / 3 ≈ 0.28 g.**

We can only reliably kill a target maneuvering below **~0.28 g**. A DJI-class quad pulls >1 g; an FPV pulls several g. **On raw load factor, an evading target out-classes us.** The honest envelope is **non-maneuvering or mildly-maneuvering targets in near-head-on geometry** — exactly what the `ROEAbort` high-crossing gate already enforces. This is the physical justification for that gate: it is the **3-to-1 overmatch rule firing**, not a tunable threshold. *Action: derive and log the abort ceiling as `achievable_g/3`; annotate `HIGH_CROSSING`/over-g aborts as the overmatch rule, not magic numbers.*

### 1.3 Speed, altitude and turn are a zero-sum triangle

At max cruise speed, **all** thrust counters weight + drag — **zero margin left to turn without descending**. Flying faster to shorten t_go directly steals the lateral-g you need to correct. These are **not independent knobs**: `SpeedPolicy` must hold a minimum lateral-g reserve, capping cruise so terminal correction is always possible. *Action: couple `control/speed.py` to the g-budget; cap cruise to preserve a reserve.*

### 1.4 The body is too slow to fix late errors — the "ten-tau-to-go" wall

A homing loop needs roughly **10 system time-constants of flight remaining** to null a heading error or a target maneuver (Zarchan/Nesline-Zarchan). Our stack:

- attitude lag τ ≈ 0.10 s (Betaflight ANGLE, ~10 Hz)
- **asymmetric prop response: spin-up ~0.05 s, spin-DOWN ~0.16 s** (a jink *reversal* hits the slow branch)
- sensor + loop delay ~0.04 s

→ effective τ_system, so the loop needs **~1.0–1.4 s of flight remaining** to respond. At 15–20 m/s closing, that is the **last ~20–30 m**, where the loop is **already committed and physically cannot correct a late jink.** This is the single hardest airframe limit on terminal geometry — and it is *why* the endgame **must** hand to **predicted-lead fly-out** (guidance brief §4). Prediction is not a nicety; it is **forced by the body's lag.** *Action: implement a "ten-tau-to-go" commit cutoff — freeze to predicted-lead once `t_go < ~10·τ_system` — replacing a hand-tuned range threshold with a physically-derived one.*

### 1.5 Aggressive maneuver poisons the seeker (strapdown DRR parasitic loop)

The FT640 is **body-fixed**. To pull lateral g the body must rotate, and the seeker rotates with it. A strapdown seeker cannot measure inertial LOS rate directly — you recover λ̇ by **subtracting gyro body-rates** from image-plane angle rate. **Any error in that subtraction** (gyro scale-factor, timing skew, latency) leaks body motion straight into λ̇, closing a **parasitic feedback loop** that lowers crossover frequency and **destabilizes PN**. The harder you maneuver, the larger the body rates, the larger the leaked error. **Flying the command hard and measuring LOS cleanly are in direct tension.** Gyro scale-factor and seeker/gyro time-sync are therefore **safety-critical calibration**, not cosmetics. *Action: add a Gate-L sim case injecting gyro scale-factor error + timing skew during an aggressive maneuver; measure induced false λ̇ and bound the allowable error. Strongly prefer **hard-mounting** the camera to delete the un-modellable soft-mount transfer function from the most safety-critical signal.*

### 1.6 Raising N does not buy maneuver — it buys instability

PN's proportionality is N·Vc. Under our >25 ms delay, the effective navigation ratio must stay >2 for stability; the practical band is 3–5 at near-zero lag, and pushing above ~4 under measurable delay drives **catastrophic instability**. The code correctly **fixes N=3 and leans on prediction.** You cannot out-gain a slow body.

### 1.7 FOV-vs-g coupling: the turn that loses the target

With ~50° HFOV the usable pitch/yaw excursion is **~±20°** before the target leaves the sensor. That FOV budget — not just energy — is why θ_max ≈ 40°. The very maneuver that applies g can **swing the target out of frame.** *Action: clamp commanded look-angle so the commit maneuver cannot eject the target; on predicted FOV exit, prefer predicted-lead coast over more g.*

### 1.8 The achievable capture volume (honest)

Putting §1.1–1.7 together, the **capture volume is a narrow forward cone, not a sphere**: near-head-on aspect, target maneuver < ~0.28 g, closing speed bounded so a lateral-g reserve survives, and all terminal correction completed *before* the last ~1–1.4 s. Outside that cone the correct outcome is **abort**, and the V&V must reward the abort (see §5).

> **Sim optimism warning:** today's `quad_sim.py` uses a single symmetric τ and a velocity-aligned-boresight assumption that *hides* most ego-motion. A real body-fixed build shows worse lag (asymmetric spin-down), the full strapdown DRR loop, prop-wash/vibration into the gyro. **Sim HITs are an upper bound on real performance, not a prediction.** *Action: replace the single τ with the actuation-lag stack (ESC <10 ms → asymmetric prop up/down → attitude settling), and surface per-run **which miss term dominated**: lag (~N·Vc·τ²·a_T/2), noise (grows with N), or saturation (demand > g·tan θ_max).*

---

## 2. ESTIMATION & OBSERVABILITY — The Honest Estimator

### 2.1 The range theorem (this is a theorem, not a CPU gap)

Range and closing speed are **fundamentally unobservable** from a single passive station on a non-accelerating bearing. The Fisher Information Matrix is **rank-deficient toward range → CRLB on range = ∞.** No filter, no UKF, no neural net beats the CRLB. The bearing-rate-nuller, Vc-scheduled-not-measured design is the **correct surrender to this theorem**, not a shortcut.

### 2.2 The cruel duality: good guidance kills passive ranging

The one passive range source is **own-maneuver parallax** (the "S-maneuver"): information toward range grows with observer acceleration *perpendicular to the LOS*. But PN **nulls LOS-rate → drives toward constant bearing (the collision triangle) → zero parallax → range goes unobservable exactly as you close.** Range is weakest in the terminal endgame — precisely where the commit gate most wants it.

> **Is own-maneuver triangulation worth it for us? No — not as a deliberate kinetic maneuver.** Commanding a maneuver *to range* un-nulls λ̇ and degrades guidance on a 0.84-g airframe we cannot spare. Harvest parallax **only opportunistically** from maneuvers already commanded for guidance; never spend g on ranging. The real fix to the range wall is **hardware** (§4), not a maneuver.

### 2.3 Keep the IMM in modified-polar — do NOT "upgrade" to Cartesian

The existing IMM state `[az, el, az_rate, el_rate]` is **accidentally a reduced modified-polar (angular) state** — and that is the **published-correct** structure. MP automatically **decouples the observable subspace** (bearing, bearing-rate) from the unobservable (absolute range), preventing the covariance ill-conditioning that is the #1 cause of bearings-only filter divergence. A Cartesian 6-state "upgrade" would form an ill-conditioned covariance with an unobservable direction that corrupts **even the observable bearing states.** **Defend the angular state; forbid the Cartesian rewrite in code review.**

### 2.4 The estimator design (two tiers)

**Tier 1 — harden what exists.** Body-frame modified-polar IMM (CV / maneuver modes) fed by gyro-de-rotated pixel motion. Concrete fixes, highest value first:
- **Add online gyro scale/bias + cam-IMU time-offset as augmented filter states** (turntable sets the prior; online removes drift). Flips `ego_gate` from a blunt damper into a **corrector** — highest value per line of code, and it directly attacks the DRR parasitic loop of §1.5.
- **Feed `EgoEstimate.quality` into measurement noise R** so the filter distrusts λ̇ when de-rotation is shaky.
- **Publish innovation covariance S** as lock-quality + a **covariance-sized search box** (satisfies guidance-brief reacquire-basket needs, §3).
- Replace the fixed `ego_gate` threshold with a **covariance-derived Mahalanobis/chi-square gate.**

**Tier 2 — diagnostics-only inverse-range observer.** A single-state EKF on **1/r** (stays bounded/Gaussian as r→∞) fusing looming-τ + own lateral accel (from FC) + IMM rate, running **only when a published observability index** (perpendicular own-accel relative to assumed range) exceeds threshold; otherwise it coasts with inflated covariance and reports `observable=False`. Its output feeds **diagnostics / t_go shaping / commit-gate geometry / the Vc_eff confidence blend ONLY — NEVER the PN gain**, which stays `Vc_sched` from SpeedPolicy. *Enforce this separation in code review, not by assumption.*

### 2.5 Metric scale is unobservable too — gyro-only de-rotation is correct

Monocular VIO cannot recover **metric scale** without acceleration excitation (Fisher info toward scale ∝ **translational accel²**). Near-constant-velocity terminal against a textureless night sky = **doubly degenerate.** So **gyro-only de-rotation is the theoretically-correct ego-motion base, not a poor-man's VIO.** Do **not** attempt translational VIO (burns CPU to produce confidently-wrong scaled translation), and do **not** use learned monocular depth (a net hallucinates scale from priors that do not hold for a 1–3 px blob on sky — it *manufactures observability the optics do not contain*).

### 2.6 A consistent filter is not a correct filter

- **NIS** (online, no truth needed) proves **self-consistency** → ship as a live **"model-wrong" abort alarm** wired to lock-quality.
- **NEES** (needs independent ground truth) proves **correctness** → make it a **hard release gate** against over-confident covariance, because a confidently-wrong covariance fed to the commit gate is **worse than no estimate.**
- Use chi-square-consistency **auto-tuning to set Q honestly** instead of by hand; pair with innovation zero-mean/whiteness checks; re-run after any re-tune.

EKF/UKF are near-identical for this mildly-nonlinear angular state (UKF only if EKF consistency testing reveals atan2 bias — still microseconds). **A particle filter is unjustified** for our gated single-track regime. The estimator is microsecond-cheap on the Pi5; **the cost is calibration metrology and Monte-Carlo NEES/NIS testing**, which become formal gates.

---

## 3. MIDCOURSE & HANDOVER — The Launch-to-Lock Bridge

### 3.1 Most published midcourse doctrine does NOT transfer — say so honestly

Loft, energy-management climb-to-cruise, impact-angle trajectory shaping, GPS/INS fly-to-basket, long inertial coasts — **all long-range/ballistic constructs.** A few-second operator-cued quad has no useful loft phase. **Our "midcourse" is really a ~1–3 s designation-transfer-and-settle phase.** Pretending otherwise is dishonest.

### 3.2 The transferable core: the handover basket

The one concept that *does* transfer: the **handover (acquisition) basket** — an angular volume, sized by propagating all pre-lock uncertainties forward, inside which the terminal seeker must find and confirm the target. Successful handover requires **both** at the same instant: (a) **seeker-acquisition** (target in FOV at adequate SNR/pixels) **and** (b) **guidance-capture** (LOS-rate observable, lead achievable).

### 3.3 Short range is genuinely kind to us here — the lever-arm ≈ 1

Handover error scales as `(intercept_range / homing_range) × designation_angular_error`. For us **the homing leg IS the whole flight**, so the lever-arm ≈ **1** — the one place short range helps. The basket is dominated by **target angular uncertainty + our own attitude uncertainty**, not range error. Concretely, at 200 m a 2 mrad designation error ≈ **~4 px** — well inside one lens-FOV. **For us the basket fits inside a single fixed FOV, and FOR==FOV is workable IF the airframe points correctly at commit.**

### 3.4 The five-step bridge (maps to existing code, mostly labeling)

1. **Pre-launch designation (LOBL):** operator builds track-box + center-of-mass crosshair on the console; seeker confirms a stable multi-frame lock on the **same** blob before commit (lock-tone, Stinger pattern — already in `arming.py` flow).
2. **Boresight-correlated handover:** express the console designation in the **seeker's own pixel frame**; require **FFC/NUC complete on the ground** so the first onboard confirm is clean. The round inherits a **tight angular basket, not a coordinate** (US7463753 pattern).
3. **Basket propagation:** from commit, grow the basket through accumulated attitude + target-motion uncertainty (covariance ~ angle-rate-cov × time-since-lock), **geometrically hard-capped** so it can never admit a second strong blob.
4. **Confined search/confirm:** search **only the basket crop** (reuse the `reacquire.py` expanding-crop ladder), declare lock only on **multi-frame kinematic continuity**, then collapse to the tracking gate. **Never full-frame.**
5. **Benign settling flyout:** until the track is settled, fly **low-gain, lead-biased (pursuit→PN)** with a commanded-look-angle FOV cap so the lead maneuver can't eject the target — *then* hand to full-gain True-PN.

### 3.5 The acquisition transient is PN's worst-conditioned moment

Right after lock — track youngest, heading error largest — PN's commanded-g and miss-sensitivity **peak**, and high gain under our >25 ms delay drives divergence. **The launch-to-lock seam is exactly where high gain is most tempting and most dangerous.** Fly it benign; lean on the **frozen template + coast**, not on cranking N.

### 3.6 The single highest-leverage code fix in this dimension

`SeekerGuidancePipeline.__init__` takes `acquisition_box` but **defaults to the full frame `(0,0,W,H)`.** That default **is the bug** — it means "no basket," i.e. the round searches the whole cluttered frame at the worst possible moment. **Wire the operator's console designation into a tight angular basket; refuse to seed the tracker on the full frame.** Also: the pipeline **starts already-locked** with no SEARCH state — add an explicit **ACQUIRE/SEARCH** state running confined-basket detection + benign settle before full gain is allowed.

### 3.7 Failure modes (and the correct response to each)

| Failure mode | Correct response |
|---|---|
| Designation lands at basket edge | Still acquires (gate must prove this) |
| Second hot blob just outside basket | **Never** acquired; basket hard-cap → HARD_LOST/ABORT |
| Lock not achieved within dwell budget | **SELF_SAFE**, not coast-to-brightest |
| Post-commit seeker blink | Bounded inertial-coast on **frozen template**; re-lock requires positive template match; **acquiring a NEW track post-commit is FORBIDDEN** |
| Wrong designation / target jinks out of blind-coast basket | **ABORT** — there is **no datalink, no re-cue** after commit |
| Worst-case initial heading error at transient | Bounded commanded-g, no FOV ejection |

> **Honest ceiling:** the basket is **purely angular** (no range observability), it **degrades exactly when looming/τ degrades** (acquisition 1–3 px, crossing dA/dt→0, impact FOV-saturation), and **P(acquire within dwell) < 1.** The value of this whole dimension is **biasing handover failures toward MISSES, not toward confidently locking the wrong blob.**

---

## 4. SENSOR ROADMAP — Ranked Upgrades Beyond Single-Band 8-Bit

| Rank | Upgrade | What it buys | SWaP / cost | Verdict |
|---|---|---|---|---|
| **1** | **Radiometric 16-bit (Y16) core** | Absolute CFAR threshold; frame-to-frame stability (real temporal/micro-motion features); deletes AGC-bloom + FFC-transient false alarms | **SWaP-neutral**, ~$200–600, EAR-not-ITAR | **ADOPT — highest ROI, not exotic** |
| **2** | **Single-point ToF ranger (terminal-only)** | Makes t_go/ZEM **real**, dimensionally-valid APN, measured-decreasing-range commit gate | **~9–10.5 g, <0.5 W**, ~100 m @10% refl., 10 kHz, <$100 | **ADOPT as designated terminal upgrade, behind a flag** |
| 3 | Dual-band / two-colour | Strong decoy/clutter discriminant | **Cooled FPA = watts, 100s of g, ITAR** | **DO NOT pursue** — SWaP/cost killer; marginal vs a cool electric quad |
| 4 | Event/DVS vision | µs latency, >120 dB DR for high-rate motion | Visible DVS = **night-blind**; thermal DVS doesn't exist at Pi SWaP (FENCE-class; microbolometer ~10 ms τ kills the µs advantage) | **DO NOT adopt** for the night airborne seeker |

### 4.1 Why radiometric is #1 (and it's a self-inflicted wound today)

The FT640's crippling defect is **not resolution — it's the 8-bit AGC.** AGC is a per-frame, scene-content-dependent, history-having nonlinear remap of a 14/16-bit sensor to 256 levels. It **destroys absolute radiometry**, makes the same drone change DN as clutter enters/leaves the FOV, and injects a **global brightness transient at every FFC.** The prior briefs correctly *adapted* (relative-contrast detector, structure-not-graylevel registration) — but that adaptation is **compensating for a self-inflicted wound.** A radiometric Y16 core (Boson-R, Lepton 3.5 radiometric, any Y16 tap) restores a fixed/CFAR threshold, frame stability, and deletes AGC/FFC as false-alarm sources — **same uncooled microbolometer SWaP class.** *Caveat: it buys stability/absoluteness, **not one meter of range**; horizon contrast-inversion still demands the polarity-agnostic relative cue, so keep it as a fallback. A pure-analog CVBS FT640 needs the core replaced to expose a digital Y16 tap.*

### 4.2 The Johnson/NVESD range ceiling — strike "1.1 km" from every budget

Range to a fixed pixel-count is set by **optics, not the core**: `n_px = S / (R · IFOV)`, IFOV = pitch/focal. For a 0.3–0.5 m drone through the FT640's wide lens (~1.3 mrad/px):
- **DETECT (2 px): ~115–190 m**
- **ID-grade (~13 px): ~18–30 m**

The product-page **"1.1 km" is a vehicle/human number and is physically impossible for a small drone** — strike it from every range budget and the COMMIT_GATE. **Aperture/F# is the SNR knob; IFOV is the range knob — never conflate them** (a low F# does NOT buy more pixels on target). Encode the `n_px=S/(R·IFOV)` curve as a first-class number in the sim and gate, and assert the classifier/commit logic **abstains above the physical ID range.**

### 4.3 Why the ToF ranger is the *only* principled closure of the range wall

No pixels, bits, or bands give a passive monocular seeker range. The published architecture is **"angle channel steers, range channel triggers"** — a single-point ToF fused **only in the last seconds.** 2024–26 SWaP has moved: ~9 g, sub-watt, ~100 m, 10 kHz parts now exist. This converts the degenerate-at-impact looming-τ into a **real terminal t_go/ZEM**, re-enables **dimensionally-valid APN**, and supports a **measured-decreasing-range commit decision** — turning the prior briefs' scheduled stand-ins into measured reality. *Caveats: single-point → valid **only when the beam is on target** (centroid wander/off-axis = wrong or no range); honest range falls below 100 m on a small cool low-reflectivity target; it's an **active emitter** (eye-safety/detectability/ECCN); and it gives **nothing in midcourse.** Fuse it into the IMM only inside the ENDGAME window, hysteretic and gated, or it spikes terminal λ̇.*

### 4.4 Fusion rule for any second sensor

Fuse at the **IMM/track level or as a terminal trigger — NEVER at pixel/feature level.** Each sensor keeps an explicit "insufficient/abstain" state. **Re-invest all SWaP saved by skipping DVS/dual-band into kinematic + temporal-rise-time + structure discrimination on the single channel** — none of these upgrades solves bird-vs-drone or raises detection range; those are information-not-on-the-sensor limits.

---

## 5. THE V&V PYRAMID — Seven Gated Rungs To A Safe First Live Intercept

Two rails, both green at every rung, **safety rail dominant**: a perfect sim intercept is **blocked** from props-on if kill latency regressed. Scoring is **asymmetric everywhere: correctly aborted = PASS, wrongly hit = HARD FAIL** (a "hit" by coasting on a stale command against an uninterceptable geometry is a failure even though miss<capture).

| Rung | What it is | Status | Named gap it closes | Gate (concrete) |
|---|---|---|---|---|
| **R0** | Unit/property tests (seeker, IMM, gates, kill-chain) | ✅ exists | Code correctness | ruff+mypy-strict clean; 100% safety-FSM branch coverage; kill-chain invariant property tests |
| **R1** | Pure-software Monte-Carlo (`run_monte_carlo`, Mode A) | ✅ exists (crown jewel) | Guidance robustness, envelope honesty, delay-comp efficacy — **idealized world** | head-on/quartering **p90 miss < capture_radius** at N=3, 30 ms+Smith; **high-crossing aborts >95%**; **zero spurious-near-miss false-positives** |
| **R2** | Pixel-in-the-loop / SIL (Mode B, `thermal_sim.py`) | ✅ exists | Perception→guidance **integration**, AGC/FFC re-normalization — **synthetic imagery** | subpixel centroid <0.1 px; FA-rate vs stars below threshold; threshold re-bases after FFC; lock survives injected coast; Mode B CPA ≈ Mode A |
| **R3** | **HWIL: scene injection into REAL FT640+Pi, loop closed on real silicon** | ❌ **MISSING — biggest hole** | Real compute timing/jitter, OS scheduling, real AGC on real silicon | injected-scene tracker == SIL reference within tol; **p99 closed-loop latency < frame** under thermal-soak with real REACQUIRE in trace; **measured end-to-end latency ≤ value assumed in R1** |
| **R4** | Props-off safety bench (fork V&V-1/2/3 + HW-kill 5.1–5.7) | ✅ specified | **Can it always be stopped?** on real firmware | the exact boolean in `V_AND_V.md §6`; **nothing props-on runs until signed** |
| **R5** | **Captive-carry / shadow-flight (real seeker flying, NO engagement auth)** | ❌ **MISSING — validates R3** | Vibration, soft-mount transfer fn, real ego-motion, real clutter/parallax | ego-residual not read as target maneuver on **real vibration**; soft-mount residual in tol; gyro-only terminal λ̇ clean; shadow-guidance would-have-aborted on right cues |
| **R6** | Tethered, props-on (bolted to load-cell, both kill paths live) | ✅ = B3 | Closed-loop control under **real thrust/vibration** | real latency confirms R3; λ̇-null on real moving warm target under prop vibration; both abort ladders disarm instantly under load |
| **R7** | Live — **F1 non-kinetic** (inert/netted, approach to standoff) → **F2 kinetic** (slow/non-jinking/near-head-on, surveyed footprint) | ✅ = F1/F2 ladder | The real terminal closure | F1: stable terminal λ̇-null + graceful abort + **a logged refuse-to-fire**; F2: all of F1 repeatable + every range-safety condition enforced by `verifier.py` + footprint contains worst-case ballistic drop |

### 5.1 The two missing rungs are exactly the two that close the seeker-physics gap

Today the project jumps from **synthetic pixels (R2) + an open-loop soldering-iron bench (B1)** straight to a **tethered powered airframe (B3).** There is **no rung where the real tracker is proven on a known scene in a closed loop before thrust is added**, and **no rung where real vibration/soft-mount/ego-motion is characterized before the loop is closed under power.** R3 and R5 are **cheap, safe, and precisely where the design doc's own highest-risk items (soft-mount transfer fn, measured latency, gyro-only-under-vibration — all flagged M/H or H/H) get bought down before props spin.**

- **R3 is half-built already:** the `thermal_capture.py` `FrameSource` abstraction (V4L2Source ↔ synthetic source seam) means **electrical frame-injection HWIL is a small real deliverable** — feed recorded/synthetic Y16 into the real Pi runtime and assert real tracker == SIL reference. That single rung closes the *"is the real-silicon runtime faithful to the model we Monte-Carlo'd?"* question that **today has zero evidence.**
- **R5 validates R3:** the published HWIL gold standard is that **real captive-flight seeker recordings are the reference** against which injected-scene fidelity is judged — *reality anchors the chain at the bottom, not the model at the top.* R5 also harvests real clutter/birds to feed **back down** into R1/R2.

### 5.2 Three corrections to the current test posture

1. **`bench_hil.py` is NOT hardware-in-the-loop** despite its name — it's a file-artifact dry-run (no camera/GPIO/UART, hardware flags hardcoded False). It validates the launch-FSM gating logic (valuable) but **calling it HWIL would let the team believe the real-silicon gap is closed when it is not.** Reclassify it as R0-tier SIL launch-logic; build the real R3 separately.
2. **`run_monte_carlo`'s `sensor_delay` is a CONSTANT** — the design doc explicitly warns FFC/AGC delay is **event-driven jitter, not a clean bias.** Add a **per-frame latency-jitter draw** plus randomized `attitude_tau`, drag, mass, `target_step_jink_g` (up to 0.84 g), bearing-noise. Robustness numbers computed with constant delay are **optimistic.**
3. **The back-propagation rule:** any hardware-measured value (R3 latency, R5 vibration) that violates a software-rung assumption **auto-invalidates that rung's stored gate and blocks promotion** until re-run with the measured value. Mechanize it in CI the way `V_AND_V.md` already mechanizes "any rebuild re-runs the props-off suite." **Reality flows back down and re-tightens the model — that is what makes the one live shot an audited consequence, not a hope.**

### 5.3 Where the pyramid physically cannot reach full fidelity (brutal honesty)

- **True IR HWIL is out of budget** (a radiometric scene projector costs orders of magnitude more than the whole craft). Our R3 is an **honest approximation** — frame-injection validates *runtime/timing*, and leans on R5 real recordings to validate *seeker physics*. The seeker-physics gap is closed by **real flight, not a projector we can afford.**
- **The terminal endgame is the least-validatable phase, irreducibly.** τ degenerates, centroid wanders, FOV over-fills in the last fraction of a second — hardest to render in sim, hardest to inject in HWIL, and **captive-carry cannot exercise it without an actual collision.** The first real terminal closure happens at F2 with **residual unmodeled risk** — which is exactly why F2 is gated to a slow/non-jinking/near-head-on target inside the proven envelope, over a surveyed footprint.
- **Passive-monocular has no range/Vc truth**, so the sim's miss-distance ground truth (true 3D geometry) is **richer than anything the real system observes** — the sim can *measure* a miss the interceptor cannot *sense*. **Monte-Carlo capture-volume numbers are an UPPER BOUND on demonstrable performance.** Field miss distance can only be reconstructed post-hoc from **external instrumentation (a second tracking camera / RSO theodolite)** — budget it for R7 or the live miss-distance claim is **unfalsifiable**.
- **Discrimination (bird-vs-drone, hot-clutter pull-off)** the pyramid can shrink but **never close** — domain randomization makes the tracker *robust, not omniscient*; only the self-collected FT640 campaign feeding R2/R5 is real validation.
- **Statistical tail risk survives** even 10⁵ runs (a sun-warmed roof at the exact wrong frame, an FFC at minimum t_go). The pyramid drives the residual toward the **safe side (abort-on-doubt)** — the only honest posture for a single-band passive kinetic round.

---

## 6. SHORTLIST — Top 5 Next Moves, Ordered

1. **Fix the handover basket bug (§3.6).** Replace the full-frame `acquisition_box` default in `SeekerGuidancePipeline` with a **required tight angular basket** from the operator's console designation, and add an explicit **ACQUIRE/SEARCH** state with benign low-gain settling before full PN. *Single highest-leverage software change in this entire brief; near-zero hardware cost; eliminates the dominant acquisition-failure mode.*

2. **Insert R3 (frame-injection HWIL) using the existing `FrameSource` seam (§5.1).** Feed recorded/synthetic Y16 into the real RPi5 runtime, close the loop on real silicon, gate on tracker==SIL-reference + **p99 latency < frame** + **measured latency ≤ R1's assumption.** *Cheap, safe, closes the "is real silicon faithful to the model?" gap that today has zero evidence — and back-propagates the true latency into R1.*

3. **Spec the radiometric Y16 core as the baseline next hardware buy (§4.1).** SWaP-neutral swap that adds an absolute CFAR path and stabilizes temporal/micro-motion features, deleting an entire class of AGC/FFC false-alarm handling. *Confirm EAR-vs-ITAR and the frame-rate ECCN trigger before purchase; keep the relative-contrast cue as fallback.*

4. **Harden the IMM/ego-motion estimator (§2.4–2.6):** add **online gyro scale/bias + cam-IMU time-offset** as augmented states (attacks the DRR parasitic loop of §1.5), publish innovation covariance **S** as lock-quality + search-box, and make **NEES a hard release gate / NIS a live model-wrong alarm.** *Highest value per line of code on the estimation rail; gyro calibration is now formally safety-critical. Strongly prefer hard-mounting the camera.*

5. **Make the Monte-Carlo honest and insert R5 captive-carry (§5.2, §5.1):** add **latency jitter + full parameter randomization** to `run_monte_carlo` and gate on **p90/max + >95% high-crossing abort**; then fly **shadow captive-carry** (propulsion-auth withheld) to measure the real vibration spectrum / soft-mount transfer function and **validate R3 against real recordings** before any props-on test. *These two together turn the first live intercept (F2) into the terminal node of a fully gated chain where every sim-to-real gap component — latency, vibration, soft-mount, AGC/FFC, clutter, ego-motion — was measured on real hardware at a rung where failure costs a log line, not a destroyed craft and a runaway armed quad.*

---

### The bottom line, restated

The brain is more capable than the body. We do not win by making the guidance cleverer — we win by **(a) keeping every command inside the 0.84-g / FOV / ten-tau envelope, (b) never letting an unobservable range estimate touch the PN gain, (c) handing over into a tight basket and flying the seam benign, (d) swapping to honest 16-bit bits and adding the one terminal ranger that makes range real, and (e) proving all of it on a gated ladder where reality — not the model — anchors the bottom rung.** Every "abort" in that chain is a pass, not a failure. That is the only honest path to a first safe live intercept.
