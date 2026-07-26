# Phase 1.5 — Latency spike results

**Status:** ✅ **complete** — benchmarked on the MacBook Air M4 (2026-06-24); ANE placement
verified; feasible set {640, 960, 1280} recorded in DESIGN.md §5.
**Measures:** latency only. The final resolution pick (latency × recall) is **deferred
to P2.5** against fine-tuned recall (implementation-plan review note F5) — picking a
resolution against stock-COCO recall would be tuning a model we're about to replace.

## Why the Air M4 is the machine

The ≥10fps gate is a **field-laptop** gate. CLAUDE.md Hard Constraints make the
MacBook Air M4 the floor, and the Air is fanless — it throttles under sustained load.
The Neural Engine is ~identical across the M4 line (16-core ~38 TOPS on M4 / M4 Pro /
M4 Max; Apple scales CPU/GPU cores across tiers, not the ANE), so a "faster" Mac would
give an **optimistically cool-clock** number that the field laptop can't hold. The Air's
*throttled sustained* latency is the honest worst case, so it is the right and sufficient
machine — no better hardware needed.

This is why the harness **warms up, then times a sustained window** (default 30 warm-up
+ 300 timed frames) rather than a cold burst: throttling only shows up under sustained
inference.

## Method (reproducible)

```bash
cd service
uv sync --group bench                     # installs ultralytics + coremltools (numpy<2)

# 1. Export stock YOLO11s -> CoreML .mlpackage at each resolution (FP16, ComputeUnits.all)
uv run --group bench hades-export-coreml --res 640 960 1280

# 2. Benchmark sustained ANE latency per resolution
#    (--verify-ane also confirms ComputeUnits.all is actually served by the ANE,
#     not a silent CPU/GPU fallback — exits non-zero if it falls back)
uv run --group bench hades-bench-latency --res 640 960 1280 --verify-ane
```

Run with **nothing else heavy on the machine**, on **battery vs. plugged-in both noted**
if they differ (throttling can depend on power source). The verdict is judged on the
**median** fps (one thermal/GC spike shouldn't flip it); **p90** is reported so a long
tail stays visible.

- Model: stock `yolo11s` (COCO), FP16, `ComputeUnits.all`.
- Gate: detection ≥ **10 fps** (decoupled from the 30fps video path).
- Stack: see `service/pyproject.toml` `[dependency-groups].bench` (numpy pinned <2 —
  coremltools 9.0 crashes the export on numpy 2.x; root cause recorded in
  `tasks/lessons.md`).

## Results — MacBook Air M4 / 32 GB (✅ recorded 2026-06-24)

`hades-bench-latency --res 640 960 1280` (default window: 30 warm-up / 300 timed frames):

| Resolution | median ms | p90 ms | mean ms | fps (median) | ≥10fps? |
|---:|---:|---:|---:|---:|:---:|
| 640  | 3.4  | 3.8  | 3.5  | 292.8 | ✅ |
| 960  | 15.8 | 17.1 | 16.3 | 63.1  | ✅ |
| 1280 | 17.6 | 22.7 | 18.5 | 56.7  | ✅ |

**feasible (≥10fps) resolutions: {640, 960, 1280} — all three pass.**

**Machine / conditions:**
- Mac: MacBook Air M4 / 32 GB · stock `yolo11s` (COCO), FP16, `ComputeUnits.all`.
- Window: warm-up 30 / timed 300 frames per resolution.

### ANE placement — VERIFIED (this is the load-bearing check)

`ComputeUnits.all` does **not** guarantee Neural-Engine placement — Core ML places per-op
and can silently fall back to GPU/CPU. The numbers above are only meaningful if the ANE
actually served them, so we compared compute units at 640²:

| compute_units | median ms | fps |
|---|---:|---:|
| `CPU_ONLY`   | 19.8 | 50.6 |
| `CPU_AND_NE` | 3.5  | 283.2 |
| `ALL`        | 3.8  | 262.4 |

`ALL` tracks `CPU_AND_NE` (~3.5 ms), **not** `CPU_ONLY` (~20 ms) → the ANE is serving the
run (≈5.6× the CPU-only path). The `CPU (Apple M4)` line in the *export* banner is the
PyTorch **tracing** device, not the inference device — a red herring.

## Decision

- **Feasible (≥10fps) set: {640, 960, 1280}** — recorded in `docs/DESIGN.md` §5. Even the
  slowest (1280 at 56.7 fps) clears the 10 fps gate by **5.7×**; 640 clears by ~29×.
- **Honest caveats (do not over-read these as the production detection budget):**
  - Raw `predict()` only — excludes letterbox resize, NMS, and tensor marshalling that the
    live detection stage adds. Detection wall-clock will be higher than these forward-pass
    numbers; the **≤120 ms glass-to-glass** budget is measured end-to-end in Phase 5,
    separate from this throughput gate.
  - Window is ~5 s at 640; the headroom (5.7×–29×) is far larger than any plausible
    sustained-thermal drift on the fanless Air, so all three stay feasible under load.
  - Same architecture as the fine-tuned model → latency essentially unchanged at P2.5.
- **RESOLVED in P2.5 (Task 2.5.5): chosen resolution = 960.** Latency did not bind (all three
  pass), so the pick was made on *fine-tuned* held-out HERIDAL-test recall: recall peaks at
  960, ties 1280 within noise but with better precision, and degrades at 1920. So "largest
  recall wants" and "smallest that meets the floor" converge on 960 — recall does not reward
  going bigger here. See `docs/plans/p2.5-training-results.md`.
