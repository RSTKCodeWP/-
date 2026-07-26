# Guidance-law science base — PN methods, our position, and the actionable improvements

Grounding source: **Sozinov P.A., Gorevich B.N. "Kinematic analysis of proportional navigation methods as
applicable to surface-to-air missile guidance to a ballistic target."** Vestnik Almaz-Antey №2, 2022
(doi:10.38013/2542-0542-2022-2-74-92). Rigorous comparison of 4 PN methods on a maneuvering ballistic
target — from the General Designer of Almaz-Antey. Cross-checked against the open guidance literature
(Zarchan; Shneydor; Shukla & Mahapatra IEEE-1990; Yanushevsky) and the counter-UAS quad-pursuit literature.

---

## 1. The four PN methods (all: `a = Kм · Ω × V`, differ by V)

| Method | V (the vector) | Command ⊥ to | Needs | Optical GSN? |
|---|---|---|---|---|
| **PPN** (pure) | missile velocity **Vp** | **missile velocity** | Ω (LOS rate) + Vp (INS) | ✅ |
| **TPN** (true) | Vp·l_r (speed × LOS unit) | **LOS** | Ω + Vp | ✅ |
| **IPN** (ideal) | closing velocity **Vсбл** | closing velocity | Ω + Vсбл (Doppler) | ❌ |
| **PPN-I** | Vсбл·l_Vp (closing speed × vel unit) | **missile velocity** | Ω + Vp + Vсбл | ❌ |

Quality metrics defined (adopt these): **normal accel Wрн** (maneuver demand, g); **instantaneous miss
h = rотн·sin(φ_h)** (current miss); **miss phase φ_h** = angle(Vсбл, rотн) — φ_h→0 means a parallel-approach
collision course (constant bearing); **characteristic control velocity Vхар.упр = ∫Wрн dt** (control energy).

## 2. Key findings (Almaz-Antey, confirmed independently)

- **Commands ⊥ to the MISSILE VELOCITY (PPN, PPN-I) are preferable.** Commands ⊥ to the LOS / closing
  velocity (TPN, IPN) suffer a **sharp terminal acceleration blow-up** (up to ~25 g in the last 1–2 s) and a
  **rising miss-phase** on a maneuvering target → dynamic error + miss under a real g-limit. PPN/PPN-I stay
  smooth (they transition to parallel-approach). *(Web: GPN also beats TPN — larger capture region, shorter
  intercept.)*
- **PPN is the recommended method for technical realization**: fewest sensed parameters (only Ω + Vp, both
  from GSN + INS), universal (optical AND radar GSN). IPN/PPN-I additionally need Vсбл (Doppler) → degrades
  under jamming, impossible for passive optics.
- **PPN-I is best on quality** (fastest initial-error correction + low peak-g + low Vхар.упр) but needs Vсбл.
- **Kм (nav constant) = 2.5–8**: higher → closer to parallel-approach, lower Vхар.упр, BUT amplifies noise +
  loop instability. Kм is the compromise between accuracy and control energy.
- **A maneuvering target is brutal**: a 6 g target lateral maneuver demands **10–30 g** and **Vхар.упр
  570–800 m/s** from the interceptor. *(Independently confirms our honest envelope: a 0.84 g quad CANNOT
  intercept a maneuvering target; target maneuver shrinks the capture region and raises energy cost.)*

## 3. Where WE are, and what to apply

**Our law (`fpv/guidance/bearing_rate.py`): `a = N·Vc_sched·λ̇`, command ⊥ LOS, Vc scheduled.** That is the
**TPN/IPN family** — exactly the class the paper warns about: terminal acceleration blow-up. This is almost
certainly the mechanism behind our observed **terminal ROE aborts / transient over-demand** in
`launch_and_forget` (the demand spikes past 0.84 g near contact).

Actionable, in priority:

