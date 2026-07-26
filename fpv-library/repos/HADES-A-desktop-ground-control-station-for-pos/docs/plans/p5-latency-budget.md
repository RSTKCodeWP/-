# P5 — Glass-to-Glass Latency Budget (M3)

> **Gate (CLAUDE.md Hard Constraints):** in-app glass-to-glass latency — *frame on socket →
> painted with overlay + map pin* — **≤ 120 ms, measured.** Drone-link latency is **excluded**
> (it is outside the app). This is **distinct from** the P1.5 detection-throughput gate
> (≥ 10 fps); **both must hold.** Video displays at full 30 fps; detection is decoupled.

## What is measured

The **in-app** path only, instrumented at four boundaries in the renderer
(`ui/src/perf/latency.ts`, `LatencyMeter`), keyed by `frame_id`:

| Mark | Where | Meaning |
| --- | --- | --- |
| `socket` | `VideoPanel` frame handler (`videoFrameSink` push) | a frame arrived on the binary WS channel |
| `decoded` | `Image.onload` after JPEG → bitmap | the frame is decoded and ready to draw |
| `painted` | after `drawImage` + box overlay stroke | the frame is on screen **with its overlay** |

`totalMs = painted − socket` is the glass-to-glass figure; the per-stage sub-budget splits it
into `decodeMs` (`decoded − socket`) and `paintMs` (`painted − decoded`). A frame is only
sampled if it has **both** a `socket` and a `painted` mark — incomplete frames never fabricate
a sample. The map-pin update rides the same React tick as the contact-store ingest that feeds
the overlay, so "painted with overlay" is the binding visual event the budget targets.

## Methodology + honest provenance

- **Automated in-app measurement (`ui/tests/latency.spec.ts`, M3 spec):** runs the full app
  mock-driven (deterministic canned mission), paints ~90 frames, reads back
  `latencyMeter.report()`, and **asserts p95 ≤ 120 ms**. This proves the in-app stages are
  within budget and exercises the instrument end-to-end. It runs on the **CI/dev machine under
  software GL (swiftshader)** with the small canned frame — so the numbers are a **floor**, not
  the field figure.
- **The binding field gate is a manual on-device run** on the M4-class target (`/run` the
  packaged app against the recorded feed with real-resolution JPEG frames), reading the same
  `latencyMeter.report()`. Recorded here when run. The instrument is identical; only the
  hardware + frame size differ.
- **Provenance rule (P7):** never print a latency number without its hardware + frame-source
  context. Every figure below carries it.

## Measured (automated in-app, dev machine, swiftshader, canned frame)

Run 2026-06-25 (`pnpm exec playwright test tests/latency.spec.ts`):

```
[M3 latency] n=90  p50=1.9 ms  p95=22.4 ms  max=33.6 ms  mean=4.5 ms
```

- **p95 = 22.4 ms ≪ 120 ms** — the in-app path clears the budget by ~5.4× on dev hardware.
- The dominant stage is JPEG decode + canvas paint; both are sub-frame-time at 30 fps (33 ms).
- This is a **floor**: the field figure on real-resolution frames will be higher but has ~5×
  headroom to absorb it. Re-measure on-device to close the gate with the field number.

## Status

- ✅ Instrument built + unit-tested (`ui/src/perf/latency.test.ts`, 6 tests).
- ✅ Automated in-app p95 ≤ 120 ms assertion green (`tests/latency.spec.ts`).
- ⏳ **On-device field measurement pending** — manual `/run` on the M4-class target with the
  real recorded feed; paste the `[M3 latency]` line + hardware here to close the field gate.
- Cross-reference: P1.5 throughput gate (≥ 10 fps detection) in
  `docs/plans/spike-latency-results.md` — both gates must hold; they measure different things.
