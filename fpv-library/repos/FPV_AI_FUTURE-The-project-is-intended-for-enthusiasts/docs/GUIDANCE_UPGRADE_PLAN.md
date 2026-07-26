<!-- Implementation plan distilled from three guidance papers, filtered through our own measurements. -->

# Guidance upgrade plan — what three papers give us, and what to build

Sources, all read in full:

1. **Palumbo, Blaukamp & Lloyd, "Modern Homing Missile Guidance Theory and Techniques"**, JHU APL Technical
   Digest 29(1), 2010. Derives PN, APN, EPN, OGL from LQ optimal control; quantifies autopilot-lag and
   target-maneuver sensitivity.
2. **Li Kebo, Zhang Taotao & Chen Lei, "Ideal proportional navigation for exoatmospheric interception"**,
   Chinese J. Aeronautics 26(4), 2013, 976–985. 3D IPN in the instantaneous LOS-rotation plane; capture
   regions under **bounded** acceleration by phase-plane analysis.
3. **Sozinov & Gorevich (Almaz-Antey, 2022)** — already analysed in `GUIDANCE_LAW_SCIENCE.md`.

**The filter applied to all of it:** we do not adopt a technique because a paper is authoritative. Everything
below is ranked by whether it attacks a wall **we have measured on our own hardware/geometry**. Section 5
lists what these papers offer that does *not* transfer to us, and why.

---

## 1. The one finding that matters most: we correct too late and too hard

Our own measurement (2026-07-19): flying a **saturated** lateral command is ~2× worse than flying none, on
6 of 6 seeds, because it pins the airframe at full bank and — on a strapdown seeker — corrupts the λ̇ the
guidance is steering on. We had no explanation for *why the demand gets that large in the first place.*

All three papers answer it, and they agree:

- **Palumbo Fig. 9** — against a maneuvering threat, PN needs **27 g and ΔV = 1356 m/s**; APN needs **3.7 g,
  309 m/s**; EPN **3.2 g, 236 m/s**. Same intercept. The advanced laws command **earlier and far less**.
  PN's demand *grows* through the engagement (Fig. 7, solid lines); APN's *decays*.
- **Sozinov-Gorevich** — the same quantity, `Vхар.упр = ∫|W| dt`, is their headline discriminator.
- **Li et al. Figs. 8/11/14** — IPN drives the LOS rate ω_s to zero **faster** than TPN, so less is left to
  correct late.

**Diagnosis for our system:** our law `a = N·Vc·λ̇` is PN — derived assuming a *non-maneuvering target* and an
*instantaneous airframe*. Both assumptions are false for us. It therefore under-corrects early, and the error
it fails to remove early arrives as an impossible demand late — which we then saturate, which corrupts the
seeker, which is exactly the failure we measured.

**This reframes our open item.** We wrote it up as "we need an over-demand policy" (a way to fail better).
The papers say the real fix is upstream: **stop generating the late demand.**

---

## 2. Our numbers, against Palumbo's sensitivity curves

Our effective loop lag: `attitude_tau 0.10 s + sensor_delay 0.030 s + loop_delay 0.010 s ≈ 0.14 s`
(`quad_sim.py:211-215`). PN assumes **zero**.

Palumbo Fig. 6c (miss vs target maneuver, by autopilot τ): at τ = 0.1 s miss is nearly insensitive to target
maneuver; by τ = 0.5 s it blows up. We sit at **τ ≈ 0.14 s** — degraded, not yet catastrophic.

But the quantity that matters is **t_go / τ**, and it is small exactly where we lose. With τ = 0.14 s, the
last `5τ ≈ 0.7 s` is the region where the zero-lag assumption fails hardest. Closing at ~35 m/s that is the
**final ~25 m** — precisely where our CPA lands (1.15–1.48 m against a 1.5 m contact radius). **Our entire
margin lives inside the region where our guidance law's core assumption is invalid.**

### The independent confirmation of a number we measured
Palumbo Fig. 7 gives the classical **"3-to-1 rule"**: PN with N = 3 requires ~**3× the target's** acceleration
capability to intercept. Our plant ceiling is **0.84 g** → the largest target maneuver PN can handle is
**0.28 g**. The project independently measured the "reliably killable ceiling" at **~0.28 g** by seed sweeps,
months before reading this paper. Theory and our simulation agree exactly. That is a strong signal that our
envelope numbers are real, and that the wall is structural rather than a tuning artefact.

---