1. **Add a PPN mode (command ⊥ to the airframe velocity vector).** *Tested* (`fpv_ai/bench/pn_law_compare.py`,
   from-below quad, weaving target, 0.84 g wall): PPN demands **~13–15% less g** than our ⊥-LOS law in the
   maneuver-tracking phase (r∈[12,20] m: 8.2→7.1 g at 0.8 g weave) — the paper's direction holds. **BUT** even
   PPN demands ~7–8 g against a 0.8 g maneuver → **both laws saturate the 0.84 g wall; the PLANT, not the law,
   binds.** Honest verdict: PPN is a **cheap refinement** (same sensors, modest terminal benefit, avoids the
   worst ⊥-LOS spikes) — worth adopting, but it is **NOT the fix for maneuvering targets**; more g is. So it
   drops below #2 in priority.
2. **Passive ranging via OWN-MANEUVER + EKF** — the fix for our *fabricated range*. **TESTED**
   (`fpv_ai/bench/passive_range_sim.py` + 6 tests): 6-state relative-motion EKF, bearings-only measurements,
   our own commanded accel as the known input, error measured when range crosses the 40 m commit gate
   (6 seeds). Result:

   | interceptor motion | range err | Vc err | earned parallax | verdict |
   |---|---|---|---|---|
   | straight (CV) | **66%** | 63% | 0° | range **unobservable** |
   | on-course weave, 0.6 g | 36% | 34% | 20° | coarse |
   | on-course weave, 0.84 g (max) | **28%** | 24% | 27° | coarse, best on-course |
   | sustained turn (leaves the intercept) | **17%** | 26% | 45° | best, but off-course |

   **Confirmed**: our own maneuver DOES make range/Vc observable — from unusable (66%) to real (28%). But the
   honest accuracy is **COARSE (~28%), not precise**, and there is a genuine **observability-vs-control
   tension**: the parallax that resolves range is bought by curving off the intercept. A bounded on-course
   weave stays on the intercept and still earns ~27° of parallax; that is the operating point.

   ⚠️ **NEGATIVE finding, and the important one: the EKF's own covariance is a LIAR here.** On the straight
   run the filter's σr collapses to ~12% while its estimate is ~66% wrong — textbook bearings-only *false
   convergence*. **So the commit must NOT be gated on the filter's covariance**: that would replace an
   honestly-fabricated range with a confident-looking fabricated one, which is strictly worse. We gate instead
   on the **parallax actually EARNED by our own maneuver** (known exactly from our own INS, independent of the
   filter): *no maneuver → no range, whatever the filter claims.* Earned parallax is also an honest predictor
   of accuracy (20°→36%, 27°→28%, 45°→17%), which σr is not.
3. **APN with an EKF target-accel estimator** to push the maneuver envelope. We have the IMM maneuver mode;
   add a properly-estimated target-lateral-accel term (AEKF, e.g. RG-2015; TAPN needs no target-accel
   knowledge) capped to the g-budget. Extends the ~0.2 g target-weave boundary we measured.
4. **Adopt the paper's metrics** as live cues: **φ_h (miss phase)** as a terminal/commit indicator (φ_h→0 =
   on collision course → the honest COMMITTED trigger, replacing fabricated range); **h** (current miss) and
   **Vхар.упр** (control-energy) as envelope diagnostics (Vхар.упр climbing = near the g-wall).
5. **Kм/N as an explicit adaptive lever** (validated 2.5–8), scheduled by geometry/noise — we already blend N.

## 4. Science base by area (independently gathered)

- **PN theory / comparison**: Zarchan *Tactical and Strategic Missile Guidance* (AIAA, the bible); Shneydor
  *Missile Guidance and Pursuit* (1998); Shukla & Mahapatra "The PN Dilemma — Pure or True?" (IEEE T-AES
  1990); Yanushevsky *Modern Missile Guidance* (CRC 2007); Sozinov & Gorevich 2022 (this paper).
