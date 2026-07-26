> **[HISTORICAL]** — status as of 2026-07-19. 2026-06-19 spec, as built in June.
>
> **`docs/CHECKPOINT.md` is the source of truth.** Where this document disagrees with it, CHECKPOINT wins.

<!-- Block-03 TASK #1 implementation TZ -- dependency-ordered, code-grounded. Authored 2026-06-19. -->

# TASK #1 — IMPLEMENTATION TZ (master spec + per-task cluster specs)

## MASTER SPEC

All five load-bearing facts are confirmed against the code:

- **`geometry.py:148` already has `bearing_to_pixel`** — R1's "honest gap #1" (the missing inverse primitive) is resolved; no new primitive needed, just sign-convention matching.
- **Pipeline seam confirmed**: `tracker.update()` at the top (so IMM coast must use `_last_imm`), `set_search_radius` fed for next frame, `command_from_guidance` called WITHOUT `estimated_tau_s` (R3's dead-code gap), `engage_permitted = not model_wrong_alarm` already wired.
- **`area_extended_px` is hard-zeroed except top-3** (`detect.py:475,484,488`) — R4's top-K fallback is real.
- **MTI `_register` discards `hmat`** (returns warped frame only) — R5's "expose homography" change is real.
- **`_DelayBuffer` is fixed-delay, `target_step_jink_g` exists but is never swept** — V2's gaps confirmed.

Test count didn't print (pytest collect was quiet), but the 343 figure is stated authoritatively in the brief. I have everything needed to write the master TZ.

---

# MASTER IMPLEMENTATION TZ — Task-1 Campaign (Block-03 Thermal FPV Interceptor)

**Document owner:** Chief Architect · **Date:** 2026-06-19 · **Drives:** the build · **Baseline:** 343 tests green (S1/S2/S3 closed-loop)

---

## 1. Executive Plan

We are wiring and extending the passive monocular LWIR seeker so the LOS-rate-nulling interceptor survives the *terminal* phase against a maneuvering winged UAV in clutter — without ever letting range touch the guidance gain or letting appearance touch the LOS. The campaign has three substantive layers stacked on a verification spine: **Tier-0** lands estimator hardening that *already exists in `imm.py`* but is unwired (R1 coast/gate/lock-score, R2 robust λ̇, R3 τ-driven terminal timing); **Tier-1** closes the biggest perception gaps (R4 regime machine, R5 silhouette-aimpoint migration, R6 AGC-invariant event-λ̇, R7 intensity∧motion consensus + clutter carry); **Tier-2** adds the correlation/soft-association suite (R8 MOSSE+DSST, R9 anticipatory pre-warp, R10 JPDA), and a **V&M** layer (V1/A1 ACQUIRE, V2/A5 honest Monte-Carlo, V3 scenario library, V4 doctrine matrix, V5 hardware measurement) that exists only to *prove* the above. The staging philosophy is **software-first, verify-each-stage, keep-343-green**: every guidance-path change ships behind a `default-off` config flag whose OFF state is provably bit-identical to today, so each stage closes on a green gate before the next opens, and the expensive closed-loop S3 acceptance is run *once per stage* on the intended-on combination rather than per-task. The orchestration model is honest about its limits: agents do **not** free-chat — they coordinate through (a) this **shared TZ** as the single source of truth, (b) a **dependency DAG** that serializes the four files every task collides on (`pipeline.py`, `track.py`, `imm.py`, `bearing_rate.py`), and (c) **adversarial-review gates** where a strong model reviews every centroid/LOS/gain-touching diff against the doctrine matrix before merge. Where the science is genuinely incomplete, we do not pretend otherwise — two renderer assets and one hardware measurement campaign (V5) are called out as hard prerequisites for three headline acceptance numbers, and those numbers are gated, not assumed.

---

## 2. Master Task Table

> **Executor legend:** S = Sonnet (bounded/mechanical/parallel), ★ = strong model (subtle correctness, integration, safety review). **S3?** = does this change the closed-loop guidance path and force a slow-S3 re-run. **Off?** = ships behind a default-off flag whose OFF state is bit-identical to today.

| ID | One-line goal | Primary files | Depends-on | Shares-files-with (conflict) | S3? | Off? | Exec | Bench scenario |
|----|---------------|---------------|-----------|------------------------------|-----|------|------|----------------|
| **V4** | 7 doctrine invariants as executable CI gate | `tests/test_doctrine_invariants.py` (new) | — | none (new file) | no | n/a | ★ | Mode-A micro-engagements |
| **A1/V1** | ACQUIRE low-gain settle before full N | `bearing_rate.py`, `test_s3_acceptance.py` | — | **R3** (same N code+test), V2 (test file) | **yes** | yes (`acquire_settle_ticks=0`) | ★ | HEAD_ON 5/10/15 m/s |
| **A5/V2** | Per-frame latency jitter + swept step-jink MC | `closed_loop.py`, `quad_sim.py`, `test_s3_acceptance.py` | — | V1/V3 (test file), `_DelayBuffer` | **yes** (timing) | yes (`jitter_s=0`) | ★ | HEAD_ON + jink sweep |
| **R1** | IMM mixed-state coast + gate_sigma + lock-score peak-delete | `track.py`, `pipeline.py` | — (uses emitted IMM) | **R3/R4/R5/R7/R8/R10** (track.py+pipeline) | **yes** | yes (`use_imm_coast`, `use_peak_relative_deletion`) | ★ | step-jink-then-dropout replay |
| **R2** | NIS-scheduled λ̇ smooth + Huber clip + R-extent inflate | `imm.py`, `bearing_rate.py` | — (soft: V5 for thresholds) | R6 (imm.update sig), R3 (bearing_rate) | **yes** | yes (`nis_lambda_smoothing`, `huber_enabled`, `r_extent_k=0`) | ★ | glint-spike + step-jink (A5 harness) |
| **R3** | τ-driven terminal/acro + falcon-low N=2.6 | `command_map.py`, `pipeline.py`, `bearing_rate.py` | soft R2 | **R1** (pipeline seam), **A1** (N code), R5/R6/R7 (pipeline) | **yes** | yes (`use_tau_terminal`; N=2.6 opt-in) | ★ (N-option+wiring = S) | closing-geometry, varied closure |
| **R4** | REGIME FSM POINT→RESOLVED→FILL, hysteretic | `track.py`, `pipeline.py` | — | **R1/R5/R7/R8/R10** (track.py+snapshot) | no | yes (`regime_enabled=False`) | **S** | scale-sweep σ-ramp (V3-s1) |
| **R5** | Aimpoint migration: hotspot→MTI-silhouette centroid | `aimpoint.py` (new), `mti.py`, `pipeline.py` | **R4** | **R1/R2/R6/R7** (pipeline `los.update`), `mti.py` | **yes** | yes (`aimpoint_migration=False`) | ★ | aspect-sweep 0–90° (V3-s4, **renderer-blocked**) |
| **R6** | Synthetic-event log-contrast λ̇ → IMM measurement | `event_channel.py`+`derotate.py` (new), `imm.py`, `pipeline.py` | `derotate.py` refactor | R7 (pipeline flag block), R2 (imm.update sig) | **yes** | yes (`event_channel=False`) | ★ | AGC-sweep + background-march (V3-s3) |
| **R7** | Intensity∧motion consensus before LOCKED + 2-hyp carry | `track.py`, `track_manager.py`, `pipeline.py` | soft R6 (pipeline merge) | **R1/R4/R5/R8/R10** (track.py), R6 (pipeline) | **yes** (timing) | yes (`require_consensus_for_lock=False`) | ★ | horizon-crossing + hidden jink (V3-s2) |
| **R8** | MOSSE+DSST correlation in-gate; PSR/APCE→lock-quality | `correlation.py` (new), `track.py`, `pipeline.py` | **R1** (lock-score), soft **R4** | R9 (correlation.py), R1/R4/R5/R7/R10 (track.py) | **yes** (latency+proof) | yes (`correlation=False`) | ★ | closing seq; **latency_hwil profile gate** |
| **R9** | Anticipatory template pre-warp exp(Δt/τ)+aspect affine | `correlation.py` | **R8**, **R3** (τ guard) | R8 only (correlation.py) | **yes** (proof) | yes (`prewarp_enable=False`) | ★ | scale-sweep (affine **renderer-blocked**) |
| **R10** | JPDA soft-update when gate occupancy >1.2 | `track.py`, `pipeline.py` | **R1** (innovation cov) | R1/R4/R5/R7/R8 (track.py) | **yes** (centroid!) | yes (`jpda=False`) | ★ | clutter-crossing distractor (V3-s2 variant) |
| **V3** | 4-scenario sim library w/ baseline metrics | 4 new test files; `thermal_sim.py` ext | — (read thermal_sim first) | `ThermalSceneConfig` w/ R6 | no | n/a (new tests) | S (+★ for sim ext) | all four perception scenarios |
| **V5** | HW: cam↔IMU time-sync + field NETD/clutter PDF | `timesync_bench.py`, `field_noise_bench.py` (new), `PI_BRINGUP.md` | **hardware** | none | no | n/a | ★ (human executes) | physical RPi5+FT640+IMU rig |
| **R11/R12** | ToF endgame gate / frame+event front-end | (out of Task-1 scope) | hardware | — | — | — | — | deferred to Tier-3 |

---

## 3. Dependency DAG + STAGED Execution Order

```
        ┌─────────────────────────────────────────── STAGE 0 (foundation, no merge risk) ───┐
        │  V4 doctrine matrix      V3 scenario library      [read thermal_sim.py]            │
        │  derotate.py refactor (char-test: LOS bit-identical)                               │
        └────────────────────────────────────────────────────────────────────────────────┬─┘
                                                                                           │
   ┌──────────────── STAGE 1 (Tier-0 estimator, serial on shared files) ──────────────────▼─┐
   │  R1 ──(track.py, pipeline 227-255)──►  R2 ‖ (imm.py+bearing_rate, disjoint)             │
   │              └───────────────────────► R3 (pipeline 278-281, command_map)               │
   │  A1/V1 ──(bearing_rate N)── MUST land WITH or BEFORE R3 (same N lines 438-439)          │
   │  A5/V2 ‖ (closed_loop/quad_sim, disjoint from R1/R2/R3)                                  │
   └────────────────────────────────────────────────────────────────────────────────────┬──┘
                                                                                          │
   ┌──────────────── STAGE 2 (Tier-1 perception) ────────────────────────────────────────▼─┐
   │  R4 ──(track.py regime)──► R5 (aimpoint, needs regime + pipeline los.update)            │
   │  R6 ‖ (event_channel→imm)        R7 ‖ (consensus, track.py+pipeline)                     │
   │  R5/R6/R7 all touch pipeline.step → SERIALIZE pipeline edits, parallel-develop bodies   │
   └────────────────────────────────────────────────────────────────────────────────────┬──┘
                                                                                          │
   ┌──────────────── STAGE 3 (Tier-2 correlation/soft-assoc) ────────────────────────────▼─┐
   │  R8 ──(correlation.py)──► R9 (pre-warp, same module)                                    │
   │  R10 ‖ (JPDA, track.py — needs R1 cov, NOT R8)                                          │
   └────────────────────────────────────────────────────────────────────────────────────┬──┘
                                                                                          │
   ┌──────────────── STAGE 4 (hardware, async) ──────────────────────────────────────────▼─┐
   │  V5 measurement → re-tunes V2 jitter band + R2 Huber threshold (feedback, not blocking) │
   └─────────────────────────────────────────────────────────────────────────────────────┘
```

### Stage-by-stage detail

| Stage | Tasks | Run mode | Worktree-disjoint? | Verification gate that CLOSES the stage | Effort |
|-------|-------|----------|--------------------|-----------------------------------------|--------|
| **0 — Foundation** | V4, V3, `derotate.py` refactor, *read `thermal_sim.py`* | **Parallel** | **Yes** — all new files + a pure refactor. V4/V3 are new test files; `derotate.py` is extracted from `los.py:273-286`. | Full suite green **incl. derotate char-test proving LOS output bit-identical before/after refactor**. V4 must be 100% green (it's the CI gate for every later stage). No S3 needed (no guidance change). | ~Low. Highest-leverage stage: land first so every later PR is doctrine-checked. |
| **1 — Tier-0 estimator** | R1 → {R2 ‖ R3}; A1 with/before R3; A5 ‖ | **R1 serial, then R2 ‖ A5 parallel; R3 after R1; A1 fused with R3** | **Partial.** R2 (`imm.py`+`bearing_rate.py`) and A5 (`closed_loop.py`+`quad_sim.py`) are file-disjoint from R1 (`track.py`+`pipeline.py`) → safe parallel worktrees. R3 shares `pipeline.py` seam (278-281) with R1 (227-255) and shares N-lines (438-439) with A1 → **serialize R1→R3, fuse A1+R3**. | **ONE slow-S3 run** with R1+R2+R3+A1 flags all ON + A5's new gates. Must show: 343 still green with all flags OFF; with-on combination passes Gates I/J/K/L/M + new Gate N (acquire), Gate O (jitter). | ~High. The estimator core. The single S3 re-run is the gate. |
| **2 — Tier-1 perception** | R4 → R5; R6 ‖ R7 | **R4 serial → R5; R6 ‖ R7 develop in parallel, pipeline.step edits serialized** | **Mostly.** R6 lives in new `event_channel.py`/`derotate.py` + `imm.py` measurement kwarg → disjoint from R4/R5/R7 *bodies*. **But R4/R5/R7 all edit `track.py`/`pipeline.step`** → not worktree-safe in parallel; serialize the shared-file hunks (additive methods/fields). | **ONE slow-S3 run** with R5/R6/R7 on (R4 alone needs no S3 — adds an unread field). Plus V3-s1 (regime monotone), V3-s3 (event-λ̇ ≥30%), V3-s2 (consensus 0-swap). **R5's aspect metric is renderer-gated → unit-test on synthetic masks, defer the 0.2° acceptance.** | ~High. R5 is the highest-risk single task (changes LOS spine). |
| **3 — Tier-2 corr/soft** | R8 → R9; R10 ‖ | **R8 serial → R9 (same module); R10 parallel** | **R9 disjoint** (only `correlation.py`, shared with R8 → serialize). **R10 shares `track.py`** with R8 → serialize the track.py hunks. R10 is independent of R8 functionally. | **ONE slow-S3 run** with R8+R9+R10 on. **R8 adds a hard latency gate**: `latency_hwil.py --correlation` p99 < 16.6 ms on Pi5. R10 changes the centroid → its S3 is mandatory and the *most guidance-sensitive* of the three. | ~Med-High. R8 latency is the live risk; R10 the centroid risk. |
| **4 — Hardware** | V5 | **Async, human-executed** | n/a (worktree-irrelevant) | Deliverable is a numbers report, not a green test. Feeds back into V2 jitter band + R2 Huber threshold as config. Cross-check: implied λ̇ error ≤ `IMMConfig.ego_gate_radps`. | ~Med, gated on rig availability. |

**Worktree isolation honest read:** only Stage 0 is *cleanly* parallelizable across worktrees. Stages 1–3 each contain a serial spine through `pipeline.py`/`track.py` that **must** be ordered (see §4). The parallelism we actually get is: *develop bodies in parallel, serialize the shared-file hunks at integration*. Treating `track.py` and `pipeline.step` as additive-only (new methods/fields/flags, never rewriting existing lines) is what keeps the merges mechanical.

---

## 4. File-Conflict Matrix + Mandated Ordering

The four hot files and every task that touches them. **Rule: land in the order shown; later tasks add additive methods/fields/flags, never rewrite an earlier task's hunk.**

| File | Tasks (in mandated order) | Hot region | Ordering rationale |
|------|--------------------------|------------|--------------------|
| **`pipeline.py` `step()`** | R1 → R3 → R5 → R6 → R7 → R8 → R9 → R10 | 227–283 (the integration seam) | R1 inserts `set_imm_prediction` *before* line 227 + passes `model_wrong_alarm/lock_quality` into `update()`. R3 edits the `command_from_guidance` call (278-281). R5 substitutes the centroid arg at the `los.update` call (240) — **highest-conflict line**. R6 inserts `event_obs` between 238 and 242. R7 adds the consensus gate between 227 and the LOCKED consumption. R8/R9/R10 add flag-gated channel calls. **All additive; serialize strictly.** |
| **`track.py`** | R1 → R4 → R5 → R7 → R8 → R10 | `__init__` (254-273), `_on_associated` (377-416), `_on_missed` (418-477), `ThermalLockConfig` (103-161), `ThermalLockSnapshot` (168-223) | R1 adds IMM-coast state + lock-score + peak-delete. R4 adds regime enum/state/snapshot field. R5 carries regime→aimpoint. R7 adds `consensus_ok` kwarg + LOCKED gate. R8 adds `ingest_correlation` + corr fields. R10 adds `_associate_soft` + JPDA config. **Every task is additive fields/methods; the snapshot builder is the collision point — each task appends, never reorders.** |
| **`bearing_rate.py`** | A1 → R3 → R2 | `compute()` N-use (438-439), `GuidanceConfig` (243-252), `__init__` (319-321) | **A1 and R3 both touch the N-application at 438-439** → fuse into one PR or strict A1→R3. A1 introduces `n_applied`; R3's falcon-low N is a *value* on the same path. R2 adds λ̇ EMA state (319-321) + smoothing before 438 — disjoint enough but lands last. |
| **`imm.py`** | R2 → R6 | `update()` measurement (360, 403-441), `IMMConfig` (144-212), `IMMEstimate` | R2 adds Huber + R-extent inside `update()` + config. R6 adds the optional `event_obs` kwarg that replaces/blends rate-channels of `z[2],z[3]` + two diagnostic fields. **R2 first** (it reshapes the R-build R6 then references). |
| **`mti.py`** | R5 (R6 read-only) | `_register` (88-123) | R5 exposes `last_homography()`/`_last_hmat`/inlier-quality (currently `hmat` is discarded — confirmed). R6 only *reuses* the de-rotation via `derotate.py`, does not touch `_register`. No real conflict. |
| **`test_s3_acceptance.py`** | A1 → V2 → (R-task gates) | new `TestGateN/O` classes | A1 adds `TestGateN_AcquireSettling`, V2 adds `TestGateO_LatencyJitter` + extends `TestGateK`. Different classes → low conflict, but same file → serialize appends. |
| **`correlation.py`** | R8 → R9 | whole module | R8 creates it; R9 adds `prewarp()`. Serialize. |

**Single biggest merge hazard:** A1 ⊗ R3 on `bearing_rate.py:438-439` (both rewrite the N-application). **Mandate: one fused PR.** Second hazard: R5 ⊗ {R1,R6} on `pipeline.py:240` (R5 swaps the centroid that R1/R6 read). **Mandate: R5 lands after R1, and R6's `event_obs` reads `snap.centroid_px` — R5 must substitute *before* R6 consumes it, so the in-`step` order is R5-substitution → R6-event-channel.**

---

## 5. Doctrine-Invariant Gate Matrix

Each invariant × its concrete guard test (all in V4's `test_doctrine_invariants.py`, run on **every** PR; must stay green across the whole campaign).

| Inv | Statement | Concrete guard test (must stay green) | Highest-risk tasks |
|-----|-----------|---------------------------------------|--------------------|
| **1** | Range never scales guidance gain (Vc scheduled only) | `test_inv1_range_does_not_scale_gain`: `command_from_guidance(estimated_range_m=20)` vs `=200` → roll cmd bit-identical except via documented terminal-*timing* switches; with switches disabled, fully identical. | **R3** (removes range from terminal trigger), **R9** (τ warps template not gain), **A1** (N schedule must carry no range) |
| **2** | AI/learned/appearance/scene → lock-quality/engage-permission ONLY, never centroid/LOS/tracker | `test_inv2_quality_never_moves_centroid`: perturb `lock_quality`/`model_wrong_alarm`/PSR/appearance with blob geometry fixed → `snapshot.centroid_px` and IMM `az/el/az_rate/el_rate` **bit-identical**. Each of R1/R4/R5/R8/R9/R10 ships its own bit-equality variant. | **R5** (changes centroid — defended as *deterministic CV*, not learned), **R8** (PSR one line from centroid), **R10** (writes soft-centroid — defended as *kinematic association*) |
| **3** | ABORT = PASS; WRONG-HIT = HARD FAIL (default-deny on doubt) | `test_inv3_default_deny_on_doubt`: HIGH_CROSSING 25 m/s → `ROEAbort` raised, `result.hit is False`. V2's step-jink curve: beyond-envelope → abort+miss, never confident hit. R7 clutter-crossing: **0 wrong-swaps across N≥20 seeds OR abort**. | **R7** (clutter-crossing swap), **R3** (premature acro commit), **R10** (distractor capture) |
| **4** | IMM state is modified-polar [az,el,az_rate,el_rate] (no Cartesian range rewrite) | `test_inv4_imm_state_is_polar`: `IMMFilter._x` is 4-D, `IMMEstimate` exposes exactly 4 angular fields, no Cartesian/range field (introspection guard). | R2/R6 (both touch IMM update — must keep state polar) |
| **5** | Every cmd ≤0.84 g lateral, in-FOV, corrections done before ~1.0–1.4 s ten-τ wall | `test_inv5_command_within_g_budget`: per-tick `required_g ≤ achievable_g` or abort fired, over full HEAD_ON. V1 acquire reduces early demand (never tightens envelope). | **R5** (late silhouette flicker → slew-cap in FILL), **R3** (acro ×1.3 near impact), R2 (over-smoothing must not lag jink) |
| **6** | Hard-mount the camera | `test_inv6_no_gimbal_state`: LOS path uses gyro de-rotation; `AICommand` has roll/pitch/yaw/throttle only, no gimbal-angle field (schema guard). *Architectural — guards command schema, not physical mount.* | (architectural; V5 surfaces soft-mount via jitter) |
| **7** | Post-commit: NO new track; re-acquire only SAME committed track | `test_inv7_no_new_track_post_commit`: drive to LOCKED → gap → present *different* blob outside family veto → tracker coasts or re-associates SAME identity, never fresh CANDIDATE/LOCKED on intruder. | **R7** (2-hyp carry must not fork a committed track), **R1** (covariance reacquire = same track), **R8** (immutable FEAR template = LOBL reference) |

**The three highest-risk tasks for the three load-bearing invariants:**
- **Inv 1** → **R3** (must prove range is *gone* from the wired terminal path, not just unused).
- **Inv 2** → **R5** and **R10** (the only two tasks that legitimately write the centroid; both defended as deterministic-CV/kinematic, both require exact bit-equality fail-safe tests and an explicit PR statement of the boundary).
- **Inv 7** → **R7** (the 2-hypothesis carry is one careless `seed()` away from acquiring a new post-commit track).

---

## 6. Model-Allocation Plan

**Principle (per user request): Sonnet where the work is bounded, mechanical, parallel, and fully specified; strong model where correctness is subtle, the LOS/gain/centroid is touched, or doctrine sits on a knife-edge.**

### Sonnet (bounded/mechanical/parallel)
| Task | Why Sonnet |
|------|-----------|
| **R4** (whole task) | Enum + hysteretic Schmitt-trigger comparator + field plumbing through existing snapshot builders. Only subtlety (collapse-ratio direction, coast-freeze) is fully spec'd. Writes only an unread field. |
| **R3 sub-tasks: falcon-low N + pipeline τ-passthrough** | Pure config value + a 3-line `command_from_guidance` kwarg wiring. Mechanical. (The `_is_terminal_phase` τ/τ̇ commit+latch logic stays ★.) |
| **V3 test/harness scaffolding** (4 files, metrics) | Parallelizable across files; deterministic metrics. (Any `ThermalSimulator` *rendering extension* → ★.) |
| **V5 field-noise histogram bench** | Mechanical stats (temporal std, histogram). (Time-sync cross-correlation + heavy-tail *interpretation* → ★.) |
| **`derotate.py` extraction** (Stage 0) | Pure refactor of `los.py:273-286` under a bit-identical char-test. |
| **R8/R10 mechanical sub-steps** | `ranked_snapshots(k)` sort accessor; correlation FFT *scaffolding* under spec. (Integration + Inv-2 boundary → ★ review.) |

### Strong model (subtle correctness / integration / safety review)
| Task | Why strong |
|------|-----------|
| **R1** | LOS-feeding gate centre + deletion logic + px↔bearing sign chain must match `geometry.py`/`los.py` exactly (Inv 2/4/7). |
| **R2** | Robust estimation that must NOT lag a real maneuver (glint-vs-jink); Huber must clip state-update but leave likelihood raw or it silently blinds the maneuver mode (Inv 1/5). |
| **R3 (terminal commit+latch)**, **A1/V1**, **A5/V2** | Endgame timing feeds the acro amplifier; A1 touches the ROE abort boundary; A5's `_DelayBuffer` off-by-one silently corrupts every CPA number. |
| **R5** | Changes the LOS spine; Inv-2 at its subtlest; fail-safe cascade + ten-τ slew-limit; highest-conflict pipeline line. |
| **R6** | Changes closed-loop path; Inv-2 boundary (motion-measurement vs appearance); pinhole sign chain. |
| **R7** | Sits on Inv 7 (no new post-commit track) + Inv 3 (zero-wrong-swap); crossing-exit resolution is subtle. |
| **R8/R9/R10** | All change `pipeline.step`/centroid-adjacent; R8 Inv-2 (PSR one line from centroid) + hard latency budget; R9 wrong-τ-warp must be provably bounded; R10 *writes the centroid* (JPDA β-normalization, keep PSR out of β). |
| **V4** | These are the safety contracts; a test with a hole gives false assurance — the most dangerous failure mode. |
| **All adversarial-review gates** | Every centroid/LOS/gain-touching diff gets a strong-model review against V4 before merge, regardless of who wrote it. |

**Net:** ~4 tasks/sub-tasks are cleanly Sonnet (R4, R3-N-option, V3-scaffold, V5-histogram, derotate); everything that touches the closed loop or doctrine boundary is strong, with strong-model review mandatory on all merges into the hot four files.

---

## 7. Missing Science / Needs-Measurement

**Direct answer to "do we need to re-run the science, or is something missing?": The science is complete. The *mechanisms* are fully specified and grounded; what is missing is (a) two synthetic-renderer assets and (b) one hardware-measurement campaign — none of which require new theory, only construction and instrumentation.** Three headline acceptance *numbers* are gated on these; the underlying designs are not. Below is every task that cannot be fully *graded* (not "cannot be built") without more construction/measurement:

| Gap | Blocks | Nature | Recommendation |
|-----|--------|--------|----------------|
| **G1 — No aspect-rotating winged-UAV thermal renderer.** Confirmed: `thermal_sim`/`seeker_sim` render a single isotropic Gaussian (`target_sigma_px`), no silhouette/aspect/offset-hotspot. | **R5** aimpoint-walk-<0.2°-vs-aspect metric; **R9** affine pre-warp acceptance | **Construction, not science.** A deterministic extended-target generator (elongated profile + movable motor-hotspot + aspect param + independent target/background motion for MTI residual). | Build as a distinct Stage-0/Stage-2 deliverable (fold into A5 harness ext). Until then R5/R9 unit-test on synthetic masks; **gate the 0.2°/+20%-PSR-affine numbers on the asset.** Ship R5 scale-path + R9 scale-warp now. |
| **G2 — No scripted crossing-distractor blob.** `seeker_sim` has target + (near-static) stars only. | **R10** clutter-crossing pull-off (≥40% excursion reduction); **R7** hidden-jink-in-crossing | **Construction.** A second Gaussian on a programmed gate-crossing path (lighter than G1). | Build before R7/R10 headline acceptance; the logic is unit-testable without it but the named acceptance number is not. |
| **G3 — `area_extended_px` thresholds (`A_resolve_px`, `A_fill_px`) unmeasured.** Derived from the sim's analytic Gaussian area, not real FT640 footprints. | **R4** regime transition points | **Calibration.** Mechanism is correct; the numbers need a bench scale-sweep / field clutter. | Spec as *config, not constants*; tune on V3-s1 + V5 field data. Does not block R4 landing (default-off, classifier is sound). |
| **G4 — FT640 post-AGC clutter PDF + effective bit-depth + cam↔IMU time-sync residual/jitter unmeasured.** This is **V5**. | **R2** Huber threshold (is glint really heavy-tailed?); **R6** absolute λ̇-improvement; **V2** jitter magnitude; **`IMMConfig.sigma_meas_*`/`ego_gate_radps` validation** | **Hardware measurement — the only true "missing data."** Needs FT640+CVBS-USB+Pi5+IMU per `PI_BRINGUP.md`. A model cannot run it; a human must. | **R2/R6/V2 ship with placeholders flagged as such**: R2 R-inflation default `r_extent_k=0`, V2 jitter band {0,5,10 ms} stated as plausible-not-measured, R6 acceptance = *relative* improvement on synthetic stressor. V5 re-tunes them post-measurement. Cross-check: measured implied λ̇ error must be ≤ `ego_gate_radps=0.05` or that A4 gate is mis-tuned. |
| **G5 — R6 bolometer-latency honesty.** The bolometer τ≈10–15 ms caps any *speed* benefit; R6 is an *invariance* win, not a latency win. | R6 framing | **Not a gap — a correctness caveat.** | State plainly in R6's PR: event channel removes AGC/background sensitivity, does not reduce sensor latency. |

**Confirmation/correction of "we believe the science is complete":** **Confirmed.** No task in the campaign requires re-deriving guidance, estimation, or perception theory. Every "missing" item is either a *renderer to build* (G1, G2 — engineering), a *threshold to calibrate* (G3 — tuning), or a *physical quantity to measure* (G4/V5 — instrumentation). The campaign is correctly structured to ship the mechanisms now behind default-off flags and back-fill the three gated acceptance numbers as G1/G2/V5 complete.

---

## 8. Definition of Done (whole campaign)

The Task-1 campaign is **done** when **all** of the following hold:

1. **Baseline integrity:** The full suite (343 + all new tests) is green with **every new flag OFF**, and a per-stage regression proves the OFF state is **bit-identical** to the pre-campaign baseline (centroid, LOS, IMM state, and guidance command stream) for R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, A1, A5.
2. **Doctrine matrix (V4) 100% green** on the final integrated build, with the per-task Inv-2 bit-equality variants (R1/R4/R5/R8/R9/R10) and Inv-7 no-new-post-commit-track all passing. The three knife-edge defenses (R5/R10 centroid-as-deterministic-CV/kinematic; R7 carry-without-fork) are each stated in their PR and enforced by a green fail-safe test.
3. **Closed-loop S3 acceptance** re-run **once per stage** with the stage's intended-on flag combination, passing Gates I–M **plus** new Gate N (ACQUIRE: ≥15% early-spike reduction, CPA ≤1.05×, hit-rate parity) and Gate O (latency-jitter: median CPA ≤2× at 10 ms, hit-rate ≥95%), and V2's step-jink envelope curve pinned to the 0.84 g physics (hit at ≤0.4 g, abort+miss at ≥1.0 g, transition at 0.84 g).
4. **Latency budget proven on Pi5:** `latency_hwil.py --correlation [--prewarp]` p99 < 16.6 ms (60 Hz) with R8/R9 active, with the spec'd fallbacks (scale-filter decimation / patch cap) applied if needed; all other tasks shown ≪17 ms.
5. **Perception acceptance** met where un-gated: R4 regime monotone+hysteretic (V3-s1), R6 ≥30% λ̇-RMS-reduction-relative under AGC/background sweep (V3-s3), R7 zero-wrong-swap-or-abort across N≥20 crossings (V3-s2). **Gated numbers (R5 0.2°-aspect-walk, R9 +20%-affine-PSR, R10 ≥40%-pull-off-reduction)** are either met on the delivered G1/G2 renderer assets, **or** explicitly carried as renderer-blocked with the mechanism unit-tested on synthetic masks and the acceptance scheduled.
6. **Every guidance-path change is default-off opt-in** with a documented flag, and the intended-on configuration is recorded per scenario.
7. **V5 executed on the physical rig** (or explicitly deferred with a dated hardware-availability note): cam↔IMU time-sync residual+jitter and field NETD/effective-bit-depth/post-AGC-clutter-PDF measured, written back into `IMMConfig`/sim config, with the cross-check that implied λ̇ error ≤ `ego_gate_radps=0.05`; **R2's Huber threshold and V2's jitter band re-derived from the measurement** (or the placeholder status flagged in-code if V5 is deferred).
8. **A1 and A5 (the two pending pre-campaign tasks) are landed and green**, closing the original roadmap's open items.

---

**Build order one-liner:** Stage 0 (V4+V3+derotate, parallel) → Stage 1 (R1→{R2‖A5}→R3⊕A1, one S3) → Stage 2 (R4→R5; R6‖R7, one S3) → Stage 3 (R8→R9; R10, one S3 + latency gate) → Stage 4 (V5, async, re-tunes R2/V2). Serialize every hunk through `pipeline.py`/`track.py`/`bearing_rate.py`/`imm.py`; keep all guidance-path changes additive and default-off; strong-model-review every centroid/LOS/gain diff against V4 before merge.


---

# PER-TASK CLUSTER SPECS



<!-- cluster: spec-tier0 -->

I now have everything needed. Key facts confirmed:

- The pipeline calls `tracker.update()` at the *top* of the frame (line 227), then runs IMM (line 242) and feeds `set_search_radius` back for the *next* frame (line 250). So the IMM mixed-state for coast is a previous-frame quantity — R1 must use `self._last_imm`.
- `command_from_guidance` is called WITHOUT `estimated_range_m`/`estimated_tau_s` (lines 278-281), so the terminal/acro/los-hold phases in `command_map.py` are currently **never triggered** in the wired pipeline — they only fire in unit tests. R3 must wire `estimated_tau_s` from looming.
- `bearing_rate.py` has a single hardcoded `cfg.N`; falcon-low N is a config addition.

Here is the implementation TZ.

---

## Cluster R1–R3 — Tier-0 "already-built-but-unwired" free wins (IMM-hardening consumption, NIS-scheduled robust λ̇, τ-driven terminal timing)

These three tasks wire estimator hardening that already exists in `imm.py` into the tracker (`track.py`), the guidance smoothing/innovation path (`bearing_rate.py`), and the terminal-phase trigger (`command_map.py` via `pipeline.py`). All three share `pipeline.py` as the integration seam — sequencing and conflict notes are called out per task.

---

### R1 — Consume IMM hardening in the tracker

**ID & goal.** R1: replace the tracker's 2-point CV coast with IMM mixed-state prediction, drive the reacquire gate from the IMM covariance-sized `gate_sigma`, and route `model_wrong_alarm`/`lock_quality` into a continuous lock-score with peak-relative (hysteretic) deletion — none of which currently feed `track.py`.

**Files & exact locations.**
- `fpv/seeker/track.py`:
  - `ThermalLockTracker.__init__` (lines 254–273) — add IMM-handoff state + lock-score state fields.
  - `ThermalLockTracker._predict_centroid` (lines 505–517) — currently `cx + vx*(missed+1)`, a 2-point CV from `_update_velocity`. **Add** an optional IMM-supplied predicted-centroid override consumed during coast.
  - **New public method** `ThermalLockTracker.set_imm_prediction(centroid_px, az_rate_radps, el_rate_radps, valid)` (insert near `set_search_radius`, lines 303–312) — the pipeline pushes the previous-frame IMM mixed state as a px prediction for the *next* frame's coast.
  - **New public method** `ThermalLockTracker.update_lock_score(model_wrong_alarm, lock_quality)` OR fold both into `update()` via two new optional kwargs (preferred — see below). Touch `_on_associated` (377–416) and `_on_missed` (418–477) to apply peak-relative deletion.
  - `ThermalLockConfig` (103–161) — add lock-score config fields.
  - `ThermalLockSnapshot` (168–223) — add `lock_score: float` and `lock_score_peak: float` output fields + `to_dict` entries.
- `fpv/guidance/pipeline.py`:
  - Lines 227–250 — the tracker `update()` is called *before* IMM runs. To feed IMM mixed-state into coast we must push **last frame's** IMM (`self._last_imm`) into the tracker *before* `update()`. Add a `set_imm_prediction(...)` call just before line 227, and pass `model_wrong_alarm`/`lock_quality` from `self._last_imm` into `update()`.

**Change / algorithm.**

1. **IMM mixed-state coast (replace 2-pt CV).** The IMM state is angular `[az,el,az_rate,el_rate]` (Inv 4) and the tracker works in pixels; the pipeline owns both the `intrinsics` and `LOSObservation`, so it is the correct place to project. New tracker state:
   - `self._imm_pred_px: tuple[float,float] | None = None`
   - `self._imm_rate_px_per_frame: tuple[float,float] = (0.0,0.0)` (az/el rate projected to px/frame via `f_px*dt`, supplied by pipeline)
   - `self._imm_valid: bool = False`

   `set_imm_prediction(centroid_px, rate_px_per_frame, valid)` stores these. `_predict_centroid()` becomes: if coasting (`_missed_frames>0`) **and** `_imm_valid`, return `imm_pred_px + imm_rate_px_per_frame*(missed_frames+1)`; else fall back to the existing 2-pt CV branch (lines 513–517) verbatim. **The IMM never moves the centroid while LOCKED** — only the predicted gate-centre during coast. Doctrine: the centroid that feeds LOS is still the *observed* blob centroid on associated frames (line 412), unchanged.

   Pipeline wiring (before line 227): project `self._last_imm` az/el to a pixel point through `pixel_from_bearing` (boresight + f_px) and az_rate/el_rate to px/frame as `rate_px = f_px * rate_radps * dt_eff`; call `self._tracker.set_imm_prediction(px, rate_px, valid = self._last_imm is not None and not self._last_imm.model_wrong_alarm)`. **Missing primitive:** confirm `geometry.py` exposes a `bearing_to_pixel`/`pixel_from_bearing` inverse of `pixel_to_bearing`; if absent, R1 must add the 2-line inverse (`x = cx + f*tan(az)`, `y = cy - f*tan(el)`). This is the one piece that needs a code check, not a design decision.

2. **gate_sigma → set_search_radius.** Already wired (pipeline line 250). R1's job is only to confirm `_gate_radius()` (531–543) consumes `_dynamic_gate_px` as an expand-only floor — it does (line 543). **No change**, but R1 must add a regression test that the propagated gate is actually used during REACQUIRE (currently untested end-to-end). One refinement: during REACQUIRE the gate is `base*reacquire_expansion_factor` then `max(.,dynamic)`; verify the dynamic floor is applied *after* the REACQUIRE multiplier (it is, line 540–543) so a covariance blow-up during reacquire still wins.

3. **Continuous lock-score with peak-relative deletion.** New `ThermalLockConfig` fields:
   - `lock_score_alpha: float = 0.3` (EMA smoothing of per-frame quality)
   - `lock_score_peak_decay: float = 0.995` (peak leaks down slowly so a permanently-degraded track can still be released)
   - `lock_score_rel_delete: float = 0.5` (delete when `score < rel_delete * peak`)
   - `lock_score_model_wrong_penalty: float = 0.4` (multiplicative hit when `model_wrong_alarm`)

   New tracker state `self._lock_score: float = 0.0`, `self._lock_score_peak: float = 0.0`. New per-frame update (called inside `update()` after association decision, using two new optional kwargs `model_wrong_alarm: bool = False, lock_quality: float = 1.0` passed from pipeline's `self._last_imm`):
   ```
   q = lock_quality * (lock_score_model_wrong_penalty if model_wrong_alarm else 1.0)
   if associated: q *= 1.0           else: q *= confidence_decay_per_missed_frame
   self._lock_score = alpha*q + (1-alpha)*self._lock_score
   self._lock_score_peak = max(self._lock_score, peak_decay*self._lock_score_peak)
   ```
   **Peak-relative deletion:** in `_on_missed`, when in REACQUIRE, transition to HARD_LOST if `_lock_score < rel_delete*_lock_score_peak` **OR** the existing `reacquire_frames` budget is exceeded (keep the frame-count budget as a hard backstop). This is strictly additive — it can only delete *earlier*, never keep a track longer than the existing budget, so it cannot regress current acceptance.

   **Doctrine placement (Inv 2):** `lock_quality`/`model_wrong_alarm` are IMM-derived *consistency* signals, not appearance/AI. They feed only `lock_score` → deletion → (eventually) engage-permission. They must NOT enter `_associate`/`_association_cost`/`_predict_centroid`. Enforce by code review + a test asserting centroid output is bit-identical with vs. without lock-score wiring on associated frames.

**New / changed tests + acceptance thresholds.** New file `fpv/seeker/tests/test_r1_imm_coast.py`:
- *IMM-coast tracks covariance:* replay a synthetic step-jink-then-dropout sequence; assert the coast predicted-centroid error vs. ground truth is **≥30% lower RMS** than the 2-pt CV baseline over a 10-frame coast (the IMM carries acceleration via the maneuver mode; 2-pt CV does not).
- *Reacquire gate within propagated 3-σ:* after a 6-frame dropout, assert `tracker.gate_px` is within **±5%** of `3*sqrt(S_proj)` px computed from the last IMM `gate_sigma_*`, and that a target re-appearing at the propagated mean re-associates (no fresh CANDIDATE — Inv 7).
- *Peak-relative deletion:* drive `lock_quality` smoothly from 1.0→0.2; assert deletion fires when `score` crosses `0.5*peak`, **before** the `reacquire_frames` count, and that a single 1-frame `lock_quality=0` dropout does **not** delete (hysteresis).
- *Centroid-untouched invariant:* assert `snap.centroid_px` on every associated frame is identical with lock-score/IMM-coast enabled vs. disabled.
- Extend `fpv/seeker/tests/test_track.py` for the new config validation (`__post_init__` ranges).

**Doctrine-invariant compliance.**
- **Inv 2 (AI/quality → lock only):** lock_quality/model_wrong_alarm route to `lock_score`→deletion/engage-permission only; centroid/LOS/association untouched (tested bit-identical).
- **Inv 4 (modified-polar):** IMM stays angular; the *pipeline* projects to px for the gate centre — no Cartesian range rewrite of IMM state.
- **Inv 7 (same-track reacquire):** covariance-ellipse reacquire re-associates the SAME track inside the propagated gate; HARD_LOST→NO_TARGET reset (lines 347–354) is unchanged, so no *new* track is acquired post-commit by R1 (post-commit lockout is a pipeline/`engage` concern, not regressed here).
- **Inv 3 (ABORT is a PASS):** earlier peak-relative deletion → earlier ABANDON → safe coast/abort, never a confident wrong re-lock.

**Dependencies.** None must land first (uses already-emitted IMM fields). **Shares `pipeline.py` lines 227–255 with R3** (R3 also edits the `command_from_guidance` call ~278). Low conflict — different line ranges, but land R1 then R3 to avoid a merge in the same function. R2 also touches the IMM→guidance handoff but in `bearing_rate.py`, not `track.py`; no overlap.

**Risk & S3-gate sensitivity.** Coast prediction changes the *gate centre* during dropouts, which changes which blob associates → **can perturb the closed-loop LOS** → **must re-run the slow S3 acceptance.** Make it default-off-able: gate the IMM-coast and peak-relative-deletion behind a `ThermalLockConfig.use_imm_coast: bool = True` / `use_peak_relative_deletion: bool = True` so S3 can A/B. Lock-score output is free (additive field) and can ship even if coast is held back.

**RPi5 bench-testability.** Replay recorded/synthetic closing-geometry sequences with injected dropouts; assert reacquire gate radius vs. propagated covariance and the ≥30% coast-RMS win offline (no hardware needed). Latency: one bearing→pixel projection + a handful of scalar ops per frame ≪ 1 ms — trivially inside 17 ms.

**Recommended executor model.** **strong.** It touches the LOS-feeding gate centre and the deletion logic (safety-critical: a too-eager deletion drops a real track, a too-lax one risks a stale lock); the px↔bearing projection sign chain must match `los.py`/`geometry.py` exactly. Subtle correctness + Inv-2/4/7 sensitivity.

---

### R2 — NIS-scheduled λ̇ smoothing + Huber-clip in-gate innovations + R inflation with pixel-extent

**ID & goal.** R2: adaptively smooth the IMM-output LOS-rate (`λ̇`) hard when innovations are quiet and open the loop the instant the maneuver/NIS alarm fires; robustly (Huber) down-weight in-gate-but-tail glint innovations; and inflate measurement noise `R` as the blob's pixel-extent grows (centroid noise ∝ extent at the endgame).

**Files & exact locations.**
- `fpv/seeker/imm.py`:
  - **Huber + R-inflation belong inside the filter** (they change the update), so they go in `IMMFilter.update`:
    - R-inflation: at lines 403–412 where `R_frame` is already built from ego-quality. **Add** a pixel-extent term: `R_frame[0,0] *= ext_factor; R_frame[1,1] *= ext_factor` (bearing channels) where `ext_factor = 1 + k_ext*(extent_px/extent_ref - 1)` clamped ≥1. Requires a new input — see data flow.
    - Huber clip: in the per-mode loop at lines 423–441, after computing `innov` (428) and `S` (429), compute the Mahalanobis norm and apply a Huber weight to the *innovation used in the Kalman update* `x_new = x_pred + K @ (w_huber * innov)` (line 438) — clip only the rate channels `innov[2:4]`, leave bearing channels for stability of the position estimate. The likelihood (`mahal`, line 449) uses the **un-clipped** innovation so mode probabilities still react.
  - `IMMConfig` (144–212) — add `huber_delta_sigma: float = 3.0`, `r_extent_k: float = 1.0`, `r_extent_ref_px: float = 4.0`, `lambda_dot_smooth_quiet: float`/`_alarm` for the bandwidth schedule.
  - `LOSObservation` carries no extent; **add** `extent_px: float = 0.0` to `LOSObservation` in `fpv/seeker/los.py` (lines 85–118) and populate it in `LOSComputer.update` from a new `extent_px` arg, OR (cleaner, lower-blast-radius) pass extent directly to `IMMFilter.update(los, dt, extent_px=...)` as a kwarg. **Prefer the kwarg** — keeps `los.py` untouched.
- **NIS-scheduled λ̇ smoothing** is a *guidance-input* smoothing, not a filter change. Two honest options:
  - (a) In `bearing_rate.py` `BearingRateGuidance.compute` (327–441): smooth `imm.az_rate_radps`/`el_rate_radps` (lines 367–368) with an EMA whose alpha is scheduled by `imm.nis_true`/`model_wrong_alarm` *before* forming `brn_az/brn_el` (438–439). Add EMA state to `BearingRateGuidance.__init__` (319–321).
  - (b) In `pipeline.py` between IMM (242) and guidance (273).
  - **Choose (a):** keeps the schedule co-located with the law it feeds, and `BearingRateGuidance` is already stateful (tick counter), so adding `_lambda_dot_ema` is natural.

**Change / algorithm.**

1. **NIS-scheduled λ̇ smoothing (bearing_rate.py).** New `GuidanceConfig` fields: `lambda_smooth_alpha_quiet: float = 0.3` (heavy smoothing when NIS low), `lambda_smooth_alpha_alarm: float = 0.9` (near-passthrough when alarm), `nis_schedule_ref: float = 9.21` (the IMM χ² bound). Per tick:
   ```
   frac = clamp(imm.nis_true / nis_schedule_ref, 0, 1)
   if imm.model_wrong_alarm: frac = 1.0
   alpha = alpha_quiet + frac*(alpha_alarm - alpha_quiet)
   lam_az = alpha*imm.az_rate_radps + (1-alpha)*self._lam_az_ema   # init to first sample
   ```
   Use `lam_az/lam_el` in `brn_az/brn_el` (438–439) **and** in `lambda_dot_mag` geometry classification (382). This filters glint hard (NIS quiet) but lets a real jink (NIS/alarm high) through with minimal lag — the exact Palumbo/Ch.6 behavior. Reset EMA in a `reset()` method (mirror pilot's).

2. **Huber in-gate clip (imm.py).** After `S_inv` (lines 432–435), for the rate sub-block compute `d = sqrt(innov[2:4] @ Sinv_rr @ innov[2:4])` (Mahalanobis, 2-DOF). Huber weight `w = 1.0 if d <= delta else delta/d` with `delta = huber_delta_sigma * sqrt(2)` (χ²-2DOF scaling). Apply only to the rate channels of the innovation fed to `x_new` (line 438): build `innov_used = innov.copy(); innov_used[2:4] *= w`. **Likelihood uses raw `innov`** so the maneuver mode still fires on a true jink — the clip only limits how far a single tail excursion moves the state, it does not blind the mode-probability update. This is in-gate (the χ² gate already rejects gross outliers; Huber down-weights the in-gate tail).

3. **R inflation with pixel-extent (imm.py).** `ext_factor = 1 + r_extent_k * max(0, extent_px/r_extent_ref_px - 1)`, applied to `R_frame[0,0]`/`[1,1]` (bearing channels) after the ego-quality build (lines 409–411). At `extent_px == r_extent_ref_px` factor is 1.0 (no-op → backward-compatible with the current 343-green tests, which pass `extent_px=0` default → factor=1.0). Larger extent → larger bearing R → filter trusts the centroid less as the blob resolves/fills (centroid jitter grows with extent). Source `extent_px` from `blob.area_px` as `sqrt(area_px)` (the pipeline has `blob` at line 262) or directly from a future `extent_extended_px`; **document that `sqrt(area)` is a proxy until R4/R5 supply a true silhouette extent.**

**New / changed tests + acceptance thresholds.** New file `fpv/seeker/tests/test_r2_robust_lambda.py`:
- *Glint-spike rejection:* inject 1–2-frame glint spikes (5–10× nominal λ̇) onto a quiet track; assert output **λ̇ RMS drops ≥30%** vs. the un-smoothed/un-Huber baseline, AND mean λ̇ bias < 5% (smoothing must not shift the DC level).
- *Step-jink not lagged:* a sustained step-jink (constant new λ̇ for ≥10 frames) must reach **≥90% of the new λ̇ within ≤3 frames** once `model_wrong_alarm`/high-NIS opens the bandwidth — i.e. the schedule must not flatten a real maneuver. Assert lag (frames-to-90%) is **no worse than +1 frame** vs. the un-smoothed baseline.
- *Huber bounds single-frame influence:* a lone 8-σ in-gate innovation moves the filtered rate by **≤ huber_delta_sigma·σ**, not the raw 8σ.
- *R-extent no-op at ref:* with `extent_px = r_extent_ref_px`, assert the IMM output is **bit-identical** to the current (extent-unaware) filter — protects the 343-green suite.
- *R-extent monotonicity:* larger `extent_px` → larger posterior bearing variance and smaller Kalman gain on a fixed innovation.
- Extend `test_a4_estimator.py` style for the new `IMMConfig` validation.

**Doctrine-invariant compliance.**
- **Inv 1 (range never scales gain):** smoothing/Huber/R-inflation operate on λ̇ and centroid-noise, never on `Vc` or `N`; `a_cmd = N·Vc_sched·λ̇` magnitude source unchanged. R-inflation uses pixel-*extent*, not range.
- **Inv 2:** all signals are kinematic/consistency (NIS, innovation, extent), not appearance/AI; they affect λ̇ quality and the filter, which is the LOS authority — *not* a learned signal. (Extent is geometric, doctrine-clean.)
- **Inv 5 (≤0.84 g, corrections before the wall):** robust smoothing *reduces* spurious large commands from glint, helping the g-budget; the alarm-opened bandwidth ensures real corrections still complete before the ten-τ wall.

**Dependencies.** None hard. **Best after R1** only because both want the same S3 re-run; can develop in parallel (disjoint files except the shared S3 gate). The `extent_px` kwarg on `IMMFilter.update` is a new signature param — coordinate with anyone else touching that call (pipeline line 242).

**Risk & S3-gate sensitivity.** Huber + λ̇ smoothing are **directly in the closed-loop guidance path → mandatory S3 re-run.** All three sub-features must be default-off-able: `GuidanceConfig.nis_lambda_smoothing: bool`, `IMMConfig.huber_enabled: bool`, and R-extent is self-disabling at `r_extent_k=0`. The danger is over-smoothing lagging a real jink (Inv 5 violation) — the step-jink lag test is the guard.

**RPi5 bench-testability.** Inject glint spikes + step-jink on replayed sequences (exactly the A5 Monte-Carlo harness, per roadmap §5 "A5 is the right harness to validate R1/R2"); measure λ̇ RMS and lag offline. Latency: one EMA + one Mahalanobis norm + two scalar R multiplies per frame ≪ 1 ms.

**Recommended executor model.** **strong.** Robust estimation that must *not* lag a real maneuver is the classic safety-critical trade (glint-filter-vs-jink); the Huber must clip the state-update innovation while leaving the likelihood raw — easy to get subtly wrong and silently blind the maneuver mode. Closed-loop + Inv-1/5 sensitive.

---

### R3 — τ-driven terminal-commit/acro (replace range/fixed-timer) + falcon-low N≈2.6 option

**ID & goal.** R3: make the terminal/acro/LOS-hold phase trigger off looming-τ (passive, range-free) instead of the `estimated_range_m`/fixed-`tau_threshold` timers, and add an opt-in falcon-low navigation ratio `N≈2.6` to the guidance law.

**Files & exact locations.**
- `fpv/guidance/command_map.py`:
  - `_is_terminal_phase` (293–304) — currently fires on `range_m < 15` OR `0 < tau_s < 0.4`. **Change** to τ̇-/τ-based commit (see algorithm). The `range_m` branch (300–301) is doctrine-suspect terminal *timing* (not gain, so it's legal, but the roadmap wants it gone).
  - `_is_los_hold_phase` (307–311) — fires on `range_m < 5`. **Change** to a τ floor (e.g. `tau_s < los_hold_tau_s`).
  - `LosGuidancePilot.command_from_guidance` (146–269) — the call already accepts `estimated_tau_s` (line 157) and passes it to `_is_terminal_phase` (190). **The wiring gap is upstream:** `pipeline.py` (278–281) calls this *without* `estimated_tau_s`. R3 must pass `estimated_tau_s = looming_est.tau_s if looming_est.tau_confidence >= threshold else None`.
  - `PilotConfig` (64–102) — replace/augment `acro_switch_range_m`/`los_rate_hold_range_m` semantics with τ-based fields: `acro_tau_s: float = 0.4` (keep), add `commit_tau_dot: float = 0.5` (Lee's τ̇ reference), `los_hold_tau_s: float = 0.15`.
- `fpv/guidance/pipeline.py` (278–281) — pass `estimated_tau_s` (and keep `estimated_range_m=None` — we have no range, Inv 1) into `command_from_guidance`.
- `fpv/guidance/bearing_rate.py`:
  - `GuidanceConfig.N` (243) — already a float field; falcon-low is just a *value* (`N=2.6`). **Add** a named constructor/preset or a `GuidanceConfig.falcon_low()` classmethod and/or a documented `N=2.6` default-off option. No law change — `N` already flows into `brn_az/brn_el` (438–439) and `N_effective` (512). Document the delay-robustness rationale (the module docstring already argues N=3 vs N=4; add the N≈2.6 / ≤0.84 g-airframe / PNAS-falcon note).

**Change / algorithm.**

1. **τ-driven terminal commit.** Replace `_is_terminal_phase` logic with a τ/τ̇ rule using the looming estimate. The cleanest honest signal we have is `looming.tau_s` (with `tau_confidence` gating) and a finite-difference `tau_dot`. Commit to terminal/acro when **τ falls below `acro_tau_s` AND `tau_confidence ≥ commit_tau_conf`** (a confident, imminent contact). Optionally arm on `tau_dot ≤ commit_tau_dot` (Lee: τ̇<0.5 ⇒ guaranteed arrival) as a secondary condition. Because τ self-scales with closure (faster closure ⇒ smaller τ ⇒ earlier commit), this replaces the fixed 1.0–1.4 s timer automatically. **Critical fail-safe:** τ_confidence collapses at saturation (blob fills FOV) — but per the roadmap that is *past* the commit point, so the commit fires while τ is still observable; once committed, **latch** terminal phase (do not un-commit when τ_confidence later drops). Add a latched `self._terminal_committed: bool` to the pilot.
   - `_is_los_hold_phase` → `tau_s < los_hold_tau_s` (and latched once entered, mirroring the existing `_los_frozen` latch at lines 221–229).
   - **Keep `estimated_range_m` parameter in the signature** (back-compat for tests/ToF future R11) but it must default to `None` and never be supplied by the wired pipeline (Inv 1: range is for CPA/fuze only, never timing the gain-bearing command path — though note terminal *timing* is not gain, we still prefer τ to keep range fully out of the loop).

2. **Pipeline wiring.** At `command_from_guidance` (pipeline 278–281), add:
   ```
   tau_arg = looming_est.tau_s if (looming_est.tau_confidence >= cfg.commit_tau_conf
                                   and math.isfinite(looming_est.tau_s)) else None
   ... estimated_tau_s=tau_arg, estimated_range_m=None, ...
   ```
   This is the actual "unwiring" fix — the terminal phase is currently dead code in production.

3. **Falcon-low N≈2.6.** Pure config. Add `GuidanceConfig.falcon_low()` returning `GuidanceConfig(N=2.6, ...)` and document: low N matches a low-g, rate-limited airframe (≤0.84 g) and is more delay-robust (the existing docstring's miss∝N·Vc·T_d² argument). Default stays `N=3.0`. The blend already slides `N_effective` from 1→N (line 512), so N=2.6 composes cleanly.

**New / changed tests + acceptance thresholds.** New file `fpv/guidance/tests/test_r3_tau_terminal.py`:
- *τ triggers terminal, range does not:* with `estimated_range_m=None` and a `LoomingEstimate` ramping τ 2.0→0.3 s at `tau_confidence=0.8`, assert terminal/acro engages exactly when `tau_s < acro_tau_s`, and that supplying a small `estimated_range_m` has **no effect** (range fully removed from the trigger).
- *Closure-speed self-scaling:* two closing-geometry sims, fast vs. slow closure; assert the fast-closure case commits terminal at the **same τ** (≈`acro_tau_s`) but **earlier in wall-clock/range** — demonstrating τ self-scaling vs. a fixed timer.
- *Commit latches through saturation:* once committed, drop `tau_confidence`→0 (saturation); assert terminal phase stays latched (no un-commit, no acro chatter).
- *Low-confidence τ does not commit early:* `tau_confidence < commit_tau_conf` with small τ must **not** trigger terminal (default-deny / no premature acro).
- *Falcon-low N:* assert `GuidanceConfig.falcon_low().N == 2.6` and that a fixed λ̇ yields `brn_az` scaled 2.6/3.0 vs. default; assert the command still respects the ≤0.84 g clamp (Inv 5).
- Update `fpv/guidance/tests/test_pipeline.py` (already modified per git status) to assert `estimated_tau_s` is now passed through.

**Doctrine-invariant compliance.**
- **Inv 1 (range never scales gain):** R3 *removes* range from the terminal trigger entirely (`estimated_range_m=None` in the wired path); τ is a passive optical observable, not range, and it times *phase switching*, never the `N·Vc·λ̇` gain. Falcon-low changes `N` (a fixed scheduled constant), not a range coupling.
- **Inv 2:** τ/looming is a geometric optical cue (area growth), not AI/appearance; it gates timing/engage-phase, consistent with doctrine's "looming → engage-permission/timing only."
- **Inv 3 (ABORT is a PASS):** low-confidence τ → no commit (default-deny on doubt); never a premature acro into a wrong-hit.
- **Inv 5 (≤0.84 g, corrections before the ten-τ wall):** τ-driven commit *is* the ten-τ-wall enforcement done honestly; the acro amplification (line 237, ×1.3) still passes through the `_clamp(...,−1,1)` and the downstream g-clamp, so ≤0.84 g holds.

**Dependencies.** **Soft-depends on R2** only in that both want looming/λ̇ to be trustworthy, but R3 is independently shippable. **Shares `pipeline.py` lines 262–283 with R1** (R1 edits ~227–255, R3 edits ~278–281 — adjacent, land R1 first). No file conflict with R2 (R2 = imm/bearing_rate filter internals; R3 = command_map phase logic + the N value).

**Risk & S3-gate sensitivity.** Changes *when* the terminal/acro phase fires in the closed loop → **must re-run S3.** The acro ×1.3 amplification near impact is the sensitive part; a too-early commit (bad τ) could amplify a glint-driven command. Mitigated by the `commit_tau_conf` gate + latch. Default-off: keep the legacy range/fixed-timer path behind a `PilotConfig.use_tau_terminal: bool = True` toggle for A/B. Falcon-low N is inherently opt-in (non-default value).

**RPi5 bench-testability.** Closing-geometry sims with varied closure speed (roadmap §5 R3 "closing-geometry sims with varied closure speed"); assert commit-τ invariance and range-independence offline. Latency: one finite-difference + comparisons per frame, negligible vs. 17 ms.

**Recommended executor model.** **sonnet** for the falcon-low N option and the pipeline wiring (mechanical, well-bounded). **strong** for the `_is_terminal_phase` τ/τ̇ commit logic + latch (terminal-phase timing is endgame-critical; a wrong commit feeds the acro amplifier near impact). **Recommendation: assign R3 to strong**, but it is the most splittable — the N option and pipeline-passthrough could be a sonnet sub-task if parallelized.

---

### Honest gaps / what cannot be fully specified without more research or measurement

1. **R1 — the bearing→pixel inverse primitive.** I confirmed `geometry.py` provides `pixel_to_bearing` (used in `los.py`); I did **not** verify an inverse `bearing_to_pixel` exists. If it does not, R1 must add it (trivial: `x=cx+f·tan(az)`, `y=cy−f·tan(el)`), but the implementer must read `geometry.py` first to match the exact intrinsics fields and the el sign convention (`pixel_to_bearing(py)=atan2(-(py-cy),f)`, per los.py line 58).

2. **R2 — the true `extent_px` source.** I used `sqrt(area_px)` as a proxy because `area_extended_px` is computed in `detect.py` but on a different 180×180-window scale (pipeline lines 257–261 explicitly warn its scale doesn't match looming, and there's a look-down border artefact). A *correct* extent for R-inflation needs either R4/R5's silhouette extent or a validated window-scale-matched extent. **Until then, R2's R-inflation should ship with `r_extent_k=0` (no-op) by default and the `sqrt(area)` proxy gated behind an explicit opt-in**, flagged as needing the R4/R5 extent to be trustworthy.

3. **R3 — `tau_dot` reliability and the `commit_tau_conf` value.** Lee's τ̇=0.5 reference is theoretically clean, but `tau_dot` is a finite difference of an already-noisy τ; its usable SNR on the **real FT640 post-AGC** signal is **unmeasured**. The exact `acro_tau_s`/`commit_tau_conf`/`los_hold_tau_s` thresholds need tuning against real or high-fidelity replayed closing sequences (a roadmap MEASUREMENT task: real NETD/post-AGC clutter PDF on the RPi5 bench). I specified the *mechanism* and conservative defaults; the *numbers* are provisional until that bench measurement exists. Recommend shipping τ-commit with the latch + a frame-count backstop (so a degenerate τ cannot indefinitely defer commit).

4. **S3 re-run cost is real for all three.** R1 (gate centre), R2 (λ̇ smoothing + Huber), and R3 (terminal-phase timing) each perturb the closed loop. They should be merged behind their default-off toggles, then S3 re-run **once** with the intended-on combination, rather than three separate slow S3 cycles — coordinate the sequencing (R1→R3 share `pipeline.py`; R2 is file-disjoint and can run in parallel up to the shared final S3 gate).

**Relevant file paths:** `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/track.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/imm.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/los.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/looming.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/bearing_rate.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/command_map.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/pipeline.py` (lines 227–283 are the integration seam for all three).

---



<!-- cluster: spec-tier1a -->

The `thermal_sim` renders a single Gaussian PSF with a configurable `target_sigma_px` (no aspect/silhouette structure), and `seeker_sim` likewise. This is an important honesty point: there is currently **no extended-shape / aspect-rotating winged-UAV thermal renderer**, which R5's aimpoint-walk-vs-aspect acceptance metric requires. I have enough to write the spec now.

I have all the grounding I need. Here is the spec.

## Cluster R4–R5: Closure-Phase REGIME Staging + Aimpoint Migration (the missing critical-path stage)

These two tasks form one logical stage: R4 introduces a *regime* axis (target angular scale) orthogonal to the existing lifecycle FSM, and R5 changes what the aimpoint *is* in each regime. They share `track.py` and the `area_extended_px` cue, so they must be co-designed; I spec them as separable deliverables (R4 can land and be useful alone; R5 depends on R4's regime output) but flag the shared-file conflict explicitly.

A structural fact that shapes both specs, verified in the code: **the centroid that guidance ultimately consumes is `snap.centroid_px`**, set in `track.py::_on_associated` to `blob.centroid_px` and read in `pipeline.py::step` at line 240 (`self._los.update(centroid_px=snap.centroid_px, ...)`). Everything R4/R5 does either (a) writes to a new lock-quality/regime field that guidance does not read, or (b) changes which *pixel* becomes `centroid_px` — and (b) is the LOS spine, so it is safety-critical and S3-gated. I separate the two carefully below.

---

### R4 — REGIME state machine (POINT → RESOLVED → FILL), hysteretic, keyed on `area_extended_px` / top-hat area-collapse

**ID & goal.** Promote the dormant `area_extended_px` cue (computed in `detect.py` lines 483–488, carried on `ThermalBlob.area_extended_px`, currently read by nothing) to a first-class, hysteretic *regime* state that classifies the target's angular scale (POINT / RESOLVED / FILL) and publishes it for R5 (aimpoint), R2 (R-inflation), and the coast-budget logic — **without** ever writing to centroid/LOS.

**Files & exact locations.**
- `track.py` (primary):
  - **Add** `class TargetRegime(str, Enum)` near `TrackingState` (after line 87): `POINT`, `RESOLVED`, `FILL`.
  - **Add** a `RegimeConfig` dataclass (or fields on `ThermalLockConfig`, line 103–161) holding the two hysteresis thresholds and the collapse-ratio threshold.
  - **Add** a `RegimeClassifier` (small stateful helper, ~40 lines) OR inline state on `ThermalLockTracker.__init__` (line 254): `self._regime = TargetRegime.POINT`, plus rolling references `self._area_px_peak`, `self._area_ext_ref`.
  - **Change** `ThermalLockTracker.update()` (line 325): after a successful association in `_on_associated` (line 377), call `self._update_regime(blob)` and stamp the result.
  - **Change** `ThermalLockSnapshot` (line 168–206): add field `regime: TargetRegime = TargetRegime.POINT` and emit it in `to_dict`. Add `area_extended_px: int = 0` and `top_hat_area_px: int = 0` passthrough for observability.
  - **Change** `_on_associated` (lines 405–416) and the coast/miss/empty snapshot builders (lines 438–477, 490–501, 646–657) to carry `regime` through (frozen on coast — do not reclassify with no observation).
- `pipeline.py`:
  - **Change** `PipelineOutput` (line 44) to add `regime: str = "POINT"` (observability only; **not** read by guidance/control).
  - **Change** `step()` (after line 227 `snap = self._tracker.update(obs)`) to surface `snap.regime.value` into `PipelineOutput`.
- `detect.py`: **no change required** — `area_extended_px` is already computed for the top-K salient blobs. (One honest caveat below about which blob carries it.)

**Change / algorithm.**

Regime is keyed on **two** signals, exactly as the roadmap states (`area_extended_px` AND top-hat-area-collapse):

1. `area_extended_px` (the un-suppressed half-max footprint) is the *growth* signal — it keeps climbing as the target resolves, where `area_px` saturates.
2. The **collapse ratio** `c = area_px / max(area_extended_px, 1)` is the *resolution* signal: for a true point target the top-hat passes the whole blob so `c ≈ 1`; once the target resolves, the white top-hat suppresses the interior and `area_px` collapses while `area_extended_px` keeps growing, so `c → 0`. This collapse is the physically-grounded "the centroid is about to become unreliable" trigger (per doc M2, lines 65 and 225).

Classification (hysteretic Schmitt-trigger on a scale proxy `s = area_extended_px`, gated by collapse `c`):

```
POINT    → RESOLVED : area_extended_px >= A_resolve_px AND c <= c_collapse   (sustained K_promote frames)
RESOLVED → FILL     : area_extended_px >= A_fill_px                          (sustained K_promote frames)
FILL     → RESOLVED : area_extended_px <  A_fill_px * (1 - hyst)             (sustained K_demote frames)
RESOLVED → POINT    : area_extended_px <  A_resolve_px * (1 - hyst)          (sustained K_demote frames)
```

- Hysteresis band `hyst` (e.g. 0.3) and separate promote/demote dwell counts (`K_promote=3`, `K_demote=5` — demotion is slower, because spuriously dropping back to POINT re-enables hotspot aimpoint, which is the failure we are trying to avoid) prevent chatter on a target hovering near a threshold.
- The thresholds `A_resolve_px`, `A_fill_px` are in `area_extended_px` units (the 180×180-window footprint scale — **not** `area_px`, and **not** the `LoomingConfig` scale; see the explicit warning in `pipeline.py` lines 257–261). Concrete starting values, derived from the simulator's analytic target area (`thermal_sim.py::_target_area`, `≈ π·(1.177·σ)²`): at σ=1.5 px a point target footprint is ~10 px; `A_resolve_px ≈ 80` (≈ a target ~5 px radius at half-max), `A_fill_px ≈ 6000` (≈ a target filling a meaningful fraction of the window). **These must be tuned against the bench scale-sweep — see "cannot be fully specified" note below.**
- On coast (`missed_frames > 0`) the regime is **frozen**, not reclassified — there is no fresh `area_extended_px`. This mirrors the existing coast philosophy in `_on_missed`.

Regime is published on the snapshot; **the regime value never alters `centroid_px` in R4**. R4 is purely a classifier + plumbing. (R5 is what makes the regime *do* something to the aimpoint.)

Honest caveat carried into the spec: `detect.py` computes `area_extended_px` only for the **top-3 salient blobs** (line 80, `_EXTENDED_AREA_TOP_K`). The tracker's associated blob is usually salience-rank 0, but during a clutter crossing it may not be in the top-3, in which case its `area_extended_px == 0` and the regime would spuriously read POINT. **Mitigation (in scope for R4):** when the associated blob has `area_extended_px == 0` but `area_px` is large, fall back to the last valid regime (freeze) rather than forcing POINT. A cleaner fix (compute `area_extended_px` for the tracked blob specifically) is a `detect.py`/`pipeline.py` change that should be called out as a **follow-on**, not bundled here.

**New / changed tests + ACCEPTANCE THRESHOLDS.** New file `tests/test_regime.py`:
- **Monotone promotion:** feed a synthetic scale-sweep (reuse `thermal_sim.py` with `target_sigma_px` ramped 1.5 → 60 over N frames, or a direct `area_extended_px` ramp into `ThermalLockTracker`); assert the regime sequence is monotone non-decreasing POINT→RESOLVED→FILL with **no back-transition** during a pure closing ramp.
- **Hysteresis / no chatter:** drive `area_extended_px` as a noisy signal dithering ±25% around `A_resolve_px`; assert **fewer than 1 transition per 20 frames** (chatter-rejection), versus the un-hysteretic comparison which must show ≥5×.
- **Collapse gate:** a *bright-but-still-point* glint (high `area_px`, `area_extended_px` small, `c ≈ 1`) must **stay POINT** — assert regime never promotes on intensity alone.
- **Coast freeze:** during a missed-frame coast the regime equals its pre-coast value for every coasted frame (assert no reclassification with `associated_blob is None`).
- **Top-K dropout fallback:** associated blob with `area_extended_px == 0` and large `area_px` does **not** force POINT (assert regime holds last value).
- **Doctrine guard test (critical):** in a sequence where regime cycles POINT↔RESOLVED↔FILL, assert `snap.centroid_px` is **bit-identical** to a baseline run with the regime classifier disabled — i.e. R4 provably does not move the LOS. This is the Invariant-2 firewall test.

**Doctrine-invariant compliance.**
- **Inv 2 (AI/appearance signals never write centroid/LOS/tracker):** R4 writes only a new `regime` field that guidance does not read; the "Doctrine guard test" above proves `centroid_px` is unchanged. `area_extended_px` is a deterministic CV cue, not learned, but it is an *appearance/scale* signal, so it is correctly confined to the regime/quality plane.
- **Inv 1 (range never scales gain):** `area_extended_px` is a pixel footprint, **not** a range estimate, and the regime output feeds aimpoint/gate/R, **never** `N·Vc·λ̇`. No guidance-gain path touches regime.
- **Inv 4 (IMM stays modified-polar):** untouched; regime is upstream of the IMM and writes nothing to it.
- **Inv 7 (no new track post-commit):** regime is a *property of the same committed track*; it never spawns or re-seeds a track. Confirm the classifier resets in `seed()` (line 277) so a fresh designation starts at POINT.

**Dependencies.** None must land first (R4 is Tier-0-adjacent — the cue already exists). Shares `track.py` and `ThermalLockSnapshot` with **R1** (IMM-coast wiring) and **R5** (aimpoint). Conflict risk with R1 is moderate (both edit `_on_associated`/`_on_missed`/snapshot); recommend R4 and R1 land in a coordinated branch or R1 first. R5 **depends on** R4's `regime` field.

**Risk & S3-gate sensitivity.** **Does NOT change the closed-loop guidance path** (it only adds an unread field) — so it does **not** require a full slow S3 re-run for correctness, though one regression S3 pass is cheap insurance. Fully **default-off-able**: gate behind a `regime_enabled: bool = False` config flag; when off, `regime` is pinned POINT and nothing downstream changes. Low risk.

**RPi5 bench-testability.** Validate now with the scale-sweep replay (`thermal_sim` σ-ramp) on the bench; assert the regime trace promotes at the expected frame. **Latency:** essentially free — `area_extended_px` is already computed (the only existing cost, and it's already top-K-capped per `_EXTENDED_AREA_TOP_K`); the classifier is a handful of scalar comparisons per frame (<<1 µs). No 17 ms-budget concern.

**Recommended executor model.** **sonnet.** Well-bounded, mechanical: an enum, a hysteretic comparator, field plumbing through existing snapshot builders, and deterministic tests. The only subtlety (collapse-ratio direction, coast-freeze) is fully specified above.

---

### R5 — AIMPOINT MIGRATION: hotspot (POINT) → MTI-registered silhouette-centroid + forward velocity-vector bias (RESOLVED/FILL)

**ID & goal.** Make the aimpoint a function of regime: in POINT keep today's intensity-weighted hotspot centroid (the current `blob.centroid_px`); in RESOLVED/FILL migrate to a **silhouette centroid** computed from an MTI-registered frame-difference mask (reusing `mti.py`'s ORB+RANSAC homography), plus a small **forward velocity-vector bias** toward the winged body's leading volume. This is the single most important missing critical-path stage (doc lines 37, 65, 103, 176): the hotspot *walks across the airframe as aspect rotates*, injecting a λ̇ disturbance exactly at the endgame.

**This task changes the LOS spine.** Unlike R4, R5 changes which pixel becomes `centroid_px`. It is therefore safety-critical, S3-gated, and must be default-off.

**Files & exact locations.**
- `mti.py`:
  - **Add** a public method `MotionGate.last_homography() -> np.ndarray | None` (or `register(prev, cur) -> H`) exposing the homography already computed internally in `_register` (lines 88–123). Today `_register` returns the *warped frame* and discards `hmat`; R5 needs the matrix (and the inlier mask / quality) to warp the previous frame around the **target ROI** specifically. Add `self._last_hmat` / `self._last_inliers` storage and a `homography_quality` property (inlier fraction) so the aimpoint can be confidence-gated.
  - The near-identity guard (lines 112–121) already prevents a homography that registers the *target* instead of the background — reuse it; if it fails, R5 must fall back to the POINT aimpoint (see below).
- **New module** `seeker/aimpoint.py` (keep this out of `track.py` to avoid a numpy dependency in the pure-python tracker, mirroring `track_manager.py`'s "numpy-free" design note):
  - `class AimpointMigrator` with `compute(frame_f, prev_frame_f, blob, regime, homography, hquality, los_velocity_dir) -> tuple[centroid_px, aimpoint_quality]`.
  - Algorithm (RESOLVED/FILL only): extract the ROI around `blob.bbox` (padded by a margin); warp `prev_frame_f` ROI into the current frame via `homography`; compute the **registered frame difference** `D = |cur_roi − warped_prev_roi|`; threshold (percentile+MAD, reusing the `detect._compute_threshold` pattern) to a **silhouette mask**; take the **largest connected component** containing/nearest the blob centroid; compute its **geometric (binary) centroid** = the silhouette centroid. Then apply the **forward bias**: shift the aimpoint a fraction `beta_fwd · r_silhouette` along the unit LOS-velocity direction (from the IMM `az_rate/el_rate`, projected to pixels, or from the tracker's `_velocity_px_per_frame`) toward the leading edge — bounded so it can never leave the silhouette mask.
- `pipeline.py` `step()`:
  - **Change** lines 227–240: after `snap = self._tracker.update(obs)` and after the MTI block (lines 170–195, which already runs the MotionGate), when `regime != POINT` **and** MTI homography quality is above threshold, call the migrator and **substitute** the centroid handed to `self._los.update(...)` at line 240. When regime == POINT, or homography quality is low, or the silhouette mask is degenerate → use `snap.centroid_px` unchanged (fail-safe to the current behaviour).
  - The MotionGate is currently only constructed when `motion_gate=True` (line 89). R5 needs a registered frame difference regardless of whether the MTI *gate* is on. **Decision:** R5 constructs/uses its own `MotionGate` (or shares the existing one) but the *aimpoint substitution* is independently flagged (`aimpoint_migration=True`), so the two features are decoupled.

**Change / algorithm (precise).**

```
aimpoint(frame, prev, blob, regime, H, q, v_dir):
    if regime == POINT or H is None or q < q_min:
        return blob.centroid_px, quality=baseline      # FAIL-SAFE: today's hotspot
    roi = pad(blob.bbox, margin)
    warped_prev = warp(prev[roi], H_local)             # background registers, target leaves residual
    D = abs(cur[roi] - warped_prev)
    mask = D > (median(D) + k*MAD(D))                  # silhouette = independently-moving pixels
    comp = largest_cc_containing(mask, blob.centroid_in_roi)
    if comp.area < min_silhouette_px:                  # degenerate -> fail-safe
        return blob.centroid_px, quality=baseline
    c_sil = binary_centroid(comp)                      # geometric, NOT intensity-weighted
    c_aim = c_sil + beta_fwd * r_eff * unit(v_dir)     # forward bias toward leading volume
    c_aim = clamp_into(c_aim, comp)                    # bias can never exit the silhouette
    return roi_to_image(c_aim), quality=f(q, comp.solidity)
```

Key physics/design points:
- The silhouette centroid is a **geometric** (binary) centroid of the *moving-region* mask — this is precisely what removes the intensity/AGC/aspect dependence that walks the hotspot (doc §1.2, line 225: "thresholding couples the centroid to AGC and background"). It is **not** intensity-weighted.
- The **forward velocity-vector bias** (`beta_fwd`, e.g. 0.25) nudges the aimpoint from the body-geometric-centroid toward the leading edge along the closure vector — the doctrine-correct hit point for a winged body (doc lines 104, 133–134, 176). It is clamped inside the silhouette so it cannot run off the target.
- **Mutual fail-safe to POINT** at every degeneracy (low homography quality, mask too small, low solidity, NaN) — the aimpoint *only* migrates when the registered-difference evidence is strong; otherwise it is bit-identical to today. This is the conservative, default-deny posture.
- `aimpoint_quality` is published to the **lock-quality channel only** (Inv 2) — it never gates the LOS *value*, only informs the commit/engage gate that the aimpoint source changed.

**New / changed tests + ACCEPTANCE THRESHOLDS.** New file `tests/test_aimpoint.py`:
- **Aimpoint-walk vs aspect (the headline metric, doc line 176):** render a winged-UAV thermal whose hotspot (motor glow) sits off the geometric centroid and *rotates* across the body as aspect sweeps 0°→90°. **Acceptance: silhouette-centroid aimpoint walk < 0.2° across the full aspect sweep**, versus the hotspot centroid which must show ≥3× larger walk on the same sequence. **(See blocking caveat below — this renderer does not yet exist.)**
- **λ̇ disturbance reduction:** on a closing sequence with a migrating hotspot, the **λ̇ RMS with aimpoint migration drops ≥30%** versus hotspot-only, with no added lag (cross-correlation peak at zero shift, within ±1 frame).
- **Fail-safe identity:** when homography quality < `q_min` (textureless / static scene → MTI returns identity per `mti.py` line 102), the migrated centroid is **bit-identical** to `snap.centroid_px` (assert the POINT path).
- **Regime gating:** in POINT regime the aimpoint is **always** `blob.centroid_px` (assert no migration before resolution).
- **Bias bound:** the forward-biased aimpoint is **always inside the silhouette mask** (assert clamp), across a range of `v_dir` and `beta_fwd`.
- **Reacquire-same-track guard (Inv 7):** migration never changes track identity; assert the tracker state/ID is unchanged across a regime transition.

**Doctrine-invariant compliance.**
- **Inv 2 (the central one):** This is the delicate case — R5 *does* change `centroid_px`, which looks like writing the LOS. It stays compliant because the new aimpoint is computed by a **deterministic CV operation (registered frame difference + binary centroid)**, *not* by any AI/learned/appearance-model signal. The doctrine forbids *learned/appearance/scene* signals on the centroid; a geometric segmentation of the *moving* region is the doctrine-sanctioned aimpoint (doc lines 39, 103, 133 explicitly prescribe "silhouette-centroid via MTI-registered frame difference" as the *correct* aimpoint). The `aimpoint_quality` scalar — the only thing that could be construed as a confidence/appearance signal — is routed to lock-quality **only**, never to the LOS value. **This distinction must be stated in the PR and enforced by the fail-safe test.**
- **Inv 1 (range never scales gain):** the migrator uses no range; the forward bias is a fraction of the *pixel* silhouette radius, not a metric distance. λ̇ still drives `N·Vc·λ̇` unchanged.
- **Inv 4 (IMM modified-polar):** the IMM is fed the migrated centroid through the *same* `los.update → imm.update` path; no Cartesian range rewrite. The IMM consumes `v_dir` read-only.
- **Inv 5 (≤0.84 g, in-FOV, pre-ten-tau):** migration must be frozen/heavily-damped inside the ten-τ wall in FILL (doc line 134: "late innovations can only add miss") — **spec requirement:** in FILL within the terminal window the aimpoint is rate-limited (slew cap) so a late silhouette flicker cannot inject a large step. This is an explicit guard, tested.
- **Inv 7 (no new track post-commit; re-acquire SAME track):** migration is a property of the committed track; it spawns nothing. Tested.

**Dependencies.** **Depends on R4** (needs the `regime` field). Shares `pipeline.py::step` with R1/R2 (IMM wiring) and `mti.py` with the MTI gate. Conflict risk on `pipeline.py` line ~240 (the `los.update` call) is **high** — R5 substitutes the centroid argument there, R1/R2 add IMM-feedback around it. Coordinate ordering: R4 → (R1) → R5.

**Risk & S3-gate sensitivity.** **Changes the closed-loop guidance path — MUST re-run the full slow S3 acceptance** (closed-loop S1/S2/S3 in `test_acceptance.py` / `test_s2_acceptance.py`). This is the highest-risk task in the cluster. **Default-off mandatory:** gate behind `aimpoint_migration: bool = False` in `SeekerGuidancePipeline.__init__` (line 79 neighbourhood); when off, the LOS spine is the current code exactly. Opt-in, with the regime+homography fail-safes meaning even when on, it degrades to identity whenever evidence is weak.

**RPi5 bench-testability & latency.** Validate with the aspect-sweep + closing-geometry replay on the bench; measure aimpoint walk and λ̇ RMS. **Latency is a real concern:** the ORB+RANSAC homography in `mti.py::_register` is the dominant cost and currently runs only when `motion_gate=True`. R5 needs a homography on resolved/closing frames. **Budget mitigations (in scope):** (a) reuse the homography MotionGate already computed (do not recompute); (b) run the registered difference on the **ROI only** (target bbox + margin), not the full frame; (c) only run migration in RESOLVED/FILL (POINT is the long early phase and stays free). The ROI-confined difference + binary centroid is cheap (~a few hundred µs); the homography is the risk and must be **profiled on the Pi5** to confirm the per-frame total stays under 17 ms when migration is active. If the homography is shared with an already-on MTI gate, the marginal cost is just the ROI difference.

**Recommended executor model.** **strong.** This is safety-critical (changes the LOS the guidance law nulls), touches Invariant 2 at its most subtle boundary, requires the careful fail-safe cascade and ten-τ slew-limit, and shares the highest-conflict line in `pipeline.py`. Correctness here is the difference between a stable terminal aimpoint and a self-inflicted λ̇ disturbance.

---

### Cross-cutting honesty flags (cannot be fully specified without more work)

1. **No aspect-rotating winged-UAV thermal renderer exists.** Verified: `thermal_sim.py` renders a single isotropic Gaussian PSF (`target_sigma_px`, `_gaussian2d`, `_target_area`) and `seeker_sim.py` likewise — neither has airframe silhouette, a hotspot offset from the geometric centroid, or aspect rotation. **R5's headline acceptance metric ("aimpoint walk < 0.2° across 0–90° aspect") cannot be measured until this renderer is built.** This is a prerequisite sub-task: an extended-target thermal generator (elongated/winged intensity profile + a movable motor-hotspot + aspect parameter + independent target-vs-background motion so MTI has a residual to find). **Estimate this as a distinct deliverable before R5's acceptance can be graded**; without it, R5 can only be unit-tested on synthetic masks, not validated on the metric that justifies it. Recommend folding this into the A5 Monte-Carlo harness extension (doc line 195 already calls for an "aimpoint-walk-vs-aspect metric" under A5).

2. **`area_extended_px` thresholds (`A_resolve_px`, `A_fill_px`) are unmeasured.** The values I gave are derived from the simulator's analytic Gaussian area, not from real FT640 footprints. They must be calibrated against bench replay (and ideally real field clutter, per the doc's "MEASUREMENT tasks"). Spec them as config, not constants, and tune on the scale-sweep.

3. **`area_extended_px` top-K coverage gap** (only top-3 salient blobs get it computed). The R4 fallback handles it safely (freeze regime), but the clean fix — computing `area_extended_px` for the tracked blob specifically — is a small `detect.py`/`pipeline.py` follow-on worth scheduling.

Relevant files: `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/track.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/detect.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/blob.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/mti.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/pipeline.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/thermal_sim.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/seeker_sim.py`; new: `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/aimpoint.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/tests/test_regime.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/tests/test_aimpoint.py`.

---



<!-- cluster: spec-tier1b -->

I have everything I need. The critical architectural facts are now exact:

- `los.py` `LOSComputer.update()` already maintains `_prev_world_px` and produces de-rotated world pixels — R6 must reuse the same de-rotation but it cannot write into `LOSObservation.az_rate/el_rate` without touching the LOS spine (Inv 2 / Inv 4 tension — the honest crux).
- Guidance reads lambda-dot at `bearing_rate.py:367-368` straight off `imm.az_rate_radps`. The only Inv-2-clean way for R6 to feed lambda-dot "preferentially" is as a **measurement into the IMM** (the IMM remains the sole LOS authority), not as a side-channel that bypasses it.
- R7 has both halves already built: `mti.py` `MotionGate.update()` returns the motion mask, and `track_manager.py` `MultiTrackManager` does N-of-M continuity. The gap is purely the **consensus AND-gate before LOCKED** and a **2-hypothesis carry**, wired in `pipeline.py` (which already instantiates both behind flags).

Here is the spec.

## Cluster R6–R7 — Invariance & Consensus (synthetic-event λ̇ channel + intensity∧motion consensus / 2-hypothesis clutter carry)

Both tasks live in the seeker perception layer and are wired through `SeekerGuidancePipeline.step()`. R6 sharpens the λ̇ measurement against AGC/background nuisances; R7 hardens the LOCKED decision and clutter-crossing survival. They share `pipeline.py` and the `mti.py`/`los.py` de-rotation primitive, so they are specified to land R6→R7 (R7 reuses R6's de-rotated-difference frame for free) but can be developed in parallel against separate test files.

---

### R6 — Synthetic-EVENT log-contrast λ̇ channel

**ID & goal.** Compute a per-pixel d(log I)/dt motion field on **de-rotated** frames, take its first moment inside the IMM gate to produce an AGC/background-invariant LOS-rate measurement, and feed it **into the IMM as an additional rate measurement** (the IMM stays the sole LOS authority) — a cleaner λ̇ under glint/AGC/background-march, honestly an *invariance* win, not a µs-latency win (bolometer τ ≈ 10–15 ms caps the speed benefit).

**Files & exact locations.**
- **NEW** `fpv/seeker/event_channel.py` — `EventLambdaConfig` (frozen dataclass) + `EventLambdaChannel` class with `update(frame_u16, roll_rad, shift_px, centroid_px, gate_px, dt) -> EventLambdaObservation | None` and `reset()`. Holds the previous de-rotated log-frame (mirrors `MotionGate`'s history-of-one pattern, `mti.py:53`).
- **REUSE, do not duplicate, the de-rotation math** in `los.py:273-286` (`LOSComputer.update` STEP 2: `theta=_cum_roll_rad`, inverse-rotation to world pixel). Factor that block into a module-level helper `derotate_frame(frame_f, cum_shift_px, cum_roll_rad, intrinsics) -> ndarray` in a new `fpv/seeker/derotate.py`, and have **both** `los.py` (pixel-domain, unchanged behaviour — call it on the centroid only) and `event_channel.py` (whole-frame `cv2.warpAffine`/numpy-grid resample) call it. This keeps a single source of truth for the ego-inversion sign chain.
- **CHANGE** `imm.py`: `IMMEstimate` gets two diagnostic fields `event_lambda_used: bool=False`, `event_residual_radps: float=0.0`. `IMMFilter.update()` gains an **optional** `event_obs: EventLambdaObservation | None = None` kwarg. When present and `event_obs.confidence >= cfg.event_min_confidence`, the rate channels of the measurement vector `z[2], z[3]` (imm.py:360) are replaced by (or precision-weighted-blended with) the event λ̇, and the rate-channel `R_frame[2,2]/[3,3]` (imm.py:409-411) is set from the event channel's reported variance. New `IMMConfig` fields: `event_min_confidence: float=0.5`, `event_blend: Literal["replace","precision"]="precision"`.
- **CHANGE** `pipeline.py`: in `__init__`, add `event_channel: bool=False` flag → instantiate `EventLambdaChannel` (default OFF). In `step()`, after the ego `gyro_derotation` call (line 238) and before `self._imm.update` (line 242), call the channel with the **same roll-only ego** the LOS uses (pipeline passes only `omega_z`; the event de-rotation must use the identical `_cum_*` accumulation to stay phase-aligned), then pass `event_obs` into `self._imm.update(los_obs, dt, event_obs=event_obs)`. Reset the channel on `ffc_state != "READY"` exactly as MTI does (pipeline.py:170-175).

**Change / algorithm.**
1. `L_k = log(max(frame_f, 1.0))` (1.0 floor; 8-bit AGC frames are `uint16`-cast but ≤255 effective — the log kills the multiplicative AGC gain `g_k`: `log(g_k·I) = log g_k + log I`, and the *temporal difference* removes the spatially-uniform `log g_k` term to first order, plus any static background).
2. De-rotate `L_k` into the world frame via `derotate.derotate_frame` using the pipeline's cumulative `(shift_px, roll_rad)` (same accumulators as `los.py`). Keep the previous de-rotated log-frame `L_{k-1}^world`.
3. `dLog = (L_k^world − L_{k-1}^world) / dt` over the registered overlap region; zero the border invalidated by warp.
4. Restrict to the **IMM gate disc** (centre = tracked `centroid_px`, radius = `gate_px` from `tracker.gate_px`) — never the whole frame (keeps it in budget and avoids voting on distant clutter). Inside the disc, the **motion field first moment**: weight each pixel by `|dLog|` (a contrast-change magnitude, AGC-invariant), compute the intensity-of-change-weighted centroid displacement vs. the previous frame's change-centroid → pixel velocity `(v_x, v_y)`; convert to `(az_rate, el_rate)` with the *same pinhole formula* as `los.py:315-316` (`az_rate = v_x·f/(f²+dx²)`, `el_rate = −v_y·f/(f²+dy²)`).
5. `confidence` = function of in-disc change-energy SNR (median/MAD of `|dLog|` inside vs. an annulus outside), saturating to 0 when too few moving pixels (textureless / hovering target with no contrast change → fall back to the centroid-difference λ̇, i.e. return `None`). Report `var_radps2` from the change-energy (lower energy → higher variance → IMM trusts it less).
6. **Output** `EventLambdaObservation(az_rate_radps, el_rate_radps, confidence, var_radps2, n_pixels, frame_id)`.

Data flow stays Inv-2/Inv-4 legal **only because the event λ̇ enters as a measurement into the IMM**, which remains the single LOS producer; it does **not** create a parallel λ̇ that bypasses the filter into `bearing_rate.compute` (which reads `imm.az_rate_radps` at `bearing_rate.py:367`). This is the load-bearing design decision.

**New / changed tests + ACCEPTANCE THRESHOLDS.** New `fpv/seeker/tests/test_event_channel.py`:
- **AGC-invariance:** render a closing target with a per-frame multiplicative AGC gain sweep (±40% gain ramp) and a marching background (sky→horizon→ground brightness shift, reproducible via a new `SeekerSimConfig.agc_gain_fn`/`background_march` — see RPi5 section). λ̇ RMS error vs. ground-truth `target_lambda_dot_*` must **drop ≥ 30%** with the event channel ON vs. the centroid-difference baseline. (Threshold matches the doc's "≥30% under glint"; if the rendered AGC stress is mild the realized gain may be lower — **acceptance is the relative improvement, asserted on the same sequence**.)
- **No-regression on clean frames:** with gain=1, background static, λ̇ output with channel ON must match baseline within **5% RMS** (the channel must not *hurt* the easy case).
- **Confidence gating:** a hovering target with zero contrast change must return `confidence < event_min_confidence` (channel declines, IMM uses centroid λ̇) — assert `event_lambda_used == False`.
- **Sign correctness:** target drifting right (+az ground truth) yields `event_obs.az_rate_radps > 0`; drifting up yields `el_rate_radps > 0` (guards against a flipped pinhole sign vs. `los.py`).
- **Budget:** see RPi5 section; assert in-test wall-clock of `EventLambdaChannel.update` on a 256×192 gate disc.

**Honest gap (stated explicitly):** the *magnitude* of the ≥30% improvement cannot be guaranteed without a **measured post-AGC clutter PDF and effective bit-depth** from the FT640 on the RPi5 bench (a listed MEASUREMENT task). The synthetic AGC/background model is a stand-in; until that field NETD/clutter measurement exists, R6's acceptance is **relative improvement on the synthetic stressor**, and the spec flags that the absolute terminal-wall benefit is unverified. Also honestly: because the bolometer cannot change temperature in µs, the channel sharpens λ̇ and removes AGC/background sensitivity but does **not** reduce sensor latency.

**Doctrine-invariant compliance.**
- **Inv 1 (range never scales gain):** untouched — R6 only changes the *λ̇ measurement*, never `Vc_sched` or `N`.
- **Inv 2 (AI/appearance writes only to lock-quality):** **borderline and the key review point.** The log-contrast field is a *physical motion* measurement, not a learned/appearance/scene-classification signal, so feeding it into the IMM's *rate measurement* is the same category as the existing centroid-difference λ̇ — permitted. It is **not** an appearance/scene cue and must never set lock-quality/engage-permission; it stays on the LOS-measurement side. The implementer MUST keep the event channel free of any learned or template component to stay on the legal side of Inv 2.
- **Inv 4 (modified-polar IMM):** preserved — event λ̇ is injected as `[az_rate, el_rate]` measurements in the existing 4-state polar vector; no Cartesian/range rewrite.
- Inv 3/5/6/7 untouched.

**Dependencies.** Depends on the `derotate.py` extraction (do this first; it is a pure refactor of `los.py:273-286` and must be covered by a characterization test asserting bit-identical LOS output before/after). Shares `pipeline.py` `step()` and `__init__` flag plumbing with R7 (conflict risk — coordinate the flag block). Shares the IMM `update()` signature change with nothing else currently. Does **not** depend on R1–R5.

**Risk & S3-gate sensitivity.** **Changes the closed-loop guidance path** (λ̇ into the IMM → `bearing_rate`), so the **slow S3 closed-loop acceptance MUST be re-run** with the channel both OFF (prove bit-identical to current 343-green baseline — the no-op-when-OFF contract) and ON. Default-OFF opt-in via `event_channel=False`; ship OFF, enable per-scenario. The precision-blend mode (vs. hard replace) reduces the risk of a bad event frame swinging the command.

**RPi5 bench-testability.** Validate by replaying synthetic closing-geometry sequences from `SeekerSim` with **new stressors**: add `agc_gain_fn: Callable[[int],float]` (per-frame multiplicative gain) and a `background_march` option to `SeekerSimConfig` so the bench can render the exact AGC-sweep + background-march sequence R6 targets (these renderer hooks are themselves a small prerequisite). Latency: whole-frame log+warp is the cost driver — **confine the warp+diff to the gate disc bounding box** (typ. ≤ 2×gate_px square ≈ 120²), not the full 256×192, to fit the ~17 ms/frame budget; assert measured `update()` ≤ ~2 ms on the bench. If the bounding-box warp still overruns, fall back to a numpy log-diff without sub-pixel warp (roll-only de-rotation is small per-frame).

**Recommended executor model.** **strong.** It changes the closed-loop guidance path, touches the IMM measurement model, and the Inv-2 boundary (motion-measurement vs. appearance) plus the pinhole sign chain are subtle correctness/safety-critical points. The `derotate.py` extraction sub-step alone is mechanical (sonnet-able), but the channel→IMM integration and S3 re-validation need strong.

---

### R7 — Intensity∧Motion CONSENSUS before LOCKED + 2-hypothesis clutter carry

**ID & goal.** Require the intensity blob and an independent MTI motion track to *agree* before the FSM is allowed to declare LOCKED (an intra-sensor 2-channel corroboration), and carry a **second-best hypothesis** through a clutter crossing, resolved by `track_manager`'s existing N-of-M continuity — so a coordinated jink hidden inside a horizon crossing cannot silently swap the lock onto clutter.

**Files & exact locations.**
- **CHANGE** `pipeline.py` `step()` consensus gate: the building blocks already exist — `self._mti.update()` returns the motion mask (pipeline.py:175) and `self._mtm` (`MultiTrackManager`) already runs N-of-M (pipeline.py:203-221). What's missing is the **AND before LOCKED**. Add, between the tracker `update` (pipeline.py:227) and the LOCKED transition's consumption, a consensus check that **gates the promotion to LOCKED**, not the centroid.
- **CHANGE** `track.py`: `ThermalLockTracker.update()` gains an optional `consensus_ok: bool = True` kwarg threaded into `_on_associated` (track.py:377). In the `CANDIDATE → LOCKED` branch (track.py:390-393) the transition fires only when `self._stable_frames >= stable_frame_count` **AND** `consensus_ok`; otherwise the tracker stays in CANDIDATE (holds, does not reset) accumulating consensus. Add `ThermalLockConfig.require_consensus_for_lock: bool = False` (default OFF → current behaviour bit-identical). This gates *presence promotion only* — it never moves `centroid_px` (Inv 2).
- **CHANGE** `track_manager.py`: add a `second_best()` / `carry_hypotheses()` accessor exposing the **top-2 confirmed-or-confirming tracklets** through a clutter crossing. The manager already keeps multiple `Tracklet`s and confirms on N-of-M (track_manager.py:237-247); add `MultiTrackManager.ranked_snapshots(k=2)` returning the k tracklets ranked by `(confirmed, hits_in_window, -mean_residual)`. No change to the confirmation math.
- **CHANGE** `pipeline.py`: introduce the **clutter-crossing trigger** — gate occupancy inside the tracker gate (count of post-MTI blobs within `tracker.gate_px` of the predicted centroid) `> ~1.2` average over a short window → enter "carry" mode: keep the committed-track hypothesis **plus** the single best alternate from `ranked_snapshots(2)`; on exit, the one that retained N-of-M continuity to the *committed identity's* propagated track wins. **The committed identity always has priority; the alternate may only be adopted if the committed hypothesis fails continuity AND the alternate satisfies the SAME-track re-association rule (Inv 7).**

**Change / algorithm.**
- **Consensus (M8):** define `consensus_ok` for the candidate blob as: the blob's bbox overlaps the MTI motion mask (reuse the exact `_is_mover` predicate already in pipeline.py:179-183) **AND** the blob is near a CONFIRMED `MultiTrackManager` tracklet (reuse `_continuous`, pipeline.py:212-219). I.e. consensus = (intensity-salient, already true since it's a detected blob) ∧ (MTI-moving) ∧ (trajectory-continuous). When `motion_gate`/`trajectory_continuity` flags are OFF, `consensus_ok` defaults True (no behaviour change). This is the AND-of-independent-channels the doc's M8 calls for, and it requires **no new detector**.
- **2-hypothesis carry (M9):** on the clutter-crossing trigger, the pipeline holds `(committed_centroid, alternate_centroid)`. The single-target `ThermalLockTracker` is **not** forked (Inv 7 forbids acquiring a new track post-commit); instead the alternate is carried *only inside the MultiTrackManager* (which is already a backstop that never touches the spine, track_manager.py docstring). At crossing exit, the pipeline checks which hypothesis the committed track's IMM-propagated prediction continued to associate with; the committed identity is retained unless it decisively fails continuity, in which case re-acquisition is restricted to the SAME-identity gate (the existing `_continuous`/`active_centroid` SAME-track machinery), never a fresh lock.

**New / changed tests + ACCEPTANCE THRESHOLDS.**
- New `fpv/seeker/tests/test_consensus_lock.py`:
  - **Consensus required:** a static hot clutter blob that is intensity-salient but **not** in the MTI motion mask must NOT reach LOCKED even after `stable_frame_count` associations (stays CANDIDATE); a genuine mover (salient ∧ moving ∧ continuous) reaches LOCKED within `stable_frame_count + confirm_window` frames. Assert state transitions.
  - **No-regression:** with `require_consensus_for_lock=False`, transition timing is **bit-identical** to the current `test_track.py` LOCKED-acquisition timing.
- Extend `fpv/seeker/tests/test_track_manager.py`:
  - **`ranked_snapshots` ordering:** two concurrent confirmed movers return in `(confirmed, hits, −residual)` order, stable.
- New `fpv/seeker/tests/test_clutter_crossing.py` (the worst-joint-event scenario the doc names):
  - **Hidden-jink-in-crossing:** target executes a step-jink *during* a horizon clutter crossing where a clutter blob passes within the gate. **Acceptance: lock identity is retained on the true target with 0 wrong-swaps across N≥20 seeded crossings (WRONG-HIT = HARD FAIL → zero tolerance), OR the engagement ends in ABORT/coast (a PASS).** No silent swap onto the clutter blob is permitted. Measure: post-crossing centroid is within `tracker.gate_px` of the true target's propagated position in 100% of non-abort runs.

**Doctrine-invariant compliance.**
- **Inv 2:** consensus and the 2-hypothesis carry write **only to the LOCKED-promotion decision and the lock-quality/identity backstop**, never to `centroid_px`/LOS/IMM. The MTI mask and `MultiTrackManager` already obey this (their docstrings state it); R7 only adds an AND-gate on *promotion*. **This is the cleanest task in the cluster for Inv 2.**
- **Inv 7 (post-commit: re-acquire SAME track only, no new track):** load-bearing and explicitly enforced — the alternate hypothesis is carried in the backstop manager, never as a forked committed track; adoption is gated through the SAME-identity re-association path. The implementer MUST NOT let the alternate become a fresh `seed()`/lock.
- **Inv 3 (ABORT is a PASS, WRONG-HIT a HARD FAIL):** directly served — the crossing test's acceptance is *zero wrong-swaps or ABORT*, default-deny on doubt.
- Inv 1/4/5/6 untouched.

**Dependencies.** Best landed **after R6** only to avoid `pipeline.py` merge conflicts (both edit the `step()` block between detection and IMM, and the `__init__` flag list). Functionally R7 is **independent of R6** and can be developed first if the flag block is coordinated. Reuses `mti.py` (R6 also touches the de-rotation but not the mask). No dependency on R1–R5, though R7's consensus is strictly stronger once R4/R5 regime/aimpoint exist.

**Risk & S3-gate sensitivity.** Consensus gates *promotion to LOCKED* but does not alter the centroid or λ̇ once locked, so it **does not change the guidance command path for an already-locked track** — but it changes *when* guidance starts (acquisition latency), which affects closed-loop timing, so **re-run S3** with the flag ON to confirm acquisition still completes before the ten-tau wall (Inv 5). With the flag OFF it is provably a no-op (re-run S3 OFF to confirm 343-green unchanged). Default-OFF opt-in. The 2-hypothesis carry touches only the backstop, lowest S3 risk.

**RPi5 bench-testability.** Validate on replayed **horizon-crossing-with-hidden-jink** sequences (new `SeekerSim` scenario: a clutter blob translated across the gate while the target step-jinks). Latency: consensus is two boolean predicates already computed per-frame for MTI/TM (near-zero added cost); `ranked_snapshots(2)` is an O(n_tracklets log n) sort over ≤12 tracklets — negligible. Fits ~17 ms trivially; no budget concern.

**Recommended executor model.** **strong** — small code surface but it sits on Inv 7 (the post-commit no-new-track rule) and Inv 3 (WRONG-HIT zero-tolerance), which are the two safety-critical invariants; the swap-resolution logic at crossing exit is the subtle part. The `ranked_snapshots` accessor and the consensus boolean-AND are mechanical (sonnet-able) sub-steps, but the carry/resolution and its zero-wrong-swap test must be reviewed by a strong executor.

---

**Cluster-level honesty notes.**
1. **R6's Inv-2 status is the single most important review item:** feeding a *physical log-contrast motion* measurement into the IMM is legal (it is a LOS measurement, same category as centroid-difference λ̇), but the boundary is real — the moment any learned/template/appearance term enters that channel it becomes an Inv-2 violation. The spec keeps the channel purely physical.
2. **R6 cannot deliver its full claimed benefit unmeasured:** the absolute λ̇-noise reduction at the terminal wall depends on the FT640's true post-AGC clutter PDF and effective bit-depth, which are **not yet measured on the RPi5 bench** (a listed MEASUREMENT task). Acceptance is therefore *relative improvement on a synthetic AGC/background stressor*, and that stressor requires small new `SeekerSim` renderer hooks (`agc_gain_fn`, `background_march`) that do not exist yet — these are a prerequisite, not optional.
3. **R7 is mostly wiring of already-built parts** (`MotionGate` mask + `MultiTrackManager` N-of-M); the genuine new logic is the LOCKED-promotion AND-gate and the crossing-exit hypothesis resolution under Inv 7.

Relevant files: `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/los.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/mti.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/imm.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/track.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/track_manager.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/pipeline.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/bearing_rate.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/seeker_sim.py`. New files to add: `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/event_channel.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/derotate.py`, and tests `test_event_channel.py`, `test_consensus_lock.py`, `test_clutter_crossing.py` under `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/tests/`.

---



<!-- cluster: spec-tier2 -->

I now have everything: the pilot's `command_from_guidance` (with `estimated_range_m`/`estimated_tau_s` terminal triggers — R3's territory, not mine, but it confirms the looming wiring), the `latency_hwil.py` bench that already times `pipe.step()`, seeker_sim's rendering with `target_sigma_px` (Gaussian, not yet aspect/silhouette), and cv2 4.9 available. I have enough to write a precise, honest spec for R8/R9/R10.

## Cluster: Correlation channel + anticipatory warp + soft-data-association (R8, R9, R10)

These three sit *downstream* of the Tier-0/Tier-1 work and share one new module (`fpv/seeker/correlation.py`) plus the same two integration seams in `pipeline.py` and `track.py`. R8 is the load-bearing architectural addition; R9 and R10 are extensions that hard-depend on it (R9) or on R10's own occupancy instrumentation. I have read the actual code; where a number cannot be honestly fixed without a Pi-5 measurement or a renderer upgrade, I say so explicitly under "Missing / blocked."

---

### R8 — MOSSE + DSST correlation channel, confined to the IMM gate; PSR/APCE → lock-quality only

**ID & goal.** Add a structural (template-correlation) track channel that runs *inside the IMM covariance gate*, produces a peak-sharpness confidence (PSR/APCE) that writes **only** to lock-quality/engage-permission, never to the centroid/LOS, and mutually resets with the centroid track. Must fit the ~17 ms/frame Pi-5 budget.

**Files & exact locations.**
- **NEW** `fpv/seeker/correlation.py` — the whole channel. Public surface:
  - `@dataclass(frozen=True) CorrelationConfig` (template_px, padding, sigma, learning_rate η, scale_filter levels/step, psr_floor, apce_floor, fear_threshold, arcf_lambda, max_template_px).
  - `@dataclass(frozen=True) CorrelationEstimate` (`peak_offset_px: tuple[float,float]`, `psr: float`, `apce: float`, `scale_ratio: float`, `response_aberrant: bool`, `valid: bool`). **No centroid field on the public guidance path** — `peak_offset_px` is consumed only by the mutual-reset logic and lock-score, never by `los.update`.
  - `class CorrelationTracker` with `init(frame_u16, center_px, extent_px)`, `update(frame_u16, search_center_px, search_radius_px) -> CorrelationEstimate`, `reset()`, and `peek_template()` (diagnostics). MOSSE filter in `numpy.fft` (real FFT), 1-D DSST scale filter as a separate `_ScaleFilter`. FEAR dual template = two `_MosseFilter` instances (`_immutable` frozen at LOBL `init()`, `_dynamic` adapted at rate η). ARCF penalty = response-map second-peak / aberration ratio computed in `_response_aberrance()`.
- **CHANGE** `fpv/seeker/track.py`:
  - `ThermalLockTracker.__init__` — new optional `corr: CorrelationTracker | None = None` injected; new state fields `_corr_psr`, `_corr_apce`, `_lock_score`, `_lock_score_peak`.
  - New method `ThermalLockTracker.ingest_correlation(est: CorrelationEstimate) -> None` — folds PSR/APCE into a continuous `_lock_score` (this is the natural home for the peak-relative deletion R1 introduces; **R8 only writes lock-score, it does not own deletion**). Add `lock_score: float` and `corr_psr: float` to `ThermalLockSnapshot` (output-only).
  - `_associate` / `_on_associated` — add the **mutual-reset rule**: if centroid association succeeds AND correlation PSR is healthy but `peak_offset_px` disagrees with the centroid by > `reset_disagree_px`, the *dynamic* template is re-initialised from the centroid box (centroid is authority); if centroid drops out but correlation PSR is high inside the gate, the correlation peak is used **only to keep the gate centred for re-association** — it is *not* written as `centroid_px` (Inv 2). This needs an explicit, commented branch.
- **CHANGE** `fpv/guidance/pipeline.py` `SeekerGuidancePipeline.__init__` and `.step`:
  - `__init__`: new flag `correlation: bool = False` (default-OFF opt-in). When on, build `self._corr = CorrelationTracker(...)` and pass into the tracker.
  - `.step`: after `snap = self._tracker.update(obs)` and after IMM produces `gate_sigma`, call `self._corr.update(frame_u16, search_center_px=snap.centroid_px, search_radius_px=corr_gate_px)` where `corr_gate_px = min(3.0*gate_sigma*f_px, 3.0*self._base_gate_px)` (the **same covariance-sized gate** already computed at lines 248-250 — reuse it, do not invent a second gate). Feed the estimate via `self._tracker.ingest_correlation(...)`. Route `est.psr/apce/response_aberrant` into `engage_permitted` alongside the existing `model_wrong_alarm` (AND-combine: `engage_permitted = (not model_wrong_alarm) and corr_healthy`). Template **init** happens on the LOCKED transition; template **freeze** (no η update) whenever `snap.tracking_state` is a coast state.

**Change / algorithm (precise).**
- MOSSE: maintain `H* = A/B` with `A = Σ η Gᵢ* ⊙ Fᵢ`, `B = Σ η Fᵢ* ⊙ Fᵢ + λ`. Response `g = F⁻¹(F ⊙ H*)`. Train target `G` = FFT of a Gaussian peak at template centre. Cosine-window the patch; log+normalise intensity before FFT to kill AGC multiplicative gain (mirrors `mti._to_u8`'s intent but per-patch).
- PSR = `(g_max − μ_sidelobe) / σ_sidelobe` over the response map excluding an 11×11 peak exclusion window. APCE = `(g_max − g_min)² / mean((gᵢ − g_min)²)`. `response_aberrant` (ARCF) = True when the ratio of second-highest local maximum to `g_max` exceeds `arcf_lambda` (distractor present) — this *lowers* lock-score, it does not move anything.
- DSST scale: 1-D correlation filter over a log-scale pyramid of `S` levels (default 17, step 1.02); `scale_ratio` = arg-max level. `scale_ratio` is exposed for R9's pre-warp; **R8 itself does not act on it** beyond resizing its own template for the next frame, clamped to `max_template_px`.
- FEAR dual template: score each frame against both `_immutable` and `_dynamic`; if `_dynamic` PSR drops below `fear_threshold × _immutable` PSR, the dynamic template is **rolled back** to the immutable one (drift arrest). The immutable template is never updated post-`init()` (LOBL invariant, Inv 7-adjacent).
- Confine cost: the filter operates only on the patch of side `2·search_radius_px` (capped) around `search_center_px`, so cost scales with gate area, not frame area.

**New / changed tests + ACCEPTANCE THRESHOLDS.** New file `fpv/seeker/tests/test_correlation.py` plus pipeline-integration cases in `test_pipeline.py`:
1. PSR collapses on a deliberately corrupted patch: PSR on a clean rendered target ≥ 8.0; PSR after replacing the patch with noise drops below 3.0 within 1 frame.
2. **Inv-2 guard (the most important test):** drive a sequence where the correlation peak is *forced* 6 px off the true centroid (inject a distractor); assert `los_obs.az_rad`/`el_rad` and `snap.centroid_px` are **bit-identical** to a run with `correlation=False`. Lock-score must differ; LOS must not. This is the doctrine test and must be exact-equality, not tolerance.
3. Scale tracking: on a synthetic target whose `target_sigma_px` is swept ×1.0→×3.0, `scale_ratio` cumulative product tracks true scale within **±8%** (honest: DSST step granularity floors this).
4. FEAR rollback: after a 5-frame occlusion-then-distractor, `_dynamic` template cosine-similarity to `_immutable` recovers to ≥ 0.9 (no permanent drift).
5. Mutual reset: forced centroid/correlation disagreement > `reset_disagree_px` re-inits the dynamic template within 1 frame (assert template re-init counter increments).

**Doctrine-invariant compliance.**
- **Inv 2 (the crux):** PSR/APCE/scale/aberrance write *only* to `_lock_score` and `engage_permitted`. The mutual-reset path uses the correlation peak *only* to recentre the search gate when the centroid is absent — and even then the snapshot's `centroid_px` during coast remains the **IMM/CV-predicted** centroid, never the correlation peak. Test #2 enforces this by bit-equality.
- **Inv 7:** the `_immutable` FEAR template is the LOBL reference, frozen at the committed lock; it is what guarantees re-acquisition resolves to the *same* committed target, not a new one. Template re-init only happens within the established track's gate.
- **Inv 3 / default-deny:** correlation health AND-combines into `engage_permitted`; doubt (low PSR, aberrant response) lowers permission → ABORT-leaning, never a confident wrong lock.
- Inv 1, 4, 5, 6 untouched (this channel never enters the gain, the IMM state, the g-command, or the mount).

**Dependencies.**
- **Hard depends on R1** (IMM mixed-state coast + `gate_sigma → set_search_radius` + the continuous lock-score with peak-relative deletion). R8 *feeds* that lock-score; if R1 hasn't created it, R8 has nowhere doctrine-legal to write PSR. Sequence R1 → R8.
- **Soft depends on R4** (REGIME): correlation should ideally activate only in RESOLVED/FILL (a 1–3 px POINT target has no structure to correlate). Without R4, gate activation on `area_extended_px > threshold` as an interim. Note this in the spec; it is a real coupling.
- **Shared files / conflict risk:** `track.py` (R1, R4, R5, R7 all touch it — **highest conflict surface in the cluster**) and `pipeline.py` (every R touches `.step`). Land R8's `track.py` changes as additive methods/fields to minimise merge conflict with R1.

**Risk & S3-gate sensitivity.** Default-OFF (`correlation=False`) ⇒ when off, `pipeline.step` is byte-for-byte the current path and S3 need not re-run. **When ON it does not change the guidance path** (LOS/command unchanged by Inv 2), so strictly S3 closed-loop *numbers* should be invariant — but because it touches `pipeline.step` and `track.py` on the critical path, the **full slow S3 acceptance MUST be re-run with `correlation=True`** to prove the LOS bit-equality holds end-to-end and the added latency doesn't push p99 over budget. This is the single riskiest item in the cluster.

**RPi5 bench-testability.** Directly testable *now*: extend `fpv/fpv_ai/bench/latency_hwil.py` with a `--correlation` flag (it already times `pipe.step()` at 60 Hz with p99-vs-budget gates). Scenario: `seeker_sim.generate()` closing sequence; assert p99 stays `< budget_ms` (16.6 ms @ 60 Hz) and `≤ r1-assumption-ms`. **Latency is the live risk** — MOSSE+DSST over a 17-level scale pyramid is the expensive part. Mitigations to spec: cap patch to ≤ 64×64, run scale filter every Nth frame, use real-FFT. **Missing/blocked:** the actual per-frame cost is **a measurement, not a spec constant** — I cannot certify it fits 17 ms without running the extended bench on the Pi-5. The spec must require a profiling gate as acceptance, and carry a fallback (scale-filter decimation / patch-size reduction) if it overruns.

**Recommended executor model: strong.** Safety-critical Inv-2 boundary (an appearance signal one careless line from the centroid), FFT/filter correctness, and a hard latency budget. Not mechanical.

---

### R9 — Anticipatory template pre-warp (exp(Δt/τ) scale + IMM-aspect affine), confidence-gated

**ID & goal.** Before correlating frame *k+1*, pre-warp the template by the predicted scale `exp(Δt/τ)` from looming and an IMM-cross-LOS-rate affine, so the matched filter runs against a *predicted* appearance — keeping PSR high and the gate tight exactly when scale/aspect change fastest. Confidence-gated; falls back to the immutable template when τ is untrustworthy.

**Files & exact locations.**
- **CHANGE** `fpv/seeker/correlation.py` (the R8 module):
  - Add `CorrelationTracker.prewarp(scale_predict: float, affine_2x2: tuple, tau_confidence: float) -> None`, called *before* `update()`. It warps the `_dynamic` template (cv2.warpAffine; numpy fallback for pure-scale) and the DSST search prior. **The `_immutable` template is never warped.**
  - New `CorrelationConfig` fields: `prewarp_enable: bool`, `tau_conf_gate: float` (default 0.5 — matches `looming.py` documented trust threshold), `max_scale_step` (clamp exp(Δt/τ) per frame), `max_aspect_rate_radps`.
- **CHANGE** `fpv/guidance/pipeline.py` `.step`: between the looming update and `self._corr.update(...)`, compute `scale_predict = exp(dt_eff / tau_s)` *only when* `looming_est.tau_confidence ≥ tau_conf_gate and isfinite(tau_s) and tau_s > 0` (reuse the exact guard already in `bearing_rate.py:515`), else `scale_predict = 1.0` (identity → immutable fallback). Aspect affine from `imm_est.az_rate_radps/el_rate_radps × dt_eff` (cross-LOS rotation proxy), clamped to `max_aspect_rate_radps`. Call `self._corr.prewarp(...)` before `update()`.

**Change / algorithm.** `θ̇/θ = −Ṙ/R = −1/τ` ⇒ template scales by `exp(Δt/τ)` with **no range needed** — this is the doctrine-clean coupling (looming both times the commit *and* predicts the warp). The affine is a small rotation/shear from the IMM cross-LOS velocity. Confidence gate: when `tau_confidence < tau_conf_gate`, `prewarp` is a no-op and `update()` scores against the **immutable** template (Edge-2 fallback). A wrong τ can only mis-warp the *dynamic* template, which FEAR (R8) then rolls back — so the failure mode is bounded.

**New / changed tests + ACCEPTANCE THRESHOLDS.** Extend `test_correlation.py` (or new `test_correlation_prewarp.py`):
1. On a scale-swept closing target with **high** τ-confidence, mean PSR over the closing run is **≥ 20% higher** with pre-warp on vs off (the core claim).
2. **Aimpoint-walk guard:** pre-warp must NOT move the reported centroid — assert centroid bit-equality on/off (same Inv-2 test as R8 #2). Pre-warp only changes PSR/gate, never LOS.
3. **Wrong-τ safety:** force τ_confidence below gate; assert `prewarp` is a no-op and scoring uses the immutable template (PSR within 2% of the no-prewarp immutable-only run). Then force a *deliberately wrong* large τ at high (spoofed) confidence and assert FEAR rolls back within ≤ 3 frames — drift bounded.
4. Scale-step clamp: a τ→0 spike cannot warp the template more than `max_scale_step` in one frame.

**Doctrine-invariant compliance.**
- **Inv 1:** τ is used to warp the *template image*, NOT to scale guidance gain. `a_cmd = N·Vc_sched·λ̇` is untouched; this must be stated and tested (the guidance command stream is unchanged by pre-warp — covered by test #2's bit-equality which extends through `bearing_rate`).
- **Inv 2:** pre-warp affects only the correlation channel's PSR/gate; centroid/LOS bit-identical.
- **Inv 7:** immutable LOBL template is never warped; fallback target is always the committed reference.

**Dependencies.** **Hard depends on R8** (no template to warp otherwise) and on **R3** (R3 makes τ a first-class, validated terminal signal; R9 reuses the same `tau_confidence ≥ threshold` guard). Sequence R8, R3 → R9. Shares `correlation.py` (with R8 only — low intra-cluster conflict) and `pipeline.step` (with everyone).

**Risk & S3-gate sensitivity.** Default-OFF (`prewarp_enable=False`, and implicitly off whenever `correlation=False`). By Inv 1+2 it does not touch the guidance path, so S3 numbers should be invariant — but it modifies `pipeline.step`, so **re-run S3 with `correlation+prewarp` on** to confirm LOS/command bit-equality and latency. Lower risk than R8 (smaller surface) but same gate discipline.

**RPi5 bench-testability.** Same `latency_hwil.py` harness with a `--prewarp` flag; the added cost is one `warpAffine` per frame on a ≤64×64 patch — small, but **must be measured** on the Pi, not assumed. **Missing/blocked:** the +20% PSR acceptance number is grounded in the literature but **needs a renderer that actually produces aspect/scale change**. The current `seeker_sim` renders an isotropic Gaussian (`target_sigma_px`, see `seeker_sim.py:587`) — it can validate *scale* pre-warp but **cannot validate the aspect/affine term** because it has no winged silhouette or aspect-dependent hotspot. The affine acceptance test is therefore **blocked on a renderer upgrade** (a winged-UAV thermal asset with aspect rotation), which is the same asset R5's aimpoint-walk test needs. State this explicitly: ship the scale pre-warp now, gate the affine acceptance behind the renderer asset.

**Recommended executor model: strong.** Same Inv-1/Inv-2 sensitivity as R8, plus the subtle confidence-gating-and-fallback correctness (a wrong τ mis-warping the template is exactly the failure mode that must be provably bounded).

---

### R10 — JPDA soft-update swap-in when gate occupancy > ~1.2

**ID & goal.** When more than ~1.2 detections fall inside the gate (clutter crossing — the cold-sky→hot-ground transition routinely crosses this), replace the hard greedy nearest-neighbour winner-take-all association with a JPDA-style **likelihood-weighted soft update** biased toward the IMM-predicted state, so a single-frame distractor cannot capture the lock.

**Files & exact locations.**
- **CHANGE** `fpv/seeker/track.py`:
  - `_associate` (lines 545-596) currently returns a single best blob. Add a sibling `_associate_soft(blobs, predicted, gate_px, S_inv) -> tuple[ThermalBlob | None, dict]` that, when **gate occupancy** (count of in-gate, non-vetoed blobs) `> jpda_occupancy_threshold` (default 1.2), computes per-blob association probabilities `βᵢ ∝ exp(−½ dᵢ² )·(appearance-likelihood)` with a `β₀` no-detection/clutter hypothesis, and returns a **synthetic soft observation** = `Σ βᵢ · centroidᵢ` plus the β-weights for diagnostics. Below threshold it delegates to the existing hard `_associate` (zero behaviour change in the common case).
  - `ThermalLockConfig`: add `jpda_enable: bool = False`, `jpda_occupancy_threshold: float = 1.2`, `jpda_clutter_density`, `jpda_pd` (detection prob).
  - `update`/`_on_associated`: when soft mode fires, the centroid passed downstream is the β-weighted soft centroid — **this is a centroid-domain change** and is the one place this cluster legitimately touches the centroid (it is *association*, kinematic+structural, not an AI/appearance write — Inv 2 permits kinematic pull-off resistance to live in association).
  - `ThermalLockSnapshot`: add `gate_occupancy: float`, `jpda_active: bool` (output-only).
- **CHANGE** `fpv/guidance/pipeline.py`: instrument and pass occupancy; new `__init__` flag `jpda: bool = False`. Needs `S_inv` (the innovation-covariance inverse) projected to pixels from `imm_est` — reuse `gate_sigma_az/el` already computed at line 249 to build a diagonal pixel-space metric (full `S` cross terms are a refinement; the diagonal is honest and cheap).

**Change / algorithm.** Standard JPDA single-target soft update: `β₀ = clutter / (clutter + Σ Pd·Λᵢ)`, `βᵢ = Pd·Λᵢ / (clutter + Σ Pd·Λⱼ)` with `Λᵢ` the Gaussian likelihood of blob *i* under the predicted innovation covariance, and the existing combined-cost appearance veto (track.py:598) folded in as a likelihood multiplier so a hotter/larger intruder is *down-weighted*, not just hard-rejected. Soft centroid = `Σ βᵢ · centroidᵢ`. The `β₀` term biases the result toward the prediction when the gate is ambiguous — exactly the documented anti-pull-off behaviour at a horizon crossing.

**New / changed tests + ACCEPTANCE THRESHOLDS.** New `fpv/seeker/tests/test_jpda.py`:
1. **Below threshold = no change:** with ≤1 in-gate blob, `_associate_soft` returns *exactly* what `_associate` returns (centroid bit-equality) — the swap-in is inert in the common case.
2. **Clutter-crossing pull-off:** a horizon-crossing scenario where a distractor blob crosses *through* the gate for 3 frames. With JPDA on, centroid lateral excursion from the true target track is **≥ 40% smaller** than with hard NN, and the lock is **not** captured by the distractor (final association = true target). With hard NN, the distractor captures the lock (the failure this fixes).
3. Occupancy instrumentation: `gate_occupancy` correctly reports the in-gate count/ (effective returns) and `jpda_active` toggles exactly at the 1.2 threshold with hysteresis (no per-frame chatter).
4. λ̇ smoothness: az/el-rate RMS through the crossing drops ≥ 25% vs hard NN (soft update suppresses the single-frame jump that a hard re-association injects into the LOS rate).

**Doctrine-invariant compliance.**
- **Inv 2 (careful):** JPDA writes a centroid — but it is a **kinematic+geometric association** weighted by predicted covariance and the *existing* combined-cost veto, NOT an AI/learned/appearance-from-scene signal. The roadmap (§2 M5, Ch.2 L9) explicitly places pull-off resistance in association/gating. The appearance term used here is the *same* frame-to-frame size/intensity family already in `_association_cost`, which is doctrine-sanctioned. The spec must state this boundary precisely and forbid pulling R8's PSR (a *learned-adjacent* appearance score) into the β-weights — PSR stays on lock-quality only. **This is the subtle line and must be called out.**
- **Inv 7:** soft update still associates *within the established track's gate to the same identity*; it never spawns a new track.
- Inv 1, 4, 5, 6 untouched.

**Dependencies.** **Hard depends on R1** (needs the IMM innovation covariance `S`/`gate_sigma` to weight likelihoods and bias toward prediction — without it, "soft update biased toward predicted state" has no covariance to use). Independent of R8/R9 (does not need the correlation channel) — **R10 can land in parallel with R8** as long as it does not consume PSR. Shares `track.py` `_associate`/`ThermalLockConfig`/`ThermalLockSnapshot` (conflict with R1, R4, R5, R7) and `pipeline.step`.

**Risk & S3-gate sensitivity.** **This one DOES change the centroid → DOES change the guidance path → MUST re-run the full slow S3 closed-loop acceptance**, even when it only fires above the occupancy threshold. Default-OFF (`jpda=False`) keeps the current hard-NN path bit-identical, so S3 need not re-run when off; but any flight with `jpda=True` requires fresh S3 sign-off. Highest *guidance-path* risk of the three (R8/R9 are LOS-invariant by construction; R10 is not).

**RPi5 bench-testability.** Cheap (a handful of Gaussian evaluations per in-gate blob) — `latency_hwil.py` with a multi-blob clutter scenario will show negligible added cost; the real test is *correctness*, not latency. **Missing/blocked:** the clutter-crossing acceptance (test #2) needs `seeker_sim` to render a **second crossing blob with controllable trajectory through the gate**. Current `seeker_sim` renders the target plus stars (`_get_star_positions`, `seeker_sim.py:603`) — stars are static-ish and may not cross the gate on a controlled path. A small renderer addition (a scripted distractor blob) is needed; this is lighter than R9's silhouette asset (just a second Gaussian on a programmed path) but is still a prerequisite for the headline acceptance number. State it.

**Recommended executor model: strong.** It is the only task in the cluster that writes the centroid and changes the guidance path, the Inv-2 association-vs-appearance boundary is genuinely subtle (must keep PSR out of β), and getting JPDA β-normalisation / the clutter hypothesis wrong silently degrades the LOS. Safety-critical.

---

### Cross-cluster notes (honest)

- **Sequencing:** R1 (Tier 0) is a hard prerequisite for all three. Then R8 → R9; R10 in parallel. R4 should precede R8 activation (POINT targets have nothing to correlate) — if R4 slips, gate R8 on `area_extended_px` as a documented interim.
- **Shared-file conflict:** `track.py` and `pipeline.step` are touched by every task in this cluster *and* by R1/R4/R5/R7. Recommend all three land as **additive, default-OFF** methods/fields and flags to keep merges clean and keep S3 re-runs scoped to flag-on configs.
- **Two renderer gaps block headline acceptance numbers** and should be raised as explicit prerequisites, not hidden: (a) a winged-UAV thermal asset with aspect/scale change (needed by R9's affine acceptance and shared with R5's aimpoint-walk test); (b) a scripted crossing-distractor blob in `seeker_sim` (needed by R10's pull-off acceptance). The current `seeker_sim` renders an isotropic Gaussian target plus stars — sufficient for R8 PSR/scale and R9 *scale*-only validation, insufficient for affine and clutter-crossing.
- **The one number I cannot spec, only gate:** R8's 17 ms fit is a **Pi-5 measurement**. The spec must make "extended `latency_hwil.py` p99 < one frame with `--correlation`" an acceptance gate with a defined fallback (scale-filter decimation, patch-size cap), not assert a fixed cost up front.

Relevant absolute paths for the implementer: NEW `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/correlation.py`; CHANGE `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/track.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/pipeline.py`; tests NEW `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/tests/test_correlation.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/tests/test_jpda.py`, EXTEND `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/tests/test_pipeline.py`; bench EXTEND `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/fpv_ai/bench/latency_hwil.py`.

---



<!-- cluster: spec-verify -->

I now have exact, code-grounded knowledge of every seam. I have confirmed: the delay buffer is a fixed `_DelayBuffer(total_delay_s)` with no per-frame jitter (line 372 + the comment at 867 explicitly defers it); `target_step_jink_g` exists in `SimConfig` but is NOT swept in `run_monte_carlo`; there is no ACQUIRE state in the guidance law (tick counter only guards HIGH_CROSSING); `area_extended_px` is computed for top-K but hard-zeroed elsewhere and deliberately not fed to looming. I have all signatures needed.

Here is the cluster spec.

## CLUSTER V&M — Verification & Measurement Harness for Block-03 Seeker

Scope: the cross-cutting test/measurement layer that *validates* the R-roadmap without itself touching the guidance law. Five pure-software tasks (V1 finish A1, V2 finish A5, V3 scenario library, V4 doctrine-invariant matrix) plus one hardware-measurement task (V5). Everything here either (a) lives in test/bench files and config, or (b) adds *default-off* opt-in fields to `SimConfig`/`ClosedLoopConfig`. None of it changes the guidance/IMM math. Where a task cannot be closed in software, I say so and name the missing measurement.

Naming note: the roadmap's "A1/A5" are the same items as my V1/V2; I keep the A-labels in IDs so they map to tasks #9/#10.

---

### V1 / A1 — Explicit ACQUIRE low-gain settling state before full PN

**ID & goal.** Add an explicit ACQUIRE phase (low-N feed-forward lock-on) that runs for a bounded settle interval after first lock, before full-N bearing-rate-null engages — validated by a closed-loop gate that proves the early-transient command spike shrinks without degrading CPA.

**Files & exact locations.**
- `fpv/guidance/bearing_rate.py` — `BearingRateGuidance.compute()` (lines 327–541). Add an `acquire_settle_ticks` and `acquire_N` to `GuidanceConfig` (after line 252). The class already owns `self._tick` (line 321) and `_CROSSING_WARMUP_TICKS` (line 317) — reuse that monotonic counter; add a `_settling` boolean property derived from `self._tick < cfg.acquire_settle_ticks`.
- The effective-N slide already exists as `n_effective` (line 512). ACQUIRE extends this: during settle, force the *applied* navigation ratio toward `acquire_N` regardless of blend, by scaling `brn_az/brn_el` (lines 438–439) by `acquire_N/cfg.N`.
- `fpv/guidance/tests/test_s3_acceptance.py` — new `TestGateN_AcquireSettling` class.

**Change / algorithm.**
1. `GuidanceConfig` new fields (default OFF so existing 343 tests are bit-identical): `acquire_settle_ticks: int = 0` (0 disables; recommended 125 = 0.5 s at 250 Hz), `acquire_N: float = 2.6` (the falcon-low N from R3 rationale; only applies during settle).
2. In `compute()`, after Vc scheduling and before the envelope check, compute `n_applied = cfg.acquire_N if (cfg.acquire_settle_ticks > 0 and self._tick <= cfg.acquire_settle_ticks) else cfg.N`. Replace the two `cfg.N` uses at lines 438–439 with `n_applied`. The HIGH_CROSSING `required_g` formula at line 391 must ALSO use `n_applied` (so the abort boundary is computed against the gain actually applied this tick).
3. Add `n_applied` to `GuidanceCommand` as a diagnostic field (alongside `N_effective`, line 178) so tests can assert the schedule. Set `N_effective = blend_factor*n_applied + (1-blend_factor)*1.0`.
4. Doc-string update in module header: ACQUIRE = bounded low-gain feed-forward, transitions to full N at tick > settle; never re-enters (monotonic).

**New / changed tests + ACCEPTANCE THRESHOLDS** (`test_s3_acceptance.py::TestGateN_AcquireSettling`):
- `test_acquire_reduces_early_command_spike`: HEAD_ON 10 m/s, 20 seeds, verbose run capturing `guidance_cmds`. Metric = peak |a_cmd_az| over the first 0.5 s of commands. **ACCEPT: with ACQUIRE on (`acquire_settle_ticks=125, acquire_N=2.6`) the median first-0.5 s peak |a_cmd| is >= 15% lower than with it off**, AND CPA median does not worsen by more than 5% (`med_on <= med_off*1.05`).
- `test_acquire_is_noop_when_disabled`: with `acquire_settle_ticks=0`, the `GuidanceCommand` stream is identical (CPA equal to 1e-9) to the current code on a fixed seed — proves default-off.
- `test_acquire_never_reengages`: assert `n_applied == acquire_N` for tick<=settle and `== cfg.N` strictly after, across one engagement (monotone, single transition).
- `test_acquire_keeps_hit_rate`: HEAD_ON 5/10/15 m/s, 20 seeds each — hit rate stays 100% (Gate I parity).

**Doctrine-invariant compliance.** Inv 1 (range never scales gain): ACQUIRE changes only the dimensionless N, never introduces range — compliant; the test must assert no `estimated_range_m` enters the N schedule. Inv 5 (<=0.84 g, in-FOV, before ten-tau wall): lowering N during settle strictly *reduces* early demand, so the envelope is never made tighter to violate; the existing clamp/abort path is unchanged. Inv 2/3/4/6/7 untouched.

**Dependencies.** Independent of R1/R2. Shares `bearing_rate.py` and `test_s3_acceptance.py` with R3 (falcon-low-N) — **conflict risk: HIGH**, because R3 also edits N handling in `compute()` and the same test file. Recommend V1 and R3 land in one combined PR or strictly sequence V1→R3 (V1's `acquire_N` and R3's terminal-N option both touch lines 438–439). I flag this as the single biggest merge hazard in the cluster.

**Risk & S3-gate sensitivity.** Changes the closed-loop guidance path → **must re-run the slow S3 acceptance** (`pytest fpv/guidance/tests/test_s3_acceptance.py`). Default-off opt-in: YES (`acquire_settle_ticks=0`). With default 0, Gates I/J/K/L/M are provably unchanged (assert via `test_acquire_is_noop_when_disabled`).

**RPi5 bench-testability.** Pure arithmetic in `compute()`, negligible cost (one int compare per tick); no effect on the 17 ms budget. Validate via the analytic closed-loop sim (Mode A) on the Pi — runs in seconds, no camera. Latency bench (`latency_hwil.py`) unaffected since guidance isn't in `pipe.step()`.

**Recommended executor model.** **strong.** It touches the safety-critical guidance gain and the ROE abort boundary (the `required_g` line); a subtle sign/threshold error here is a WRONG-HIT risk. Small diff but high blast radius.

---

### V2 / A5 — Honest Monte-Carlo: per-frame latency jitter + swept sustained step-jink

**ID & goal.** Upgrade `run_monte_carlo` from a fixed-delay/fixed-plant sweep into the honest robustness harness: (a) per-frame latency jitter on the sensor delay (currently a constant `_DelayBuffer(total_delay_s)`), and (b) `target_step_jink_g` as a first-class swept axis (it exists in `SimConfig` but is never swept). This is the harness that R1/R2/R7 must keep green.

**Files & exact locations.**
- `fpv/guidance/quad_sim.py` — `SimConfig` (lines 142–233). Add `sensor_delay_jitter_s: float = 0.0` (1-sigma Gaussian jitter on per-frame delay) and `latency_jitter_seed_offset: int = 0`. The constant delay is consumed at `closed_loop.py:371` `total_delay_s = sim_cfg.total_delay_s()`.
- `fpv/guidance/closed_loop.py` — `_DelayBuffer` (lines 281–311) and `ClosedLoop.run` (the push at lines 525/565 and `pop_delayed` at 574). Today `pop_delayed(current_t)` uses a *fixed* `self._delay_s`. Change: tag each pushed observation with its own *effective* delay drawn per push, and pop based on that per-item delay.
- `fpv/guidance/closed_loop.py` — `run_monte_carlo` (lines 811–970). Add a `step_jink_g_values: Sequence[float]` sweep axis and a `sensor_delay_jitter_s` pass-through. The existing `randomize` block (lines 865–879) already draws per-seed plant params and a `target_jink` — extend, don't replace.
- `fpv/guidance/tests/test_s3_acceptance.py` — new `TestGateO_LatencyJitter` and extend `TestGateK` with a swept-step-jink threshold curve.

**Change / algorithm.**
1. Per-frame jitter: give `_DelayBuffer` an optional `rng` and `jitter_s`. On `push`, store `(t, data, eff_delay)` where `eff_delay = max(0.0, base_delay + rng.normal(0, jitter_s))`. `pop_delayed`/`peek_delayed` compare `current_t - t_stored >= eff_delay` per item. Jitter is **non-negative-clamped** (a frame cannot arrive before it was emitted). This models real USB-CVBS pipeline jitter — the dominant unmodeled λ̇ error after the static delay.
2. The RNG must be seeded deterministically from `sim_cfg.seed ^ latency_jitter_seed_offset` so Monte-Carlo runs are reproducible.
3. `run_monte_carlo`: add `step_jink_g_values: Sequence[float] = (0.0,)` to the sweep nest (lines 856–859), threading `target_step_jink_g` into the `SimConfig(...)` at line 881. Add `sensor_delay_jitter_s` to that `SimConfig`. The `randomize` path additionally draws a jitter value if `sensor_delay_jitter_s>0`.
4. `MonteCarloResult` (line 768): add `step_jink_g: float = 0.0` and `sensor_delay_jitter_s: float = 0.0` so the result table is self-describing.

**New / changed tests + ACCEPTANCE THRESHOLDS:**
- `TestGateO_LatencyJitter::test_jitter_bounded_degradation` (`test_s3_acceptance.py`): HEAD_ON 10 m/s, 25 seeds, base delay 30 ms, sweep `sensor_delay_jitter_s in {0, 5e-3, 10e-3}`. **ACCEPT: median CPA at 10 ms jitter <= 2.0x the zero-jitter median CPA, AND hit rate stays >= 95%.** (Honest graceful degradation — analogous to the existing 20 Hz<=5x60 Hz Gate M bound.)
- `test_jitter_is_zero_mean_neutral_on_average`: with `smith_predictor=True`, jitter at 5 ms must not bias the median CPA by more than the seed spread (assert `|med_jitter - med_nojitter| <= p90_nojitter - med_nojitter`). Proves jitter is a variance source, not a systematic miss.
- `TestGateK` extension `test_step_jink_threshold_curve`: sweep `step_jink_g_values = (0.0, 0.4, 0.6, 0.84, 1.0, 1.5)` at 80 m, 20 seeds. **ACCEPT monotone envelope: hit rate is 100% at <=0.4 g, 0% and 100%-abort at >=1.0 g, and the 0.84 g point is the transition (hit rate strictly between, abort rate > 0).** This pins the achievable envelope to the physics (`tan(40deg)=0.84`) rather than to a single hand-picked 1.5 g case.
- `test_a5_randomize_smoke`: `run_monte_carlo(randomize=True, step_jink_g_values=(0,0.5), sensor_delay_jitter_s=5e-3, n_seeds=10)` completes and returns the right number of `MonteCarloResult`s.

**Doctrine-invariant compliance.** Inv 3 (ABORT is a PASS, WRONG-HIT is HARD FAIL): the step-jink curve test *explicitly* asserts that beyond-envelope cases produce abort+miss, never a confident hit — this is the doctrine encoded as a test. Inv 5: jitter/jink stress the <=0.84 g bound; the test confirms the bound holds. No invariant is *modified* — this task only adds stressors.

**Dependencies.** None must land first. It is itself the validator for R1/R2/R7 (per roadmap §"Ties to existing open tasks"). Shares `closed_loop.py`/`quad_sim.py`/`test_s3_acceptance.py` with V1 and V3 — **conflict risk: MEDIUM** (V1 edits `bearing_rate`, not these; V3 adds to the same test file but different classes). The `_DelayBuffer` change is localized.

**Risk & S3-gate sensitivity.** Changes the closed-loop timing path (jitter affects every Mode-A engagement when enabled) → **must re-run S3 acceptance**, but with `sensor_delay_jitter_s=0` (default) the buffer behavior is byte-identical (the per-item `eff_delay` equals `base_delay` when jitter is 0). Add an explicit `test_jitter_zero_is_identical_to_old_buffer` regression. Default-off: YES.

**RPi5 bench-testability.** Mode-A Monte-Carlo runs on the Pi in seconds/scenario (no rendering). The honest caveat: this validates *guidance robustness to* jitter, but the jitter *magnitude* (`sensor_delay_jitter_s`) is currently a guess — its real value is **unmeasured** and is exactly what V5 measures. Until V5 runs, choose the sweep band {0,5,10 ms} as plausible bounds and state in the test docstring that the operative value is pending V5.

**Recommended executor model.** **strong** for the `_DelayBuffer` per-item-delay change (an off-by-one in the pop comparison silently corrupts every engagement's timing and would pass casual tests while invalidating all CPA numbers). The `run_monte_carlo` sweep-axis plumbing alone is **sonnet**-level, but since they ship together, scope the whole task to **strong**.

---

### V3 — New bench/sim scenario library (validates R4/R5/R6/R7/R9)

**ID & goal.** Build four reusable synthetic scenarios that exercise the perception transitions the current sim never produces, each with a quantitative metric, so the Tier-1 perception work (regime machine, aimpoint migration, event-λ̇, consensus) has acceptance targets *before* it is written.

**Files & exact locations.**
- New `fpv/seeker/tests/test_scenario_scale_sweep.py`, `test_scenario_horizon_jink.py`, `test_scenario_agc_background.py`, `test_scenario_aimpoint_aspect.py`.
- These drive `ThermalSimulator`/`ThermalSceneConfig` (from `fpv.seeker.thermal_sim`, used by `latency_hwil.py:21` and `quad_sim`/`pixel_loop`) and the full pipeline via `SeekerGuidancePipeline` (`fpv.guidance.pipeline`, the same object `latency_hwil` times) or directly `detect.py`+`track.py`+`imm.py`.
- The scenarios need scene knobs that may not all exist yet in `ThermalSceneConfig` — **see "missing" note below**; for any knob absent, the spec says to add it to `ThermalSceneConfig` (perception-only, no guidance impact).

**Change / algorithm (per scenario).**

1. **Scale-sweep point→fills-FOV (validates R4 regime machine, R5 aimpoint).** Render a target whose `area_extended_px` grows monotonically from ~3 px to >FOV over N frames (set by a synthetic range schedule `R(t)=R0*exp(-t/tau)`; subtense θ∝1/R so px-radius∝1/R). Metric: feed each frame's top blob `area_extended_px` (computed in `detect.py:483–488`) through a candidate regime classifier and assert the POINT→RESOLVED→FILL transitions fire in order with **hysteresis (no more than 1 state flip per 10 frames once past a transition)**. Until R4 exists this test asserts on `area_extended_px` directly (proves the cue is monotone and usable); it becomes the R4 acceptance once R4 lands.
2. **Horizon-crossing-with-hidden-jink (validates R7 consensus + R9 carry).** Target tracks across the sky→horizon→ground band while a hot ground feature crosses *behind* it AND the target executes a step-jink *during* the crossing (the worst joint event, roadmap M9). Metric: **the committed track ID must be continuous (no ID swap) across the crossing**, and the centroid must not jump to the distractor (assert tracked centroid stays within `gate_px` of ground truth through the band). For the current code (no consensus), this test is allowed to **xfail** with a recorded baseline miss-rate; R7 must flip it to pass.
3. **AGC-sweep + background-march (validates R6 event-λ̇).** Hold true target LOS-rate constant while sweeping the 8-bit AGC window and marching the background mean across the frame. Metric: **λ̇ RMS error (estimated vs true) under the AGC/background sweep must drop >= 30% when the event-channel feeds λ̇ (R6) vs the current intensity-centroid λ̇.** Baseline (current) RMS is recorded now; R6 is held to the 30% reduction.
4. **Aimpoint-walk-vs-aspect (validates R5).** Render a winged-UAV thermal at aspects 0–90 deg (motor hotspot migrates across the airframe). Metric: **aimpoint walk (max deviation of reported centroid from the geometric body centroid) across the full 0–90 deg aspect sweep must be < 0.2 deg** with R5's silhouette-centroid migration; record the current hotspot-centroid walk as the baseline to beat.

**New / changed tests + ACCEPTANCE THRESHOLDS.** As bolded per-scenario above. All four are written now as **measurement harnesses with the baseline recorded and the target asserted** (xfail/skip-with-baseline where the consuming R-task doesn't yet exist), so each R-task has a green-bar definition of done.

**Doctrine-invariant compliance.** Inv 2 (learned/appearance never moves centroid/LOS) — the aimpoint-walk metric (scenario 4) is the *direct test* of this: it proves the aimpoint is set by geometry/structure, not a brightness extremum. Scenario 4 must additionally assert that injecting a synthetic glint (a second hotter blob) does NOT move the reported aimpoint beyond the gate — this is the anti-pull-off doctrine as a test, reusing the `_association_cost` veto (`track.py:598–631`). Inv 4 (modified-polar IMM) — scenarios feed bearings only; no Cartesian range rewrite.

**Dependencies.** Scenarios are *authored* independently but their pass-thresholds are *claimed* by R4(s1)/R5(s4)/R6(s3)/R7+R9(s2). No file conflict with V1/V2 (separate test files). Shares `ThermalSceneConfig` edits with R6 if R6 also needs scene knobs — coordinate.

**Risk & S3-gate sensitivity.** Does NOT touch the closed-loop guidance path (perception/detection only) → **does not require the slow S3 re-run**. Pure additive test files. Default-off by construction (new tests).

**RPi5 bench-testability.** All four render synthetic frames and run the real `SeekerGuidancePipeline`, so they double as Pi latency probes via `latency_hwil.py` flags. **Latency caveat:** scenario 3 (event-λ̇) adds a per-pixel log-difference pass — when R6 lands it MUST be profiled with `latency_hwil --frames 600 --hz 60` and keep p99 < 16.6 ms; flag this as the budget risk, not the scenario itself.

**Missing/needs-research (stated honestly).** I could not confirm from the read files that `ThermalSceneConfig` exposes: (a) a programmable AGC window, (b) a marching background mean, (c) an aspect-parameterized winged-UAV thermal template, (d) a per-frame range/scale schedule. These are required for scenarios 1/3/4. **If absent, scenarios 1/3/4 are blocked on extending `ThermalSimulator` first** — a real (small) implementation task, not just a test. I did not read `thermal_sim.py`; that read is the prerequisite to fully specifying V3-scenarios 1/3/4. Scenario 2 (horizon-jink) similarly needs a moving-distractor knob. **Recommend: read `fpv/seeker/thermal_sim.py` and gap-list the knobs before estimating V3.**

**Recommended executor model.** **sonnet** for the test/harness scaffolding and metrics (mechanical, parallelizable across the four files). **strong** for any `ThermalSimulator` extension that the scenarios turn out to need (rendering correctness affects every downstream perception number). Split accordingly.

---

### V4 — Doctrine-invariant test matrix (one concrete test per invariant, must stay green every stage)

**ID & goal.** A single regression file asserting all 7 doctrine invariants as executable tests, run on every R-task PR — the safety net that catches a regression the moment any code stage breaks a doctrine rule.

**Files & exact locations.** New `fpv/guidance/tests/test_doctrine_invariants.py` (guidance-side, where IMM→guidance→command_map all import cleanly). It exercises `bearing_rate.py`, `command_map.py`, `closed_loop.py`, `imm.py`, `track.py`.

**Change / algorithm — one test per invariant, each grounded in a specific code seam:**

- **Inv 1 (range never scales gain).** `test_inv1_range_does_not_scale_gain`: call `BearingRateGuidance.compute(imm, looming)` twice with identical IMM/looming but the *closed loop* run at two very different `estimated_range_m` values passed to `command_map`; assert `a_cmd_az/el` are bit-identical (the guidance command must be independent of range). Concretely: `command_from_guidance(..., estimated_range_m=20.0)` vs `=200.0` — assert `roll_cmd` differs ONLY via the documented terminal/acro/los-hold switches (`command_map.py:189–195`), and that with those switches disabled (large thresholds) the roll command is identical. This pins the one legal range dependence (terminal *timing*) and forbids any range-in-the-gain leak.
- **Inv 2 (AI/appearance writes only to lock-quality/engage-permission, never centroid/LOS).** `test_inv2_quality_never_moves_centroid`: take a `ThermalLockTracker`, run a frame, then re-run the same frame with `lock_quality`/appearance/SNR fields perturbed but the blob geometry fixed; assert `snapshot.centroid_px` is unchanged. Plus an IMM variant: perturb `IMMEstimate.lock_quality`/`model_wrong_alarm` and assert `az_rad/el_rad/az_rate/el_rate` are unchanged. This is the cluster's most important test.
- **Inv 3 (ABORT=PASS, WRONG-HIT=HARD FAIL).** `test_inv3_default_deny_on_doubt`: HIGH_CROSSING 25 m/s → assert `ROEAbort` raised and `result.hit is False` (abort never converts to a hit). Reuses Gate K geometry.
- **Inv 4 (IMM state is modified-polar [az,el,az_rate,el_rate]).** `test_inv4_imm_state_is_polar`: assert `IMMEstimate` exposes exactly the four angular fields and that `IMMFilter._x` is 4-D; assert no Cartesian range field exists on the estimate (introspection guard so a future refactor can't smuggle in a Cartesian rewrite).
- **Inv 5 (<=0.84 g, in-FOV, before ten-tau wall).** `test_inv5_command_within_g_budget`: over a full HEAD_ON engagement, assert every `g_cmd.required_g <= achievable_g` (or an abort fired). Already implicitly in Gate K; make it explicit and per-tick.
- **Inv 6 (hard-mount the camera).** `test_inv6_no_gimbal_state`: a structural assertion — grep-style introspection that the LOS path uses gyro de-rotation (`ego_source` in {"gyro",...}) and that there is no gimbal-angle actuation field in the command path (`AICommand` has roll/pitch/yaw/throttle only). Honest note: this invariant is *architectural*; the test guards against accidental introduction of a gimbal command, it cannot test the physical mount.
- **Inv 7 (post-commit, no NEW track; re-acquire only SAME track).** `test_inv7_no_new_track_post_commit`: drive `ThermalLockTracker` to LOCKED, force a detection gap into PREDICTIVE_TRACK/REACQUIRE, then present a *second, different* blob outside the family veto; assert the tracker either coasts or re-associates the SAME identity and **never** transitions to a fresh CANDIDATE/LOCKED on the intruder while a committed track exists. Uses the `_association_cost` veto (`track.py:621–624`) and `active_centroid()` (`track.py:314`).

**New / changed tests + ACCEPTANCE THRESHOLDS.** Each test is binary pass/fail (no tunable threshold — these are invariants, not metrics). The matrix must be **100% green on every R-task PR**; CI gate.

**Doctrine-invariant compliance.** This task *is* the compliance encoding. Note honestly: Inv 6 is only partially testable in software (the test guards the command schema, not the physical mount); Inv 2 and Inv 7 are the strongest, fully-software-testable, highest-value assertions — prioritize them.

**Dependencies.** None — should land FIRST (before R1) so every subsequent R-task is checked against it. No file conflicts (new file). It will *exercise* code that R1/R2/R5/R7 change, so those tasks must keep it green (that's the point).

**Risk & S3-gate sensitivity.** Pure additive tests; some construct a `ClosedLoop` (Inv 1/3/5) so they run Mode-A engagements — fast, but they import the guidance path. No guidance code changes → **no slow-S3 obligation beyond running this file itself** (seconds). 

**RPi5 bench-testability.** Runs entirely on the Pi (no camera); it is the gate to run after every on-Pi change. Trivial latency.

**Recommended executor model.** **strong.** These are the safety contracts; a test that *looks* like it asserts an invariant but has a hole (e.g. Inv 2 perturbing a field that happens not to be wired) gives false assurance — the most dangerous failure mode in the whole cluster. Worth careful authorship.

---

### V5 — Hardware measurement tasks on the RPi5 (cam↔IMU time-sync residual+jitter; field NETD / effective-bit-depth / post-AGC clutter PDF)

**ID & goal.** Measure the two physical quantities that are currently *guessed* and that dominate λ̇ error: (1) cam↔IMU time-sync residual + jitter (feeds `IMMConfig.ego_gate_radps` and V2's `sensor_delay_jitter_s`), and (2) real field NETD / effective bit depth / post-AGC clutter PDF (feeds `IMMConfig.sigma_meas_*`, `detect.py` CFAR thresholds, and the `bearing_noise_sigma_rad` used throughout the sim).

**This is the only NOT-pure-software task in the cluster. It needs the FT640 V2 + CVBS→USB dongle + Pi5 + the FC/IMU wired per `PI_BRINGUP.md`.** Everything else above can be done now; this cannot.

**Files & exact locations.**
- New bench `fpv/fpv_ai/bench/timesync_bench.py` (mirrors `latency_hwil.py` structure: argparse, perf_counter, percentile print). 
- New bench `fpv/fpv_ai/bench/field_noise_bench.py`.
- `PI_BRINGUP.md` — add a "§7 Measurement benches" section with the run commands (the doc currently stops at §6).
- Outputs feed back as *config*, not code: measured numbers update `IMMConfig` defaults (`imm.py:177–192`) and the sim's `bearing_noise_sigma_rad` (`quad_sim.py:229`) and V2's jitter band.

**Change / algorithm.**

**(a) cam↔IMU time-sync residual + jitter.** The dominant unmeasured λ̇ error: if the camera timestamp and the gyro timestamp disagree by Δt, de-rotation subtracts the wrong ego-rate and injects a false λ̇ ∝ ω·Δt. Procedure on the Pi:
1. Capture frames from `/dev/video0` (CVBS→USB dongle, `PI_BRINGUP.md` §5a) with per-frame host `CLOCK_MONOTONIC` timestamps; simultaneously read FC IMU/attitude over MSP (`/dev/ttyAMA0`, §5b) with its own host timestamps.
2. Excite a known oscillation: hand-rotate the rig sinusoidally (or mount on a turntable). Cross-correlate the image-domain global motion (ORB/RANSAC global shift from `mti.py:_register`, already on-target) against the gyro yaw-rate. The lag at peak cross-correlation = **time-sync residual** (mean Δt); the frame-to-frame spread of that lag = **jitter** (1-sigma).
3. Report: mean residual (ms), jitter 1-sigma (ms), and the implied λ̇ error `ω_max·Δt` (rad/s) at a representative body rate.
**ACCEPT/feedback:** the measured jitter 1-sigma becomes V2's `sensor_delay_jitter_s` operative value; the implied λ̇ error must be `<= IMMConfig.ego_gate_radps` (0.05 rad/s) or that gate is mis-tuned — a concrete cross-check between measurement and the A4 hardening already in `imm.py:190`.

**(b) field NETD / effective-bit-depth / post-AGC clutter PDF.** The 8-bit-AGC-CVBS chain's *real* noise is unknown; the sim assumes Gaussian `bearing_noise_sigma_rad=3e-4`. Procedure:
1. Point FT640 at a uniform thermal reference (or just the lab ceiling) and capture ~1000 static frames.
2. **NETD/effective bit depth:** temporal std per pixel → median over the array = post-AGC noise in counts; histogram the per-frame value distribution to count *actually-used* code levels (effective bit depth is usually < 8 after AGC). Report effective-bit-depth and per-pixel temporal noise (counts).
3. **Post-AGC clutter PDF:** point at a real cluttered scene (sky/horizon/ground), histogram the spatial residual after the `detect.py` top-hat+MAD stage; fit/empirically tabulate the tail (is it Gaussian or heavy-tailed? the roadmap M2 claims glint is heavy-tailed — this measures it).
**ACCEPT/feedback:** the measured post-AGC clutter PDF tail sets whether R2's Huber clip threshold and the CFAR `k` values are right; the per-pixel noise → bearing noise sigma replaces the `3e-4` guess. If the clutter PDF is heavy-tailed (kurtosis > 3 + margin), it *justifies* R2's robust loss quantitatively.

**New / changed tests + ACCEPTANCE THRESHOLDS.** These are *measurements*, not pass/fail gates — the deliverable is a numbers report, not a green test. The honest "acceptance" is: the measured jitter and noise values get written back into `IMMConfig`/sim config, and the V2 jitter band and R2 Huber threshold are re-derived from them. State explicitly: **until these run, V2's jitter magnitude and R2's clip threshold are placeholders.**

**Doctrine-invariant compliance.** Measurement-only; touches no guidance path. The benches are READ-ONLY (no arming, no RC), consistent with `PI_BRINGUP.md` §5 safety. Inv 6 (hard-mount) is directly relevant: the time-sync bench *assumes* a hard mount; if jitter is large it may indicate a soft mount, which the bench will surface — a useful side check on Inv 6.

**Dependencies.** Hardware gating only. (a) needs camera+IMU+MSP wired; (b) needs camera + a thermal reference. No software dependency on V1–V4, but its *outputs* re-tune V2 and R2.

**Risk & S3-gate sensitivity.** Zero closed-loop risk (offline measurement). The risk is purely logistical (hardware availability) and procedural (excitation quality for the cross-correlation).

**RPi5 bench-testability.** This IS the Pi bench task. Both benches follow the `latency_hwil.py` invocation pattern (`PYTHONPATH=fpv python -m fpv_ai.bench.timesync_bench --device /dev/video0 --port /dev/ttyAMA0`). The cross-correlation and histogramming are cheap; no frame-budget concern.

**Recommended executor model.** **strong** for the time-sync cross-correlation (subtle: lag-estimation sign, host-vs-device clock domains, and the ORB-shift↔gyro alignment are easy to get wrong and the result re-tunes a safety gate). **sonnet** acceptable for the field-noise histogram bench (mechanical stats), but the *interpretation* (heavy-tail decision feeding R2) wants a strong reviewer. Note: a model cannot run this — a **human must execute it on the physical rig**; the executor only writes the bench and the analysis.

---

### Cluster-level summary (do-now vs needs-hardware)

| Task | Pure SW now? | Touches closed-loop guidance (slow S3)? | Default-off | Main conflict | Executor |
|---|---|---|---|---|---|
| V1 / A1 ACQUIRE | Yes | **Yes** | Yes | R3 (same N code + test file) — **HIGH** | strong |
| V2 / A5 jitter+jink | Yes | **Yes** (timing) | Yes | V1/V3 share test file — MED | strong |
| V3 scenarios | Yes* | No | n/a (new tests) | needs `thermal_sim` knobs (read first) | sonnet + strong for sim ext |
| V4 doctrine matrix | Yes | No (runs Mode-A, no code change) | n/a | none — land FIRST | strong |
| V5 HW measurement | **No — needs RPi5+FT640+IMU** | No | n/a | none | strong (human executes) |

Honest gaps I cannot close from the read set: (1) V3 scenarios 1/3/4 depend on `ThermalSceneConfig` knobs I did not verify — **read `fpv/seeker/thermal_sim.py` next**; if knobs are missing, V3 grows a `ThermalSimulator`-extension subtask. (2) V2's jitter magnitude and R2's Huber threshold are placeholders **until V5 runs on hardware** — the numbers in V2's sweep band {0,5,10 ms} are plausible bounds, not measured. (3) Inv 6 is only architecturally testable in software (V4 guards the command schema; the physical mount is out of scope for any test).

Relevant files (absolute): `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/bearing_rate.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/command_map.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/closed_loop.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/quad_sim.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/guidance/tests/test_s3_acceptance.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/imm.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/track.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/looming.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/detect.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/fpv_ai/bench/latency_hwil.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/fpv_ai/control/speed.py`, `/Volumes/Samsa/ai_v2.0/03-fpv/PI_BRINGUP.md`. Prerequisite read for V3: `/Volumes/Samsa/ai_v2.0/03-fpv/fpv/seeker/thermal_sim.py`.

---

