# HADES Documentation — Content Gate and Outline (Task 7.0)

This is the artifact-inventory gate for Phase 7. It is **not prose**. It maps every
planned documentation section and figure to the **real artifact** it draws from. The
rule is absolute: **no figure or claim ships unless it can name its source artifact.**
Where a needed artifact does not exist, that is recorded as a **gap to disclose**, never
a number to invent.

All numbers below were either read from a committed result file or produced by running
the real code at `seed=0` on 2026-06-26. Localization and coverage numbers are
**deterministic** (seeded) and reproduce exactly.

Honesty posture carried into every doc surface:
- Detection metrics are on the **HERIDAL held-out scene split** (leakage-guarded), at a
  fixed operating point. Selection optimism is disclosed.
- Localization meter numbers are **simulator (sim)** numbers from a calibrated synthetic
  pipeline. They are tagged `(sim)` everywhere and the pending real-flight dataset
  (~2026-07-01) is named. The sim proves the method is correct and the uncertainty is
  calibrated; it does not establish a field meter-accuracy number.
- Latency p95 (22.4 ms) is a **dev/CI floor** under software GL, not the binding field
  number. The on-device field run is pending and labeled as such.

---

## Section 1 — Detection model + localization (the "what it does" + accuracy)

### 1a. Detection: precision / recall / mAP

| Claim / figure | Real value | Source artifact |
| --- | --- | --- |
| Shipped FP16 Core ML recall @ operating point | **0.551** recall, 0.676 precision (TP 793 / FP 380 / FN 645) | `docs/plans/p2.5-acceptance.md` (shipped-FP16 acceptance table) |
| `.pt` checkpoint acceptance (center-distance, 50 px) | 0.509 recall, 0.624 precision (TP 732 / FP 442 / FN 706) | `docs/plans/p2.5-acceptance.md` |
| FP16 did **not** degrade vs float32 | +0.042 recall, +0.052 precision (decode path more permissive) | `docs/plans/p2.5-acceptance.md` |
| Ultralytics val (training-time proxy, Arm A) | recall 0.910, mAP@0.5 0.952, mAP@0.5:0.95 0.663 | `artifacts/armA_heridal_sard/results.csv` (epoch 100) + `docs/plans/p2.5-training-results.md` |
| VisDrone-pretrain ablation (Arm B) underperforms on anchor | recall @50px 0.401 vs Arm A 0.510 → **Arm A ships** | `docs/plans/p2.5-training-results.md` |
| Confidence-threshold sweep (recall/precision tradeoff) | conf 0.25 → 0.51/0.62; 0.10 → 0.63/0.46; 0.05 → 0.69/0.37 | `docs/plans/p2.5-acceptance.md` |
| Split sizes (leakage-guarded) | train 5835 / val 1144 / test 376 imgs, 1438 person instances; scenes {CAP, JAS, ZRI} held out | `docs/plans/p2.5-training-results.md` |

**Figures backed:**
- `fig-detection-pr` — PR operating points from the 3-point confidence sweep (0.05 / 0.10 / 0.25). Honest as a 3-point operating-curve, **not** a smooth full PR curve (disclose).
- `fig-detection-conf-sweep` — recall vs precision across the 3 confidence points.
- `fig-quant-delta` — `.pt` float32 vs shipped FP16 (recall + precision bars).

### 1b. Resolution decision (feeds both detection and real-time)

| Claim / figure | Real value | Source artifact |
| --- | --- | --- |
| Recall by inference resolution (Arm A, HERIDAL held-out) | 640 → 0.417 / 0.689; **960 → 0.510 / 0.624**; 1280 → 0.511 / 0.559; 1920 → 0.452 / 0.442 | `docs/plans/p2.5-training-results.md` |
| Chosen resolution = **960** (peaks, ties 1280 within noise, better precision; ≥10 fps by wide margin) | — | `CLAUDE.md`, `docs/DESIGN.md`, `docs/plans/p2.5-training-results.md` |

**Figure backed:** `fig-resolution-tradeoff` — recall (and precision) vs resolution, with the 960 pick annotated.

### 1c. Localization meter error (sim, stratified)

Generated live by `hades-locsim --targets 30 --seed 0` (deterministic). Source code:
`service/src/hades/eval/locsim_report.py`. Every value tagged `(sim)`.

| range × pitch (deg from nadir) | n | median (sim) | mean | p90 | max | coverage |
| --- | --- | --- | --- | --- | --- | --- |
| [30-80) × [0-15) (near-nadir) | 30 | **1.2 m** | 1.4 m | 2.2 m | 3.7 m | 0.97 |
| [80-150) × [0-15) | 30 | 7.6 m | 9.0 m | 15.6 m | 30.5 m | 0.80 |
| [150-300) × [65+) (gated/oblique) | 60 | 11.8 m | 12.2 m | 17.4 m | 32.6 m | 1.00 |
| moving target (drifts 5 m/frame) | — | R95 **84 m**, class AREA, CONVERGING (never PINPOINT) | | | | |