- **APN / optimal guidance (maneuvering targets)**: APN = PN + target-accel compensation; MAPN/AEKF target
  maneuver estimation; optimal guidance = linear-quadratic optimal control (OGL); "Capturability of Augmented
  PPN vs time-varying maneuvers" (JGCD); TAPN (no target-accel knowledge). RL meta-learning for LOS curvature
  (arXiv 2205.00085) — a modern data-driven guidance branch.
- **Passive ranging / bearings-only (our core sensor gap)**: monocular vision has an *observability* hole
  (3D→2D, no range from bearing) → solved by observer maneuver + EKF. Daugherty 2019 (monocular passive
  ranging for UAS detect-and-avoid); "Observability Enhancement of Maneuvering Target w/ Bearings-Only"
  (AIAA G003003); Ning et al 2024 bearing-angle target motion analysis from visual measurements; UAV
  monocular-vision aerial-target tracking (Control Eng. Practice 2013).
- **Counter-UAS quad interceptor (our platform)**: PN is the standard for C-UAS multirotor pursuit — low
  compute, reliable; "Quadrotor Guidance for Targeting Aerial Objects" (arXiv 2107.01733); "Evaluation of PN
  for Multirotor Pursuit" (2020). Visual-based terminal guidance is the field norm.

## 5. What passive ranging actually buys us (and what it does not)

**Buys:** a *measured* closing speed (~24-34% error) replacing today's hardcoded `Vc_sched_mps=40`, which is
open-loop wrong whenever the real geometry differs; a real (coarse) range/t_go for a commit cue; and an
honest, physically-grounded trust gate that the machine can evaluate in flight.

**Does not buy:** precise terminal range. At ~28% a 40 m gate fires somewhere in 29-51 m, and t_go compounds
range and Vc error to ~35-40%. This is a *coarse cue*, adequate for a commit gate, **not** adequate for a
precision terminal fuze — which is fine, because we are body-to-body with no warhead and therefore need a
contact, not a burst point.

**Design rule extracted:** never let an estimator's self-reported confidence authorize a commit. Authorize on
an *independently observable physical precondition* (here: earned parallax from our own INS). This is the same
principle as the two-press human authority — authority comes from outside the estimator.

## 6. What wiring it into the live chain actually found (2026-07-19)

Feeding the passive range into the commit gate produced **no change at all** — and chasing why turned up two
defects that mattered far more than the range work itself.

**Passive range arrives too late on our geometry, for a fundamental reason.** Earned parallax stayed under the
gate until ~10 m. The interceptor barely moves across the LOS because **PN drives toward constant bearing —
which is precisely the trajectory that makes range unobservable. The better the intercept, the less parallax
it earns.** Passive ranging therefore requires a *deliberate* observability maneuver; the natural intercept
maneuver is not enough. That is the observability-vs-control tension in its sharpest form.

**Defect 1 — the g-envelope ROE abort fired on a SINGLE tick.** A transient demand spike (3.53 → 2.80 → 2.31 g,
decaying) ended engagements at ~1.2 s while the target was still ~100 m out. Because the abort is disabled
post-commit by design, it also **deadlocked the commit**: the abort prevented the commit that would have
disabled the abort. Continuing through a transient is safe — the command clamp already saturates at max-g, so
the airframe does its best either way. Fixed with a **leaky accumulator** (`envelope_abort_persist_ticks=25`;
over-demand ticks add, in-envelope ticks drain). A consecutive-run counter would *not* have worked: the
observed spikes were intermittent, so it would reset on every good frame and never fire. `0` restores the old
behaviour exactly.

**Defect 2 — a wrong assumed target span silently scales the range.** Subtense range is
`f · assumed_span / extent_px`. The harness rendered a 2 m target while the runtime assumed 4 m, so measured
range read **~2× truth** — bottoming out near 100 m while the true CPA was 1.4 m — and the 50 m commit gate
therefore never fired. Nothing anywhere in the system noticed. In flight the true span of an unknown winged
UAV is genuinely unknown, so **this error class is unavoidable for subtense** — which is the whole case for
the size-free passive range, independent of the fact that it did not help *here*.

