> **[HISTORICAL]** — status as of 2026-07-19. 2026-06-20 completion record. Its claim of verification 'through the closed-loop S3 acceptance' is qualified: the 2026-06-20 audit found a large part of that suite tested the simulator's own assumptions (analytically-true LOS rate fed straight to guidance; tau from true range). See CHECKPOINT.md section 7.
>
> **`docs/CHECKPOINT.md` is the source of truth.** Where this document disagrees with it, CHECKPOINT wins.

<!-- Task-1 implementation campaign -- completion record + operator flag reference. 2026-06-20. -->

# TASK #1 CAMPAIGN — COMPLETION RECORD & FLAG REFERENCE

Persistent acquire-and-track-to-intercept of a maneuvering winged UAV, built per
`docs/TASK1_IMPLEMENTATION_SPEC.md`. **All four software stages implemented and verified through
the closed-loop S3 acceptance.** Every feature is behind a `default-off` flag whose OFF state is
**bit-identical** to the pre-campaign baseline; the 7 doctrine invariants are an executable CI gate
(`fpv/guidance/tests/test_doctrine_invariants.py`).

## Verification

| Stage | Closing-gate result | Notes |
|-------|---------------------|-------|
| 0 — foundation | full suite green | V4 doctrine gate + `derotate.py` bit-identical + V3 scenarios |
| 1 — Tier-0 estimator | **270 passed incl S3** | R1, R2, A1, R3, A5 |
| 2 — Tier-1 perception | **291 passed incl S3** | R4, R5, R6, R7 |
| 3 — Tier-2 correlation | **304 passed incl S3** | R8, R9, R10 |

Closing-geometry acceptance (`test_closing_acceptance.py`, G1 renderer): R5 silhouette aimpoint
walks <=0.6x the hotspot-pulled centroid; the full stack holds lock through closure.

## Operator flag reference (all default-off; pass to `SeekerGuidancePipeline(...)`)

| Flag | Feature | Effect when ON | New module / file |
|------|---------|----------------|-------------------|
| `use_imm_coast` | R1 | coast on IMM mixed-state, not 2-pt CV | track.py |
| `use_peak_relative_deletion` | R1 | lock-score peak-relative track deletion | track.py |
| (GuidanceConfig) `nis_lambda_smoothing`, `huber_enabled`, `r_extent_k` | R2 | NIS-scheduled λ̇ smoothing / robust update / R inflate | imm.py, bearing_rate.py |
| (GuidanceConfig) `acquire_settle_ticks` | A1 | low-gain ACQUIRE ramp before full N | bearing_rate.py |
| `use_tau_terminal` | R3 | τ-driven terminal commit (range-free) | command_map.py |
| (GuidanceConfig) `N=2.6` | R3 | falcon-low navigation ratio | bearing_rate.py |
| `regime_enabled` | R4 | POINT/RESOLVED/FILL angular-scale FSM | track.py |
| `aimpoint_migration` | R5 | hotspot→silhouette aimpoint (RESOLVED/FILL) | aimpoint.py |
| `event_channel` | R6 | AGC/background-invariant motion locator | event_channel.py |
| `require_consensus_for_lock` | R7 | intensity∧motion consensus before LOCKED | track.py |
| `correlation` | R8 | MOSSE structural confidence → lock-score | correlation.py |
| `prewarp` | R9 | anticipatory exp(-Δt/τ) template pre-warp | correlation.py |
| `jpda_enabled` | R10 | JPDA soft centroid on a cluttered gate | track.py |

A5 (`closed_loop.run_monte_carlo(randomize=True, latency_jitter_max_s=..., target_step_jink_max_g=...)`)
sweeps the honest stressors. The latency harness `fpv_ai.bench.latency_hwil` accepts every flag for
on-target profiling (`--correlation`, `--aimpoint-migration`, ...).

## Doctrine compliance (held green throughout)

Inv 1 range never scales gain · Inv 2 quality/PSR/appearance never moves centroid/LOS (R1/R5/R8/R10
each ship a bit-equality guard) · Inv 3 abort = PASS · Inv 4 IMM modified-polar · Inv 5 ≤0.84 g ·
Inv 6 no gimbal actuation · Inv 7 no new post-commit track.

## Remaining (NOT software — blocked)

- **Stage 4 / V5** — cam↔IMU time-sync residual + field NETD/clutter-PDF: needs the RPi5 rig (camera
  + FC). Pi offline as of 2026-06-20. On-Pi R8 latency profile deferred (Mac proxy: correlation adds
  ~1 ms p99; Pi baseline compute ~17 ms, passes the R1 30 ms assumption).
- **Turn the flags ON for gates G-A / G-B** — needs real FT640 data + the Pi.
- **Phase C** (onboard abort authority) — the critical blocker for autonomy beyond the bench; a
  separate large block, not part of Task-1.

Everything above is uncommitted in the working tree (no commit made without request).