## 3. Build list (ranked by our measured constraints)

### 3.1 ZEM formulation with airframe-lag compensation — **HIGHEST VALUE**

Rewrite the guidance command in **Zero-Effort Miss** form, which unifies every law in Palumbo as
`a_cmd = N̄ · ZEM / t_go²`:

| Law | ZEM | Assumes |
|---|---|---|
| PN (ours) | `r + v·t_go` | non-maneuvering target, **instant airframe** |
| APN | `ZEM_PN + ½·a_T·t_go²` | constant target accel, instant airframe |
| **OGL** | `ZEM_APN − τ²(t_go/τ + e^(−t_go/τ) − 1)·a_M` | constant target accel, **first-order airframe lag τ** |

The OGL term subtracts **the acceleration already commanded but not yet delivered by the airframe**. That is
literally a term that says *"do not keep piling on demand while the aircraft is still catching up"* — the
designed version of the behaviour our measurement stumbled into. `a_M` is available: we command it, and the
FC gives us measured accel.

Implement as an explicit `ZemGuidance` alongside `bearing_rate`, selectable by config, default OFF, then
measure PN vs APN vs OGL on our own geometry the way we measured PPN. **Success criterion: peak demanded g
and time-at-saturation both fall.** Miss distance is the outcome, saturation time is the mechanism.

### 3.2 Honest t_go and an honest commit cue — **HIGH VALUE, small**

Everything in §3.1 needs `t_go`, and we currently do not have an honest one (ours derives from subtense
range, which inherits the target-size assumption that already burned us).

Palumbo eq. 44: `t_go = −(r·v)/(v·v)` — time to **CPA**, exact for non-accelerating bodies, and correct where
the naive `R/Ṙ` (eq. 41) is biased.

Palumbo eq. 45: `r_CPA = [(v × r) × v]/(v·v)` — the **instantaneous miss vector**. Note this is the same
quantity Sozinov-Gorevich call the miss phase `φ_h`, arrived at independently.

> **Correction to the first draft of this section.** It claimed `r_CPA`'s direction is "scale-invariant, so a
> passive seeker can use it without absolute range". Half right, and the wrong half matters. `φ_h` and the
> normalized miss `|r_CPA|/R = sin φ_h` **are** invariant to the range scale — they are angles between
> directions — **but the direction of the relative velocity `v` is not passively observable either**, so the
> formula as written is not usable from bearings alone. Caught by checking before building on it.

**What actually works, verified numerically to 0.01° on three geometries:**

```
φ_h = atan(λ̇ · t_go)          exact for t_go = R / Vc
```

`λ̇` is the **LOS rate — the seeker's primary measurement**, which we have directly and well. So the miss
phase needs only `λ̇` and a `t_go`, not the full relative state. The error is benign too: a 28 % error in
`t_go` gives ~28 % in `φ_h` at small angles — far more forgiving than needing metric range.

Three cues that degrade gracefully into each other:

| cue | needs | availability |
|---|---|---|
| **`λ̇ → 0`** (constant bearing = collision course) | nothing but the seeker | **range-free, always** |
| **`φ_h = atan(λ̇ · t_go)`** | `λ̇` + any `t_go` | inherits the range estimate's error |
| `r_CPA` exact (eq. 45) | full relative state `r`, `v` | only when an estimator supplies it |

Adopt these as the **commit cue**, replacing the range threshold that the target-span bug silently disabled.
The range-free `λ̇` cue is the important one: it is the only commit evidence a purely passive seeker can
produce without borrowing an assumption from somewhere else.

### 3.3 Guidance in the LOS-rotation plane (IRPL) — **HIGH VALUE, attacks our binding coupling**

Li et al. §2: decompose 3D relative motion into (i) planar motion inside the **instantaneous LOS rotation
plane** and (ii) rotation of that plane. They prove `r` and `ω_s` are **not coupled** to the plane's own
rotation `Ω_s`, and that the coupling term is negligible (their eqs. 24–26). So a 2D law built in the IRPL
**is** a valid 3D law.

Why this matters for us specifically: we currently split guidance into **az/el in the camera frame**. On a
strapdown seeker the camera frame **rolls with the airframe** — so our guidance axes rotate exactly when the
aircraft banks hard, which is the condition we measured as damaging. The IRPL is defined by the LOS and its
rotation — **independent of body attitude**. Guidance formulated there is structurally immune to the
attitude↔seeker coupling that is our measured binding constraint.