Formal `COMMITTED`, across 5 seeds: **1/5** originally → 2/5 with the abort persistence alone → 3/5 with the
span fix alone → **4/5 with both**. The remaining seed is reported honestly rather than tuned away.

**⚠️ And the abort persistence ships OFF BY DEFAULT — the reason matters more than the fix.** Enabling it
makes the head-on closed-loop miss **~2× worse on 6 of 6 seeds** (0.66→1.34, 0.84→2.67, 1.60→2.76,
0.49→1.60, 0.49→1.28, 0.72→1.32 m against a 0.75 m capture radius). Systematic, not seed noise.

**Mechanism, measured rather than assumed.** The closed loop's abort response **zeroes the lateral command**.
Riding through the over-demand instead applies the **clamped** command, which pins the airframe at saturated
bank **8× longer** (100 vs 12 ticks above 0.9 roll). On a **strapdown** seeker that is self-harming: full
bank tilts the camera and corrupts the very λ̇ the guidance depends on — the same maneuver↔seeker coupling
that made a gimbal win by 9× in the honest 3D sim. Thrust is also diverted off the closing axis.

**A correction to what was first written here.** The initial explanation was a *terminal blow-up of our ⊥LOS
law* — it fit the theory in §2 and was written up before it was checked. **The data refutes it:** with
persistence the terminal is **calmer**, not wilder (max |λ̇| 0.044 vs 0.127 rad/s; max |a_cmd| 3.6 vs
5.0 m/s²). The damage comes from sustained **saturation**, and it is not specific to the terminal. So this
episode is *not* evidence for PPN — PPN's standing remains what §3.1 measured. It is evidence for two other
things: an explicit **over-demand policy** ("if the demand is unreachable, do not fly a saturated version of
it" — currently a side effect of aborting rather than a designed behaviour), and another data point that our
binding coupling is **strapdown attitude ↔ seeker**, not the law family.

**The correction this forces on the 2026-07-18 "launch-and-forget proven" claim:** guidance was authorized
only 0.14–1.20 s; the mission ABORTED at 1.22 s and the recorded hit was a **post-abort ballistic coast** on
the collision course PN had already established. The authorization chain (two presses → AI_ACTIVE, no hit
without it) was and remains real; the *guided, committed terminal* was not. With both defects fixed it now
closes on 4/5 seeds.

## 7. Bottom line — Наука во главе
The rigorous Almaz-Antey analysis + the open literature independently **confirm two of our honest walls**
(a low-g plant can't intercept a maneuvering target; passive optics can't measure Vс/range). We then TESTED
the PPN idea on our own geometry and got an honest, tempering result: **PPN is a modest refinement (~13–15%
lower demand), but our envelope is PLANT-limited — both laws saturate the 0.84 g wall under any real maneuver,
so PPN alone won't widen the envelope.** Re-prioritised: the **real lever with no new hardware is passive
ranging by own-maneuver + EKF** (→ true-Vc PN + a real range/t_go → formal COMMITTED, fixing the fabricated
range), with **φ_h** as the honest commit cue and **Vхар.упр** as the energy/envelope budget. PPN is worth
adopting as a cheap refinement, but the maneuver envelope is bought with G (airframe), not with a better law.
The sim CORRECTED the paper's enthusiasm for our specific g-limited quad — that is Наука во главе.

Passive ranging was then tested too, and it landed the same way: **the idea works but is coarser than hoped**
(66% → 28% range), it costs intercept geometry to get parallax, and — the finding that matters most — **the
EKF confidently lies exactly when it is most wrong**, so the commit is gated on earned parallax, not on the
filter. Two of the three "big unlocks" from the literature came back tempered by our own geometry. That is
the process working: we now have measured numbers with error bars where we previously had a schedule and a
hope, and we know precisely which of them we are allowed to trust.