**Figures backed:**
- `fig-loc-error-by-geometry` — median/p90 meter error per stratum (the honest "near-nadir is PINPOINT, oblique is AREA" story).
- ~~`fig-loc-cdf`~~ — **DROPPED (7.2 decision).** The report emits per-stratum summary stats (median/mean/p90/max), not the raw per-trial error list, so a true CDF would need only 3-4 summary points. A 3-point CDF is weak and borderline misleading. `fig-loc-error-by-geometry` carries the localization-accuracy story honestly instead. Recorded here rather than faked.

### 1d. Localization uncertainty calibration (coverage matrix, sim)

Generated live by `run_coverage_matrix(n_trials=200, seed=0)`. Source:
`service/src/hades/eval/coverage.py`. This is the **flagship honesty proof** (anti-circular).

| row | coverage | mean NEES | median R95 | meaning |
| --- | --- | --- | --- | --- |
| matched_control | 0.995 | 1.16 | 3.63 m | arithmetic correct (≈95%+ target) |
| sigma_underestimate | 0.950 | 1.90 | 3.37 m | under-modeled jitter → lower coverage |
| sigma_overestimate | 0.985 | 1.00 | 3.55 m | over-conservative → over-covered |
| heading_bias_crab | 0.955 | 1.75 | 2.99 m | crab bias detected |
| gps_heavy_tail | 1.000 | 1.12 | 3.66 m | heavy-tail GPS absorbed |
| time_sync_50ms | 0.965 | 1.65 | 3.82 m | small offset, small drop |
| time_sync_100ms | 0.850 | 3.01 | 3.72 m | offset bites |
| **time_sync_200ms** | **0.255** | **11.93** | 3.28 m | **out-of-schema failure: MC cannot model time-sync, so coverage collapses honestly** |

**Figure backed:** `fig-coverage-calibration` — coverage per row vs the 95% target band, with the time-sync collapse as the headline (the non-tautology proof).

---

## Section 2 — Real-time performance (FPS + latency)

### 2a. Detection throughput per resolution (ANE, measured)

| Claim / figure | Real value | Source artifact |
| --- | --- | --- |
| ANE forward-pass FPS (MacBook Air M4, FP16, ComputeUnits.all) | 640 → 292.8 fps; **960 → 63.1 fps**; 1280 → 56.7 fps (all ≥ 10 fps) | `docs/plans/spike-latency-results.md` |
| ANE-served (not CPU fallback) | CPU_AND_NE ≈ 3.5 ms vs CPU_ONLY ≈ 19.8 ms @ 640 → **5.6× speedup** | `docs/plans/spike-latency-results.md` |

**Figures backed:**
- `fig-fps-by-resolution` — FPS bars per {640, 960, 1280} with the 10 fps gate line.
- `fig-ane-speedup` — CPU_ONLY vs CPU_AND_NE vs ALL latency at 640 (proves ANE placement).

### 2b. In-app glass-to-glass latency (dev floor, measured)

| Claim / figure | Real value | Source artifact |
| --- | --- | --- |
| In-app p95 (socket → decode → paint w/ overlay), dev/CI swiftshader, 90 frames | p50 1.9 ms, **p95 22.4 ms**, max 33.6 ms, mean 4.5 ms — clears 120 ms budget by ~5.4× | `docs/plans/p5-latency-budget.md` + `ui/tests/latency.spec.ts` |

**Figure backed:** `fig-latency-budget` — measured p50/p95/max vs the 120 ms budget bar.
**Disclosed gap:** this is a **floor** (software GL, small canned frames). On-device
field run on the Air M4 with real-resolution frames is **pending** and labeled pending.

---

## Section 3 — Qualitative showcase (real frames + map)

| Figure | Source artifact | Status |
| --- | --- | --- |
| `showcase-boxes` — detection boxes on footage | **real HERIDAL holdout frame** (`artifacts/heridal_holdout_test/images/*.JPG`, 4000x3000 aerial SAR, the leakage-guarded test split) + the Arm A ONNX detector | **DONE (7.4).** Picked the person-richest frame (35 GT persons); 15 real detections drawn + a zoomed crop. Stronger than the 64x48 clip_2s fixture. |
| `showcase-before-after` — stock vs fine-tuned | stock `service/models/yolo11s_640.onnx` vs fine-tuned `artifacts/armA_heridal_sard/models/yolo11s_960.onnx`, same HERIDAL frame (each at its shipped resolution) | **DONE (7.4).** The P2.5 win, side by side on real footage. |
| `showcase-map` — survivor map w/ pins + ellipses | **already rendered:** `docs/assets/p6/demo-site.png` (full coordinator UI, pins by tier, ellipses, drone track) | **Reuse as-is.** |
| `showcase-coordinator` — full UI layout | `docs/assets/p5/coordinator-full.png`, `docs/assets/p5/contact-list-detail.png`, `docs/assets/p5/status-strip.png` | **Reuse as-is.** |