This is the deepest of the three ideas and the one most specific to our failure mode.

### 3.4 APN with a gated target-acceleration estimate — **MEDIUM, with a hard caveat**

Palumbo Fig. 7: at N = 3 APN needs about **half** the acceleration PN needs against a hard-turning target.
Naively that doubles our maneuver envelope: 0.28 g → ~0.5 g of target weave.

**The caveat is explicit in the paper and it lands squarely on us:** APN needs a target-acceleration estimate,
which from a position-only (pseudo) measurement is noisy — *"if sensor quality is insufficient... the guidance
law could actually be worse than if we just used PN."* Our passive monocular seeker is precisely the
insufficient-quality case, and our own passive-range work already showed the estimator will **falsely
converge** rather than admit it does not know.

So: implement APN, but gate the `a_T` term on an **independently earned** quality precondition, exactly as we
gated passive range on earned parallax rather than on filter covariance. Never on the filter's own confidence.

### 3.5 Capture region under bounded acceleration — **MEDIUM, replaces seed sweeps with proof**

Li et al. §4 computes capture regions by phase-plane analysis **with the acceleration saturated at a_max**
(their eq. 36) — which is our exact situation (0.84 g hard wall). Their result: IPN's bounded capture region
is substantially larger than TPN's, for both maneuvering and non-maneuvering targets.

We currently characterise our envelope by sweeping seeds and reporting hit/miss. A phase-plane capture region
would give us **the boundary itself**, as a curve, for a stated a_max. That is a far stronger and more
honest way to state our envelope to an outside reviewer than "hit on 4 of 5 seeds".

---

## 4. Priority order

1. **§3.2 honest t_go + φ_h commit cue** — small, unblocks §3.1, and fixes a cue we know is broken.
2. **§3.1 ZEM/OGL with lag compensation** — attacks the measured mechanism (late saturated demand) at its source.
3. **§3.3 IRPL frame** — attacks the measured binding coupling (attitude ↔ strapdown seeker).
4. **§3.5 capture region** — turns our envelope claim into a proof.
5. **§3.4 APN** — real envelope gain, but gated behind estimate quality; do it after the estimator story is solid.

Each step follows the house rule: **build it OFF by default, measure it on our own geometry, and report the
result even when it contradicts the paper.** PPN and passive ranging both came back tempered that way.

---

## 5. What does NOT transfer (stated so nobody re-derives it later)

- **IPN's LOS-axis acceleration component** (`N·r·ω_s²` along `e_r`, Li eq. 35). Exoatmospheric interceptors
  have a dedicated longitudinal thruster. A quad's thrust is rigidly tied to its attitude, so we cannot
  command along-LOS acceleration independently of the lateral command. **The IPN *law* is largely unavailable
  to us; the IRPL *framework* (§3.3) is the part we can use.**
- **Exoatmospheric scaling.** Li et al. operate at 3–5 km/s over hundreds of km with 8 g interceptors. Our
  numbers are 30 m/s, ~150 m, 0.84 g. Their *structural* results (capture-region topology, IRPL decoupling)
  are scale-free; their *numeric* results are not.
- **EPN (constant-jerk target).** Palumbo derives it for boost-phase ballistic threats. A weakly-maneuvering
  winged UAV does not have a meaningful constant-jerk phase, and each added derivative costs estimator
  quality we do not have.
- **The LQ derivation machinery itself** (Riccati, matrix-exponential solutions). Valuable for understanding
  *why* the laws take the form they do; we consume the resulting closed-form laws, we do not need to re-derive
  them onboard.

---

## 6. Verdict

These three papers do not hand us a way past our physics walls. **The 0.84 g plant and the passive-only
sensor stay exactly where they were**, and Palumbo's 3-to-1 rule independently confirms the 0.28 g target-
maneuver ceiling we had already measured.

What they *do* give is the explanation for a defect we found empirically and could not account for, plus the
designed fix for it. We measured that we correct too late and too hard; they show that this is the *expected*
consequence of using a guidance law derived under two assumptions we violate (instant airframe, non-maneuvering
target), and they provide the corrections — ZEM with lag compensation, and a guidance frame that does not
rotate with the airframe.

That is a real gain and it is aimed exactly at where our margin is thinnest: **the last 25 m, where our CPA of
1.15–1.48 m is fighting a 1.5 m contact radius.** We are not trying to widen the envelope here. We are trying
to stop losing intercepts we are already inside.