---

## Section 4 — System overview + branding

| Element | Source artifact |
| --- | --- |
| HADES logo (top of README + in-app docs) | `HADES_logo.png` (1024×1024, repo root) → copy to `docs/documentation/assets/` |
| Architecture diagram (pipeline module map) | generate in 7.2 from the `CLAUDE.md` module map via gstack `/diagram` (FrameSource → Detector → Tracker → Projector → Confirmation → Fuse+Quantify → UI) |
| "Built with" tool badges (exact versions) | **read from lockfiles, not guessed** (Task 7.5): Python — `service/pyproject.toml` + `artifacts/armA_heridal_sard/requirements.lock.txt` (training env: torch 2.11.0+cu128, ultralytics 8.4.76, numpy 2.4.4); runtime — pyproject specifiers (numpy≥1.26, av≥12, opencv≥4.9, onnxruntime≥1.18, pydantic≥2.7, websockets≥12); UI — `ui/package.json` + `ui/pnpm-lock.yaml` (React 18.3, Vite 6, Electron 33, MapLibre GL 5, Tailwind 3, Zustand 5, TypeScript 5.7) |
| Demo-site link | the P6 static site (`pnpm build:web` → `dist-web/`); link slot filled when the user publishes Pages |

---

## Gaps to disclose (never invent)

These are expected figures with **no real backing yet**. They are disclosed as pending,
not fabricated:

1. **Per-subclass recall** (in-water/head-only, rooftop, debris-occluded). HERIDAL labels
   lack subclass tags. Machinery exists (`eval/detection_metrics.py::recall_by_size`);
   numbers land with the curated disaster set (~2026-07-01). `hades-eval` exits non-zero
   ("dataset not found") rather than fabricating.
2. **Size-stratified recall numbers** — same reason; harness ready, no tagged set.
3. **Full smooth PR curve** — only a 3-point confidence sweep exists. Render as discrete
   operating points, labeled as such.
4. **Real-flight localization meter numbers** — sim only; real dataset pending.
5. **On-device field glass-to-glass latency** — instrument built; the binding field run
   on the Air M4 is pending.
6. **FP/km² system-level false-positive rate** — `eval/fp_per_km2.py` exists; a full
   end-to-end measured curve is a v1.x item. Mention the metric, do not plot an invented one.
7. **Offline PMTiles basemap** — not baked on disk; map renders on a flat dark canvas.
   The map screenshot (`docs/assets/p6/demo-site.png`) is real regardless.

---

## Figure manifest (the contract 7.1–7.4 must satisfy)

Every figure below must trace to a row above. Anything not on this list does not ship.

| figure id | family | data source | renderer |
| --- | --- | --- | --- |
| fig-detection-pr | detection | p2.5 conf sweep | Python (7.2) |
| fig-detection-conf-sweep | detection | p2.5 conf sweep | Python (7.2) |
| fig-quant-delta | detection | p2.5 acceptance | Python (7.2) |
| fig-resolution-tradeoff | detection | p2.5 resolution table | Python (7.2) |
| fig-loc-error-by-geometry | localization | hades-locsim seed=0 | Python (7.2) |
| fig-loc-cdf | localization | hades-locsim (raw errs, 7.1 extension) | Python (7.2) |
| fig-coverage-calibration | localization | coverage matrix seed=0 | Python (7.2) |
| fig-fps-by-resolution | real-time | spike-latency-results | Python (7.2) |
| fig-ane-speedup | real-time | spike-latency-results | Python (7.2) |
| fig-latency-budget | real-time | p5-latency-budget | Python (7.2) |
| fig-arch | overview | CLAUDE.md module map | gstack /diagram (7.2) - DONE: mmd/svg/png/excalidraw |
| hero-loc-error-surface | localization | localization_surface.csv (dense real sim sweep) | **Wolfram (7.3) - script ready, USER runs** |
| hero-coverage-3d | localization | coverage_matrix.csv | **Wolfram (7.3) - script ready, USER runs** |
| hero-survivor-map | localization | mission_contacts.csv (real contacts) | **Wolfram (7.3) - script ready, USER runs** |
| showcase-boxes | qualitative | real HERIDAL holdout frame + Arm A ONNX detector | Python (7.4) - DONE: real boxes on real aerial SAR footage |
| showcase-before-after | qualitative | stock vs Arm A ONNX, same HERIDAL frame | Python (7.4) - DONE: the P2.5 win, visible |
| showcase-map | qualitative | docs/assets/p6/demo-site.png | reuse |
| showcase-coordinator | qualitative | docs/assets/p5/*.png | reuse |
</content>
