# HADES Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

> **⛔ NO GIT COMMITS for this entire project.** Every task below ends with a "Step 5: Commit"
> — **DO NOT run those commits.** Do the implementation work and run the tests; treat each
> commit message purely as the task's label/done-marker. The user will handle all commits later.
> `git init`/branching for tooling is fine; committing is not. This overrides every commit step.

> **🔁 AUTO-ADVERSARIAL REVIEW, NOT CONFIRMATION PROMPTS.** Do NOT pause to ask the user
> "should I do X or Y?" or "does this look right?". Instead, at any such decision point,
> dispatch a team of adversarial subagents (skeptic / domain-expert / red-team / simplicity)
> to stress-test the progress + the decision, fold in what survives, and proceed. Surface to
> the user ONLY for (a) a genuine contradiction the agents can't resolve, or (b) a fact only
> the user holds (GPU cluster details for P2.5; whether the real dataset has synchronized pose
> for P4). Don't over-trigger on trivial mechanical steps. Also run this panel at each phase's
> green-criterion check before declaring the phase done.

**Goal:** Build a desktop ground-control station that ingests recorded FPV-drone video + telemetry, detects humans in real time, computes survivor coordinates with honest uncertainty, and presents them in a professional coordinator UI — all validated offline against a recorded feed.

**Architecture:** Two processes over localhost WebSocket. Python service runs the pipeline `FrameSource → Detector → Tracker → Projector → Confirmation → Fuse+Quantify`; Electron/React UI renders map + video + list as projections of one selected Contact. See `docs/plans/2026-06-23-hades-design.md` (approved design) and `CLAUDE.md` (module map).

**Tech Stack:** Python (uv, Ultralytics YOLO, Core ML/coremltools, PyAV, pyserial, numpy, pytest, ruff), TypeScript/Electron/React/Vite/Tailwind/shadcn/Zustand/MapLibre GL (pnpm, Playwright).

**Phase order** (each *code* phase ends green + independently runnable, observable against the recorded feed; spike/research sub-phases produce a doc/decision, not a runnable feature):
P0 Scaffold · P1 Ingestion · P1.5 Latency spike (decision) · P2 Detection · **P2.5 Model fine-tuning** · P3 Track+Project+Confirm · **P4 Localization (flagship)** · **P5 Coordinator UI (flagship)** · P6 Demo website (static, canned-mission replay) · P7 Documentation & presentation (capstone)

**Flagship phases** (P4, P5) open with a research/spike sub-phase gate before TDD tasks.

**External review policy** (runs at each phase's green check, AFTER the internal adversarial subagent panel — a second, independent opinion; read-only, it reports, it does not edit):

**Review → TRIAGE → fix → re-verify (the review is not the end — acting on it is).** Codex/gstack only report; the executing Claude session must then:
1. **Triage** each finding with `superpowers:receiving-code-review` judgment → *valid-fix-now* / *valid-but-out-of-scope (log it)* / *invalid or context-wrong (reject + one-line reason)*. Do NOT blind-implement feedback; reject what's wrong for our context (e.g. "you should commit this" violates the no-commit rule).
2. **Fix** valid-now findings via TDD: write a failing test that reproduces the issue → fix → green. (If you can't write a failing test, the finding probably isn't real — that's the false-positive filter.)
3. **Re-verify** the phase's green criterion still holds after fixes. Only then is the phase done.
A phase is NOT complete just because the review ran — it's complete when the review's valid findings are fixed-and-verified or explicitly rejected with reasons.

- **Codex** is the correctness second-opinion — a different model, so it catches blind spots the Claude subagent panel shares. **`/codex` adversarial review** on the flagship/safety-critical logic; **`/codex` regular review** as a lighter pass on medium phases.
- **gstack `/design-review` + `/qa`** are the UI/looks-AI second-opinion at P5/P6 — Codex can't see the rendered UI, so it's the wrong tool there.
- **SCOPE EVERY CODEX CALL BY PATH, not diff.** No-commit ⇒ no diff boundary ⇒ Codex otherwise re-reviews the whole tree every time (the "large untracked body" message). Always point it at just the current phase's paths.
- **Don't over-review:** mechanical phases (P0, P1.5) get no external pass — internal tests + subagent panel suffice. Reactive tools (`/codex` rescue, gstack `/investigate`) are for when a phase is STUCK, never on a schedule.

Per-phase external review (tag repeated on each phase header below):
| Phase | External review | Scope (paths) |
|---|---|---|
| P0 | none (scaffold) | — |
| P1 | `/codex` regular (optional) | `service/src/hades/ingest/` + its tests |
| P1.5 | none (measurement) | — |
| P2 | `/codex` regular (optional) | `service/src/hades/detect/`, `eval/detection_metrics.py` + tests |
| **P2.5** | **`/codex` adversarial** | `service/src/hades/train/`, export + ablation; metric-honesty |
| **P3** | **`/codex` adversarial** | `service/src/hades/{track,locate,confirm}/`, `eval/fp_per_km2.py` + tests |
| **P4** | **`/codex` adversarial (mandatory)** | `service/src/hades/locate/` (geometry, fuse, uncertainty, coverage) + tests |
| **P5** | **gstack `/design-review` + `/qa`** (NOT Codex) | the running UI in a browser |
| P6 | gstack `/qa` on the deployed demo | the static site |
| P7 | gstack `/document-generate` + adversarial filler/AI-prose/unsupported-claim panel | `README.md`, `docs/documentation/`, in-app Docs page |

**Execution rule:** one phase per session; at 400k context, "one phase then stop" is firm.

**Single-source-of-truth discipline** (prevents the coordinate-convention divergence the design fears): the ray→ground math lives in ONE module (`locate/geometry.py`, built in P3) imported by Projector AND Fuse; the sensor-error/config schema lives in ONE module (`locate/error_model.py`) consumed by sim AND Monte Carlo. Never re-implement either.

---

## Phase 0 — Scaffold (ends green: empty pipeline runs, CI passes)

**Goal:** Both sub-projects scaffolded, a CPU-only CI workflow authored (runs when commits resume — see no-commit rule), and `docs/DESIGN.md` skeleton. No domain logic yet.

### Task 0.1: Initialize repo (NO commit)

**Step 1:** Run `git init` in project root (needed so tooling/branching works); create `.gitignore` (Python `__pycache__`, `.venv`, `node_modules`, `dist`, `*.mlpackage`, `data/`, `.DS_Store`, `cs1.pdf` and any stray non-project files).
**Step 2:** **Do NOT commit.** Leave everything staged-or-unstaged as-is. (Per the no-commit rule, `git init` is fine; committing is not.)

### Task 0.2: Scaffold Python service

**Files:** Create `service/pyproject.toml`, `service/src/hades/__init__.py`, `service/tests/test_smoke.py`.

**Step 1: Write the failing test**
```python
# service/tests/test_smoke.py
def test_package_imports():
    import hades
    assert hades.__version__
```
**Step 2: Run, verify fail.** `cd service && uv run pytest tests/test_smoke.py -v` → FAIL (no `__version__`).
**Step 3: Implement.** Add `__version__ = "0.0.0"` to `hades/__init__.py`; configure `pyproject.toml` (deps: pytest, ruff, numpy; entry points `hades-service`, `hades-eval`, `hades-locsim` as stubs).
**Step 4: Run, verify pass.**
**Step 5: Commit:** `chore: scaffold python service`.

### Task 0.3: Scaffold UI shell

**Files:** Create `ui/package.json`, Vite+React+TS+Electron skeleton, `ui/tests/smoke.spec.ts`.

**Step 1:** Write a Playwright test asserting the Electron window opens and shows an app-root element.
**Step 2:** Run `cd ui && pnpm test` → FAIL (no app).
**Step 3:** Scaffold Vite+React+TS, Tailwind, Electron main that loads the renderer, an `#app-root` div, wire `pnpm dev/test/build/start`.
**Step 4:** Run, verify pass.
**Step 5: Commit:** `chore: scaffold electron+react ui shell`.

### Task 0.4: CPU-only CI

**Files:** Create `.github/workflows/ci.yml`.

**Step 1:** Author the workflow: runs `uv run pytest` + `uv run ruff check` (service) and `pnpm test` (ui) on push. Detection/ANE tests marked `@pytest.mark.ane` and **excluded** on CI (no GPU/ANE on runners). NOTE: since this project doesn't commit/push (no-commit rule), CI won't *trigger* yet — the file is authored now so it's ready when commits resume; **the real per-phase gate during development is running the test commands locally**, not CI.
**Step 2: Commit:** `ci: cpu-only test + lint pipeline`.

### Task 0.5: DESIGN.md skeleton

**Files:** Create `docs/DESIGN.md` with section stubs: Module boundaries, WS message schema (TBD, filled P2), Coordinate conventions (datum WGS84, lat/lng order, image-axis origin, NED/FRD frames — fill now since it's pure reference), Data layout.
**Step:** Commit: `docs: design.md skeleton with coordinate conventions`.

**Phase 0 green criterion:** `uv run pytest`, `uv run ruff check`, `pnpm test` all pass in CI.

---

## Phase 1 — Ingestion (ends green: replay recorded feed → frames + time-synced pose, observable)

> **External review (green check):** `/codex` regular review (optional), scoped to `service/src/hades/ingest/` + tests.

**Goal:** `FrameSource` and `TelemetrySource` replay impls yield frames and pose aligned by `frame_id`. A CLI dumps annotated frames so ingestion is visually observable. Live impls stubbed.

### Task 1.1: FrameSource interface + SyntheticFrameSource

**Files:** Create `service/src/hades/ingest/frame_source.py`, `service/tests/ingest/test_frame_source.py`.

**Step 1: Failing test**
```python
def test_synthetic_source_yields_timestamped_frames():
    src = SyntheticFrameSource(n=3, w=64, h=48)
    frames = list(src)
    assert len(frames) == 3
    assert frames[0].seq == 0
    assert frames[0].frame.shape == (48, 64, 3)
    assert frames[1].timestamp > frames[0].timestamp
```
**Step 2:** Run → FAIL.
**Step 3:** Define `Frame` dataclass `(frame: np.ndarray, timestamp: float, seq: int)`, `FrameSource` ABC (`__iter__`), `SyntheticFrameSource` (generates gradient frames, monotonic timestamps).
**Step 4:** Pass. **Step 5: Commit:** `feat: framesource interface + synthetic impl`.

### Task 1.2: FileFrameSource (PyAV, real recorded video)

**Files:** Create `service/src/hades/ingest/file_frame_source.py`, test + a tiny committed sample `.mp4` fixture (`service/tests/fixtures/clip_2s.mp4`).

**Step 1: Failing test** — open fixture, assert ≥1 frame, correct shape, timestamps monotonic.
**Step 2:** Run → FAIL.
**Step 3:** Implement with PyAV; enable VideoToolbox HW decode where available; per-frame dimension read (no caching); skip-on-decode-error.
**Step 4:** Pass. **Step 5: Commit:** `feat: file framesource via pyav`.

### Task 1.3: Stress behavior — drops / resize / drop-to-latest

**Step 1: Failing tests** — (a) corrupt frame is skipped not raised; (b) mid-stream resolution change handled; (c) `LatestFrameBuffer` returns newest under backpressure, never backlog.
**Step 2-4:** red→green per test.
**Step 5: Commit:** `feat: ingestion tolerates drops/resize, drop-to-latest buffer`.

### Task 1.4: TelemetrySource + SrtFileSource

**Files:** Create `service/src/hades/ingest/telemetry_source.py`, `srt_file_source.py`, test + `.srt` fixture.

**Step 1: Failing test** — parse `.srt` sidecar → `Pose(lat, lon, alt, roll, pitch, yaw_or_cog, t)` samples; assert field values against a hand-checked fixture line.
**Step 2:** Run → FAIL.
**Step 3:** Implement `.srt`/`.osd` parser (DJI O4 format); `TelemetrySource` ABC.
**Step 4:** Pass. **Step 5: Commit:** `feat: telemetrysource + srt replay parser`.

### Task 1.5: Time-sync alignment by frame_id

**Files:** Create `service/src/hades/ingest/sync.py`, test.

**Step 1: Failing tests** — (a) each frame gets the nearest-timestamp pose (SLERP attitude / lerp position interpolation); (b) **injected constant offset + jitter** shifts the pairing correctly (mandatory time-sync-error test); (c) missing telemetry → flagged, not crash.
**Step 2-4:** red→green.
**Step 5: Commit:** `feat: frame<->telemetry time-sync with injectable offset`.

### Task 1.6: Stub live sources

**Step 1:** `UvcFrameSource` and `CrsfSerialSource` raise `NotImplementedError("live path built with hardware")` behind the same interfaces; a test asserts they're importable and raise.
**Step 2: Commit:** `feat: stub live frame/telemetry sources behind interface`.

### Task 1.7: Observable CLI — dump annotated frames

**Files:** Create `service/src/hades/cli/replay_dump.py`.

**Step 1:** CLI replays a clip + telemetry, writes frames to disk with pose overlaid (alt/attitude text). Test: runs on fixture, produces N images.
**Step 2-4:** red→green.
**Step 5: Commit:** `feat: replay-dump cli (observable ingestion)`.

**Phase 1 green criterion:** `uv run hades replay-dump tests/fixtures/clip_2s.mp4` produces annotated frames; all ingestion tests pass.

---

## Phase 1.5 — Latency spike (decision: bound the feasible detection resolution)

**Goal:** Measure ANE **latency** per resolution to bound which resolutions can hold ≥10fps. **This is a spike — a decision + recorded benchmark, not production code.** Note (per review F5): this measures **latency only**. The *final* resolution pick (latency × recall) is deferred to P2.5 after fine-tuning, because picking resolution against stock COCO recall would be measuring a model we're about to replace.

### Task 1.5.1: Export baseline YOLO11s to Core ML at three resolutions

**Step 1:** Script exports stock `yolo11s` to `.mlpackage` at 640, 960, 1280 (FP16, ComputeUnits.all). Commit the script; the produced `.mlpackage` artifacts are gitignored but written to a known `models/` path the benchmark loads.
**Step 2: Commit:** `chore: coreml export script (resolution sweep)`.

### Task 1.5.2: Benchmark latency on target hardware

**Step 1:** Benchmark harness measures ms/frame on ANE for each resolution on the M-series dev machine (marked `@pytest.mark.ane`, manual run).
**Step 2:** Run manually; record FPS-per-resolution in `docs/plans/spike-latency-results.md`.
**Step 3: DECISION (latency bound):** record which resolutions hold ≥10fps. Do NOT finalize the resolution yet — note the feasible set in `docs/DESIGN.md` (the final pick happens in P2.5 Task 2.5.5 against fine-tuned recall).
**Step 4: Commit:** `docs: latency spike results + feasible resolution set`.

**Phase 1.5 green criterion:** committed results doc; the feasible (≥10fps) resolution set recorded in DESIGN.md.

---

## Phase 2 — Detection (ends green: Core ML YOLO draws boxes on the recorded feed)

> **External review (green check):** `/codex` regular review (optional), scoped to `service/src/hades/detect/` + `eval/detection_metrics.py` + tests.

**Goal:** Stateless `Detector` runs the chosen-resolution Core ML model; boxes are drawn on replayed frames. WS schema for detections is formalized here.

### Task 2.1: Detector interface + stub impl

**Files:** Create `service/src/hades/detect/detector.py`, test.
**Step 1: Failing test** — `Detection` dataclass `(box_xyxy, conf, cls="person")`; `Detector` ABC `detect(frame) -> list[Detection]`; a `StubDetector` returns a fixed box. Assert shape/contract.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: detector interface + stub`.

### Task 2.2: Preprocessing (letterbox + normalize)

**Files:** Create `service/src/hades/detect/preprocess.py`, test.
**Step 1: Failing test** — letterbox+normalize a fixture frame; assert output shape/scale/padding exactly matches the Core ML export's expected input (the known footgun — test in isolation).
**Step 2-4:** red→green. **Step 5: Commit:** `feat: detector preprocessing matched to export`.

### Task 2.3: CoreMLDetector (ANE)

**Files:** Create `service/src/hades/detect/coreml_detector.py`, test (marked `@pytest.mark.ane`, manual).
**Step 1: Failing test** — load model, detect on a fixture image with a known person, assert ≥1 box conf>threshold.
**Step 2-4:** red→green using the 2.2 preprocessing. **Step 5: Commit:** `feat: coreml detector (ANE)`.

### Task 2.4: ONNX/CPU detector backend (CI determinism)

**Files:** Create `service/src/hades/detect/onnx_detector.py`, test (runs on CI).
**Step 1: Failing test** — same `Detector` interface, ONNX Runtime CPU; detect on fixture, assert boxes within a **tolerance band** (deterministic for CI where there's no ANE).
**Step 2-4:** red→green. **Step 5: Commit:** `feat: onnx/cpu detector backend for CI`.

### Task 2.5: Detection metrics harness (center-distance + per-subclass recall)

**Files:** Create `service/src/hades/eval/detection_metrics.py`, test; wire `hades-eval`.
**Step 1: Failing test** — given GT + predicted boxes, compute precision/recall by **center-distance match** (not IoU@0.5), plus **size-stratified recall** AND **per-subclass recall** keyed off hard-subclass labels (in-water/head-only, rooftop-prone, debris-occluded, in-vehicle — the acceptance-gate metric, design lines 98–100). Assert against a hand-computed fixture.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: detection metrics (center-distance, size + subclass recall)`.

### Task 2.6: WS detection message + schema

**Files:** Create `service/src/hades/ws/schema.py` (pydantic models → JSON Schema), `docs/DESIGN.md` WS section, test.
**Step 1: Failing test** — a `DetectionMessage` (frame_id, boxes, confs) round-trips serialize→deserialize; schema validates a golden fixture; rejects malformed.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: ws detection message schema + round-trip`.

### Task 2.7: Observable — boxes drawn on recorded feed

**Step 1:** Extend `replay_dump` to run the detector and draw boxes. Test on fixture → annotated frames with boxes.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: detection overlay in replay-dump (observable)`.

**Phase 2 green criterion:** `hades replay-dump --detect <clip>` draws boxes on real recorded footage (with the stock/ONNX detector — fine-tuned model lands in P2.5); `hades-eval` reports P/R + per-subclass recall; CI green on CPU path.

---

## Phase 2.5 — Model fine-tuning (ends green: a validated fine-tuned Core ML model + chosen resolution)

> **External review (green check):** `/codex` ADVERSARIAL review, scoped to `service/src/hades/train/` + export/ablation + metric-honesty (being wrong here corrupts everything downstream).

**Goal:** Replace the stock COCO detector with a domain model fine-tuned on HERIDAL+SARD — the design's detection thesis. Training runs on the **GPU cluster** (Apple Silicon dev machine can't train efficiently); only inference is local. Training is a committed reproducible script; the trained weights are a versioned artifact (e.g. release attachment / DVC / cluster path — not committed to git).

### Task 2.5.1: Dataset prep (HERIDAL + SARD → single `person` class)

**Files:** Create `service/src/hades/train/dataset.py`, test.
**Step 1: Failing test** — loader normalizes HERIDAL + SARD labels to a single `person` class in YOLO format; honors each dataset's ignore/crowd regions; a fixture sample yields the expected normalized label.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: heridal+sard dataset prep (single person class)`.

### Task 2.5.2: Augmentation pipeline

**Step 1: Failing test** — motion-blur + scale-jitter augmentation (design lines 84–85: robustness to fast camera / tiny targets) applied deterministically under seed; assert output transforms.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: motion-blur + scale-jitter augmentation`.

### Task 2.5.3: Training script (cluster) + VisDrone-pretrain ablation

**Files:** Create `service/src/hades/train/train.py` (cluster entry), `docs/plans/p2.5-training-results.md`.
**Step 1:** Reproducible training script (config-driven: epochs, img-size from the P1.5 feasible set, pretrain weights). Runs on the cluster.
**Step 2:** Train two checkpoints — {HERIDAL+SARD} and {VisDrone-pretrain → HERIDAL+SARD finetune} — and **ablate**: report HERIDAL-test recall for each (design line 102). Record in the results doc.
**Step 3: Commit:** `feat: fine-tune training script + visdrone ablation report`.

### Task 2.5.4: Re-export fine-tuned weights to Core ML

**Step 1:** Export the winning fine-tuned checkpoint to `.mlpackage` (FP16) AND to ONNX (CI path), at the candidate resolutions. Test: exported model loads and detects on a fixture (tolerance band).
**Step 2-4:** red→green. **Step 5: Commit:** `feat: export fine-tuned model to coreml + onnx`.

### Task 2.5.5: DECISION — finalize detection resolution (latency × recall)

**Step 1:** Combine P1.5 latency bound with fine-tuned per-resolution recall; pick the smallest resolution that holds ≥10fps AND meets the recall floor.
**Step 2:** Write the chosen resolution into `docs/DESIGN.md` and update `CLAUDE.md` detection line (replace "resolution TBD").
**Step 3: Commit:** `docs: finalize detection resolution (fine-tuned recall x latency)`.

### Task 2.5.6: Acceptance metrics on curated disaster footage

**Files:** extend `eval/detection_metrics.py`; `docs/plans/p2.5-acceptance.md`.
**Step 1:** Run the fine-tuned model on the **hand-curated disaster clips**; report per-subclass recall floors. (HERIDAL = sanity gate; curated footage = acceptance gate, design line 100.) Note: if real footage is thin pre-arrival (~2026-07-01), this task re-runs when the dataset lands.
**Step 2: Commit:** `docs: detection acceptance metrics on curated footage`.

**Phase 2.5 green criterion:** fine-tuned `.mlpackage` + ONNX exist and load; ablation reported; resolution finalized + propagated; per-subclass recall reported. Detector swapped from stock to fine-tuned behind the unchanged interface.

---

## Phase 3 — Track + Project + Confirm (ends green: stable IDs + world-clustered contacts)

> **External review (green check):** `/codex` ADVERSARIAL review, scoped to `service/src/hades/{track,locate,confirm}/` + `eval/fp_per_km2.py` + tests (safety-critical false-confirm logic + coordinate math).

**Goal:** Tracker (ego-motion-compensated), cheap Projector, Confirmation rule produce promoted "contacts" observable on the feed.

### Task 3.1: Tracker (ByteTrack) + ID-consistency tests
**Files:** `service/src/hades/track/tracker.py`, test.
**Step 1: Failing tests** — synthetic track scenarios: stable ID across N frames; stable ID across a short occlusion; no ID resurrection after death.
**Step 2-4:** red→green (wrap Ultralytics/ByteTrack). **Step 5: Commit:** `feat: tracker with id-consistency invariants`.

### Task 3.2: Ego-motion compensation (image-GMC primary)
**Step 1: Failing tests** — (a) on a synthetically panned sequence, GMC-compensated association keeps IDs stable where raw-IoU fails; (b) a low-feature (uniform) clip is flagged as low-confidence GMC (the water/debris failure mode).
**Step 2-4:** red→green (optical-flow/ORB GMC; telemetry pose as optional refinement input). **Step 5: Commit:** `feat: image-feature ego-motion compensation`.

### Task 3.3: Frame-gating for georeference
**Files:** `service/src/hades/locate/frame_gate.py`, test.
**Step 1: Failing tests** — good-geometry frame passes; oblique / high-angular-rate / |accel|≠1g / high-vibration frames are rejected at configured thresholds.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: frame-gating with configurable thresholds`.

### Task 3.4: Camera model + shared ray→ground math (SINGLE SOURCE OF TRUTH)
**Files:** `service/src/hades/locate/geometry.py`, `service/src/hades/locate/camera_model.py`, test.
**Step 1: Failing tests** — (a) `CameraModel` holds intrinsics `K`, distortion, **boresight `R_body_cam`** (the fixed O4 mount rotation, M10), loadable from config; (b) `ray_to_ground(pose, pixel, ground_elev) -> (lat, lon)` undistort → `K⁻¹` ray → rotate by `R_world_body · R_body_cam` → flat-earth intersect, verified against analytic truth with explicit coordinate conventions (datum, lat/lng order, image-axis origin, NED/FRD). **This ONE function is imported by both the Projector (3.5) and Fuse (4.3) — never re-implemented.**
**Step 2-4:** red→green. **Step 5: Commit:** `feat: camera model + shared ray-to-ground (single source of truth)`.

### Task 3.5: Projector (cheap per-detection ground point)
**Files:** `service/src/hades/locate/projector.py`, test.
**Step 1: Failing test** — Projector calls `geometry.ray_to_ground` per detection; emits a ground point **tagged with the 3.3 frame-gate verdict** (so 3.6 clusters only gate-passing points; gated-out detections still surface as CUE-ONLY contacts, design lines 150–151).
**Step 2-4:** red→green. **Step 5: Commit:** `feat: projector (gated per-detection ground points)`.

### Task 3.6: Confirmation rule + world-clustering
**Files:** `service/src/hades/confirm/confirmation.py`, test.
**Step 1: Failing tests** — decision truth-table (confirms after K-of-N + confidence); **false-confirm rate on adversarial flicker tracks** (test hardest); fragmented gate-passing tracks at same ground point corroborate (world-cluster); a detection NEVER suppressed from visibility — emits a **display-priority tier (contact → candidate → strong)** (M5), only the tier changes.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: confirmation rule + world-clustering + priority tier`.

### Task 3.7: False-confirmed-per-km² metric
**Files:** `service/src/hades/eval/fp_per_km2.py`, test.
**Step 1: Failing test** — integrate telemetry-swept ground area over a clip; divide confirmed false positives by km² swept (design line 96 — the mission-meaningful FP budget, distinct from 3.6's flicker rate). Assert against a fixture with known swept area + planted false confirms.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: false-confirmed-per-km2 metric`.

### Task 3.8: Observable — contacts on the feed
**Step 1:** `replay_dump` shows track IDs + contact priority tier. Test on fixture.
**Step 5: Commit:** `feat: track/contact overlay (observable)`.

**Phase 3 green criterion:** replayed feed shows stable IDs and tiered contacts; flicker false-confirm rate AND false-confirmed-per-km² measured under budget.

---

## Phase 4 — LOCALIZATION (flagship; opens with research gate)

> **External review (green check):** `/codex` ADVERSARIAL review — MANDATORY, scoped to `service/src/hades/locate/` (geometry, fuse, uncertainty, coverage) + tests. The flagship math; independent-model scrutiny is non-negotiable here.

### Task 4.0 (RESEARCH GATE): Sim + error-model design

**Not code.** Produce `docs/plans/p4-localization-research.md`: validate the geometric-sim design + sensor-error model against `localization-sota-findings` (memory note); confirm the Monte Carlo propagation approach, the coverage/NEES validation method, and the **anti-circularity rule (shared schema, not values)**. Define the sensor-error config schema. **Gate: no P4 code until this is written + reviewed.**
**Commit:** `docs: p4 localization research gate`.

### Task 4.1: Sensor-error config (shared schema) + HeadingSource
**Files:** `service/src/hades/locate/error_model.py`, `service/src/hades/locate/heading_source.py`, test.
**Step 1: Failing tests** — (a) config defines GPS σ, attitude σ, heading σ/crab, time-sync offset, σ_h; loadable/swappable; one schema consumed by both sim and MC; (b) `HeadingSource` interface (M11) — v1 impl returns the configured large heading sigma; leaves a seam for a future magnetometer/aspect-diversity impl.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: sensor-error config + heading-source interface`.

### Task 4.2: Geometric simulator
**Files:** `service/src/hades/locate/geom_sim.py`, test; wire `hades-locsim`.
**Step 1: Failing test** — given a target lat/lon + a flight path, sim emits per-frame (ground-truth pixel detection + noisy pose) so back-projection recovers ~the target within tolerance under zero noise.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: geometric localization simulator`.

### Task 4.3: Fuse — geometry-weighted average
**Files:** `service/src/hades/locate/fuse.py`, test.
**Step 1: Failing tests** — Fuse imports `geometry.ray_to_ground` (the SAME function as the Projector, D1 — not a re-implementation); multi-frame intersections average with oblique/long-range down-weighting; **stationary-target assumption** holds; a **moving target** yields non-converging (stays low CONVERGING, big radius).
**Step 2-4:** red→green. **Step 5: Commit:** `feat: geometry-weighted fusion (shared ray math)`.

### Task 4.4: Monte Carlo uncertainty → ellipse + sweep circle + class
**Files:** `service/src/hades/locate/uncertainty.py`, test.
**Step 1: Failing tests** — MC propagation → 2×2 covariance → 95% ellipse (χ²=5.991) + R95; **actionability class** (PINPOINT/SWEEP/AREA/CUE-ONLY) derived from radius; heading-limited large-sigma case yields big elongated ellipse.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: monte-carlo uncertainty + actionability class`.

### Task 4.5: Coverage validation (anti-circular)
**Files:** `service/src/hades/eval/coverage.py`, test.
**Step 1: Failing tests** — matched sim/MC noise → ~95% coverage; **mismatched** noise → coverage degrades (proves it's not tautological), with an **explicit time-sync-offset mismatch case** (M7 — the design's named dominant failure: sim injects a time-sync offset the MC doesn't model, coverage must visibly drop). Also a biased/heavy-tailed case. Optional NEES if cheap.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: coverage validation incl. time-sync mismatch`.

### Task 4.6: Taskable contact record + WS message
**Files:** extend `ws/schema.py`, test.
**Step 1: Failing test** — full contact record (track_id, coord, sweep_radius+class, **display-priority tier contact/candidate/strong** (M5), detection_conf AND localization_conf, CONVERGING/STABLE, snapshot+delta, age, clearance_state, source, heading_limited, cluster) round-trips + schema-validates.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: taskable contact record schema`.

### Task 4.7: Service loop + WS emit (ASSEMBLE THE PIPELINE)
**Files:** `service/src/hades/service/loop.py` (wire `hades-service`), test.
**Step 1: Failing test** — the loop pulls from FrameSource + TelemetrySource → Detector → Tracker → Projector → Confirmation → (Fuse on confirmed) and emits `DetectionMessage` + `ContactRecord` JSON on a localhost WS channel AND JPEG frames on the binary channel; a Python WS client receives well-formed messages aligned by `frame_id` when run against the recorded fixture. (D2 — this is where the real pipeline is first assembled; without it, P2–P4 are observable only via the CLI.)
**Step 2-4:** red→green. **Step 5: Commit:** `feat: service loop assembles pipeline + emits over ws`.

### Task 4.8: Detector→localizer glue test (M4)
**Files:** `service/tests/integration/test_detect_to_locate.py`.
**Step 1: Failing test** — feed a real `Detection` (from the detector path) through Projector/Fuse and assert the coordinate lands correctly: this tests the SEAM (does a `box_xyxy` pixel arrive at the projector in the right axis convention/origin?), distinct from the in-isolation Projector unit test and the full E2E. The named wiring-bug guard.
**Step 2-4:** red→green. **Step 5: Commit:** `test: detector->localizer coordinate seam`.

### Task 4.9 (FLAGSHIP CLOSE): meter-error report
**Step 1:** `hades-locsim` reports median/mean/p90/max meter-error stratified by slant range + pitch, + coverage. Test on sim.
**Step 5: Commit:** `feat: localization meter-error report (flagship metric)`.

**Phase 4 green criterion:** `hades-locsim` reports honest meter-error + validated coverage; the **assembled service** runs end-to-end on the recorded feed and emits contact records over WS (observable via a WS client, not just the CLI).

---

## Phase 5 — COORDINATOR UI (flagship; opens with visual-design research gate)

> **External review (green check):** gstack **`/design-review`** (visual/looks-AI audit) + **`/qa`** (drive the real UI, find/fix flow bugs). NOT Codex — it can't see the rendered UI. This is already wired into Task 5.12.

> **🎨 DESIGN TOOLING — use the RIGHT tool per job, do NOT overdo it.** (See memory
> `ui-design-tooling`.) Availability is not a reason to invoke a tool — evaluate per
> scenario. Sequence is **JUDGMENT → CONSTRAINED GENERATION → VERIFY**; tools never
> invent the aesthetic. Tool roles:
> - **frontend-design + impeccable (skills)** = judgment: decide aesthetic/hierarchy/
>   anti-AI-slop rules. Run at the 5.0 gate + design-review close (5.12).
> - **Web Design Guidelines (Vercel skill)** = audit/cross-check decisions at the gate
>   and review — not a generator.
> - **shadcn UI MCP** = accessible primitives (dialog/select/table) where a solid base
>   is needed; SKIP for bespoke viz (map overlays, video canvas).
> - **Magic MCP (21st.dev)** = generate/refine specific components CONSTRAINED by the
>   already-decided design system (feed it tokens + rules); SKIP for trivial/bespoke.
> - **Chrome DevTools MCP** = verify the running UI (measure spacing/contrast, screenshot,
>   catch AI-look tells) at component-done + phase-green; not mid-trivial-implementation.
> **At the P5 session start: verify shadcn MCP, Chrome DevTools MCP, and the Web Design
> Guidelines skill are actually connected** (user installs them before P5); if a tool
> isn't present, proceed with the judgment skills + Magic and note the gap — don't block.

### Task 5.0 (RESEARCH GATE): Visual design pass — DECIDE the system

**Not component code. This is where "doesn't look AI-generated" is won — it's a judgment problem, not a generation one.**
**Step 1 (judgment):** Run **frontend-design + impeccable** to decide the mission-control aesthetic — visual hierarchy, density, type scale, color system, spacing rhythm, motion principles, and an explicit **anti-AI-slop ruleset** (no default shadows/gradients, tabular numerals, intentional empty/loading/error states, consistent interaction grammar). Cross-check against the **Web Design Guidelines** skill if connected.
**Step 2 (artifacts):** Produce `docs/DESIGN-SYSTEM.md` — aesthetic spec + design tokens (color/space/type/radius/motion) + the anti-slop rules + reference mockups for map / video / list / detail-panel / status-bar.
**Step 3 (foundation choice):** Decide which components ride on **shadcn primitives** (accessible base: dialogs, selects, the survivor table) vs. which are **bespoke** (map overlays, video canvas, coverage layer) — record the split in DESIGN-SYSTEM.md so later tasks know which tool to reach for.
**Step 4 (adversarial review):** Per the auto-adversarial rule, run a subagent panel (design-skeptic / mission-control-domain / AI-slop-detector / simplicity) against the proposed system before locking it.
**Gate: no UI component code until DESIGN-SYSTEM.md exists and the system is locked.**
**Commit label (no commit):** `docs: design-system + visual-design pass (p5 gate)`.

### Task 5.1: Two-channel mock WS + Zustand contact store
**Files:** `ui/src/mock/mock-ws.ts`, `ui/src/store/contacts.ts`, test.
**Step 1: Failing test** — mock WS replays BOTH channels (canned `ContactRecord` JSON **and** canned JPEG frames on the binary channel, so the video panel has something to paint — review fix); store ingests records outside React render. (Selection state is NOT here — it's 5.2, per D4: the store is pure data ingestion.)
**Step 2-4:** red→green. **Step 5: Commit:** `feat: two-channel mock-ws + contact store`.

### Task 5.2: Global bidirectional selection spine (BUILT FIRST — the architectural spine)
**Files:** `ui/src/store/selection.ts`, test.
**Step 1: Failing tests** — selection state is global and owned HERE; selecting a Contact anywhere selects everywhere; hover-preview ≠ click-commit; selection survives data updates/re-sort.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: global bidirectional selection spine`.

### Task 5.3: Layout shell + status bar
**Step 1: Playwright test** — fixed grid (map primary, list rail, video docked); always-on system-health strip (link/telemetry/GPS state).
**Step 2-4:** red→green. **Step 5: Commit:** `feat: layout shell + status bar`.

### Task 5.4: Prioritized list
**Tooling:** shadcn MCP for the accessible table/select primitives; Magic MCP to refine the row/cell presentation CONSTRAINED by DESIGN-SYSTEM.md tokens (tabular numerals, status encoding). Verify density/legibility with Chrome DevTools MCP at done.
**Step 1: Playwright tests** — non-negotiable columns (ID, class, both confidences separate, clearance, age, CONVERGING/STABLE, heading-limited); sortable/filterable; tabular numerals; row↔selection linked; cleared contacts demote.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: prioritized survivor list`.

> **Map (5.5a–d) + Video (5.6) tooling note:** these are BESPOKE viz (MapLibre overlays, canvas, coverage layer). **Skip shadcn/Magic** here — they don't fit custom viz and would add AI-look. Build to the DESIGN-SYSTEM tokens by hand; use Chrome DevTools MCP to verify spacing/contrast/overlay alignment against the running map.

### Task 5.5a: Map — basemap + pins
**Step 1: Playwright tests** — offline PMTiles basemap renders; pins encode class+clearance+confidence+priority-tier; pin↔selection linked.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: map basemap + contact pins`.

### Task 5.5b: Map — sweep/area radius + eased pin motion
**Step 1: Playwright tests** — SWEEP/AREA drawn at true sweep radius (not a point); **eased pin motion, never teleport** when a coordinate refines; selected pin stays framed.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: sweep-radius rendering + eased pin motion`.

### Task 5.5c: Map — drone track + camera footprint + searched-area coverage (flagship-grade)
**Step 1: Playwright tests** — drone position+heading+track; live camera footprint; **accumulated searched-area coverage layer** (the design's "most important non-pin layer"); operator reference markers (M13).
**Step 2-4:** red→green. **Step 5: Commit:** `feat: drone track + footprint + searched-area coverage`.

### Task 5.5d: Map — clustering + layer toggles
**Step 1: Playwright tests** — pin clustering at low zoom; filter/toggle by clearance state + class; legible under dozens of contacts.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: map clustering + layer toggles`.

### Task 5.6: Video panel + overlays
**Step 1: Playwright tests** — frames from the mock's binary channel painted to canvas; box overlay aligned by frame_id; rewind/pause buffer; snapshot-to-contact; manual contact creation (AI-miss backstop); loud LINK-LOST (frozen ≠ live); fresh vs coasting overlay distinct.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: video panel with overlays + manual annotation`.

### Task 5.7a: Core loop — one-click clearance + dispatch snapshot
**Step 1: Playwright tests** — one-click clearance transitions, reversible (life-safety undo); dispatch snapshots coordinate; later motion → delta-from-dispatched alert; track ID always visible.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: clearance loop + dispatch snapshot + delta`.

### Task 5.7b: Alert tiering + ack + burst coalescing (alarm-fatigue subsystem)
**Step 1: Playwright tests** — loud alert only for PINPOINT/SWEEP high-confidence; CUE-ONLY posts silently; explicit per-contact ack (unack count never silently resets); bursts coalesce ("3 new contacts"); no repeat-chime per track.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: tiered alerts + ack + burst coalescing`.

### Task 5.7c: Degrade-visibly trust states (M12)
**Step 1: Playwright tests** — inject stale telemetry on the mock → **localization-confidence visibly collapses** and the affected contact flags heading-limited/stale (dynamic coupling, not just a static health strip); coordinates render radio-speakable, single-format, datum-explicit; never-hidden fields verified present.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: degrade-visibly trust states`.

### Task 5.8: Mission log (append-only)
**Step 1: Playwright test** — every detection/state-change/snapshot/note/link-event appends to a timestamped log view.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: append-only mission log`.

### Task 5.9: Wire UI to the real Python service
**Files:** Electron spawns the `hades-service` (assembled in Task 4.7); replace mock WS with the real localhost WS (both channels already emitted by 4.7).
**Step 1: THE mandatory E2E test** — replay recorded fixture → real service → real WS → headless UI → assert a survivor pin lands at the correct map coordinate with expected uncertainty (the coordinate-convention guard). (Thin now, because 4.7 already built the service loop — D2.)
**Step 2-4:** red→green. **Step 5: Commit:** `feat: end-to-end recorded-feed → UI pin (e2e)`.

### Task 5.10: Operator-promote → on-demand Fuse (M6 — the human-as-confirmer path)
**Files:** UI promote action → WS command; service triggers Fuse+Quantify on the named contact.
**Step 1: Failing test** — operator hovers/promotes a contact → a WS command triggers Fuse on that contact (even if not auto-confirmed) → a refined ContactRecord returns. Exercises the whole rationale for the Projector/Fuse split.
**Step 2-4:** red→green. **Step 5: Commit:** `feat: operator-promote triggers on-demand localization`.

### Task 5.11: Glass-to-glass latency budget (M3)
**Files:** `service/` + `ui/` timestamp instrumentation, `docs/plans/p5-latency-budget.md`.
**Step 1:** Instrument timestamps at decode / inference / georeference / render boundaries; measure end-to-end socket→painted-overlay+pin against the **≤120ms budget** with the per-stage sub-budget (distinct from the P1.5 throughput gate — both must hold).
**Step 2:** Record results; assert the budget in a (manual, on-device) test. **Step 5: Commit:** `test: glass-to-glass latency budget measured`.

### Task 5.12 (FLAGSHIP CLOSE): design review + AI-slop audit + Playwright gate
**Step 1 (verify the running UI):** Use **Chrome DevTools MCP** to drive the real app — screenshot each key view, measure spacing rhythm / contrast / type scale against DESIGN-SYSTEM.md tokens, and catch the AI-look tells (inconsistent spacing, default shadows/gradients, generic component defaults, non-tabular numerals).
**Step 2 (judgment audit):** Run **impeccable + frontend-design** (and **Web Design Guidelines** if connected) as a design review against `docs/DESIGN-SYSTEM.md`; fix what they flag. Capture one reference screenshot per key view.
**Step 3 (adversarial close):** Per the auto-adversarial rule, run a subagent panel including an explicit **"does this look AI-generated?"** lens; fold in fixes.
**Step 4:** Confirm the functional Playwright happy-path suite is green.
**Step 5: Commit label (no commit):** `test: ui design review + ai-slop audit + playwright green`.

**Phase 5 green criterion:** the full app replays a recorded feed end-to-end, plots survivors with honest uncertainty, operator-promote triggers on-demand localization, both real-time gates (≥10fps throughput AND ≤120ms latency) hold, passes the design review + functional Playwright suite, and the E2E coordinate test is green.

---

## Phase 6 — Demo website (static, canned-mission replay)

> **External review (green check):** gstack **`/qa`** on the deployed/served static site (verify the canned mission plays + flows work in a plain browser). No Codex pass — it reuses P5's already-reviewed UI.

**Goal:** A deployable static website that replays a pre-recorded mission through the SAME React UI built in P5 — for GitHub credibility and "click this link to see it work" demo-ability. No Electron, no Python backend, no in-browser inference. The UI is fed by a baked mission-data file instead of a live WS service. Reuses the P5 UI + the mock-WS data path; this is packaging + data-baking, not new UI.

**Why it's cheap:** P5's UI already runs against a mock-WS data source (Task 5.1) for tests. The demo is that path promoted to a polished, browser-hosted product. The only genuinely new work is (a) recording a real mission's output to a static file, (b) a browser data-source that replays it, (c) static deploy.

### Task 6.1: Bake a mission-data file from a real run

**Files:** `service/src/hades/cli/record_mission.py`, output `web-demo/public/mission.json` (+ frame thumbnails).
**Step 1: Failing test** — run the full P4-assembled service against a recorded fixture and serialize the emitted stream (timestamped ContactRecords + frame references) to a static `mission.json` that conforms to the WS schema. Assert it round-trips through the same schema the UI consumes.
**Step 2-4:** red→green. **Step 5: Commit label (no commit):** `feat: record-mission to static data file`.

### Task 6.2: Browser data source (replays the baked file)

**Files:** `ui/src/data/file-mission-source.ts`, test.
**Step 1: Failing test** — a data source that reads `mission.json` and emits the same record/frame stream shape as the mock-WS and real-WS sources, on a timer matching original timestamps (so it *plays* like a live mission). Same interface the UI store already consumes — no UI changes.
**Step 2-4:** red→green. **Step 5: Commit label (no commit):** `feat: browser file-mission data source`.

### Task 6.3: Web build target (no Electron)

**Tooling note:** the demo reuses the SAME UI + DESIGN-SYSTEM.md from P5 — no new design work, no re-deciding the aesthetic. The only design-tool use here is **Chrome DevTools MCP to verify it looks right in a PLAIN browser** (not Electron) across the demo's target viewports, since that's the new runtime.
**Files:** `ui/vite.config` web target, an entry that selects the file-mission source when running as a plain website.
**Step 1: Failing test (Playwright, plain browser — not Electron)** — `pnpm build:web` produces a static bundle; opening it in a browser loads the demo, plays the canned mission, and the map/list/video + selection spine all work against the baked data.
**Step 2-4:** red→green. Gracefully degrade the live-only affordances (no real LINK-LOST, manual-annotation can be view-only or disabled with a clear "demo mode" banner). **Step 5: Commit label (no commit):** `feat: static web build target (demo mode)`.

### Task 6.4: Deploy + GitHub polish

**Step 1:** Static-host the build (GitHub Pages / Netlify / Vercel — all free, no backend). Add a "demo mode" banner clarifying it's a canned replay, not live. Link it from the README with a screenshot/GIF.
**Step 2: Commit label (no commit):** `docs: deploy demo website + readme link`.
NOTE: deploy + README are the one place commits/push are genuinely needed to publish — flag to the user and let THEM do the commit/deploy (per the no-commit rule, you don't commit; you prepare everything and hand off the publish step).

**Phase 6 green criterion:** a static website builds and runs in a plain browser, replays a real canned mission through the full coordinator UI, clearly labeled demo mode; ready for the user to deploy + link from GitHub.

> **STOP after P6 — do NOT roll into P7.** P7 (documentation) is the capstone and the user initiates it explicitly. When P6 is green, end the session and report; wait for the user to say to start documentation.

---

## Phase 7 — Documentation & presentation (capstone; runs LAST, consumes real results)

> **⚠️ BOUNDARY — do NOT auto-start P7 after P6.** P7 begins ONLY when the user explicitly says to continue/start documentation. P6 ends; stop. (User initiates P7 manually.)

> **Skills/tools for P7 (right tool per job, don't overdo it):**
> - **frontend-design + impeccable** = the README layout/IA + in-app Docs page craft (a README is a *designed artifact*, not just prose — fights "generic GitHub readme" the same way they fight UI slop). Primary skills here.
> - **gstack `/diagram`** = the pipeline architecture figure (module map → clean editable diagram) for README/docs.
> - **Wolfram** (user-run) = the 3D/data hero visuals only (error surface, geospatial ellipses) — NOT box-and-arrow diagrams.
> - **gstack `/document-generate`** = generation/review pass (also the green-check review tool).
> - **gstack `/make-pdf`** = optional publication-quality PDF artifact (Task 7.7).
> - **NOT Codex** (reviews code correctness, says nothing about docs prose/layout/figures — wrong tool). **NOT** design-html/clone-website/design-shotgun (the docs page reuses the existing design system) or document-release (that's changelogs).

> **External review (green check):** gstack **`/document-generate`** + an adversarial subagent panel with a **"is any metric filler / is any claim unsupported by a real number / does any prose read AI-generated"** lens. Verify every figure traces to a real artifact from a prior phase.

**Goal:** Produce genuinely high-quality, thoughtful documentation of the whole system — a polished README + an in-app docs page — with real metrics, good-looking graphs (incl. Wolfram-rendered hero visuals), and qualitative bounding-box/map showcases. High-school-level clarity but high-craft and information-dense. **No em dashes in the generated docs.** Every number/figure must trace to a real artifact produced in P2.5/P3/P4/P5 — no invented results.

**Why it's last:** it documents the *finished, measured* system — real detector metrics (P2.5), real localization error/coverage (P4), real FPS/latency (P1.5/P5), real annotated frames + map screenshots (P5/P6). Written earlier, it would document wishes.

### Task 7.0 (CONTENT GATE): Inventory real artifacts → outline
**Not prose.** Collect every real result that exists: detection metrics (`docs/plans/p2.5-*.md`, `eval/`), localization meter-error + coverage (`hades-locsim` outputs), FPS/latency (`p1_5-latency-spike`, `p5-latency-budget`), and candidate frames/screenshots. Produce `docs/documentation/OUTLINE.md` mapping each planned section/figure → the real artifact it draws from. **Gate: no figure or claim that can't name its source artifact.** If a needed artifact doesn't exist, that's a gap to fill, not a number to invent.
**Commit label (no commit):** `docs: documentation outline + artifact inventory`.

### Task 7.1: Metrics export (the data behind every graph)
**Files:** `service/src/hades/cli/export_doc_data.py` → `docs/documentation/data/*.{csv,json}`, test.
**Step 1: Failing test** — export the four metric families to flat data files that the graph code (Python AND Wolfram) reads: **(a) Detection** — PR curve points, precision/recall/mAP, size-stratified + per-subclass recall, operating-point confusion; **(b) Localization** — meter-error CDF, error by slant-range & pitch, ellipse params, coverage-calibration; **(c) Real-time** — FPS per resolution {640,960,1280}, glass-to-glass latency by stage; **(d)** references to the qualitative frames. Assert each file is non-empty and matches the source artifact values.
**Step 2-4:** red→green. **Step 5: Commit label (no commit):** `feat: doc-data export for all four metric families`.

### Task 7.2: Python graphs (reproducible, in-repo) + architecture diagram
**Files:** `docs/documentation/figures/make_figures.py` → `docs/documentation/figures/*.png`, test.
**Step 1:** Generate the routine charts from 7.1 data (PR curve, per-subclass recall bars, meter-error CDF, error-by-geometry, FPS bars, latency breakdown, coverage-calibration). Styled to the project palette (consistent, no default-matplotlib look). Test: every expected figure file is produced and non-empty.
**Step 2 (architecture figure):** Use gstack **`/diagram`** to turn the pipeline module map (`FrameSource → Detector → … → UI`) into a clean editable architecture diagram for the README/docs (structure/boxes-and-arrows — Wolfram is for data/3D, not this).
**Step 3-4:** red→green. **Step 5: Commit label (no commit):** `feat: python documentation figures + architecture diagram`.

### Task 7.3: Wolfram hero visuals (code you run, I don't)
**Files:** `docs/documentation/wolfram/*.wl` (Wolfram Language scripts that read 7.1's data files), `docs/documentation/wolfram/README.md` (run instructions).
**Step 1:** Write ready-to-run **Wolfram Language** scripts for the 2-3 showpiece renders where Wolfram beats matplotlib — e.g. a **3D localization-error surface** (error vs slant-range vs pitch), a **geospatial survivor-map plot with uncertainty ellipses**, and an **error-ellipse / coverage 3D visual**. Scripts read the exported `data/*.csv` so they reflect real numbers, and `Export[]` to `figures/`.
**Step 2 (HANDOFF — user runs):** This is the one place the user runs the tool: you generate the `.wl` code + data, the user runs it in their local Wolfram, drops the resulting images into `figures/`. Flag this handoff explicitly; do not assume Wolfram in the build.
**Step 3: Commit label (no commit):** `feat: wolfram hero-visual scripts (user-run)`.

### Task 7.4: Qualitative showcase frames
**Files:** `service/src/hades/cli/make_showcase.py` → `docs/documentation/figures/showcase/*.png`.
**Step 1:** Render real annotated frames: **bounding boxes on real footage**, the **survivor map with pins + uncertainty ellipses**, and a **stock-vs-fine-tuned before/after** on the same frame (shows the P2.5 win). Pull from real recorded fixtures, not synthetic. Test: showcase images produced.
**Step 2-4:** red→green. **Step 5: Commit label (no commit):** `feat: qualitative showcase frames (boxes + map + before/after)`.

### Task 7.5: The README (single markdown source)
**Files:** `README.md` (root), `docs/documentation/assets/` (logo, tool badges).
**Step 1:** Author the README using the **judgment skills (frontend-design/impeccable for layout/IA, not just prose)**. Required elements:
- **HADES logo at the top** (`HADES_logo.png` already in project root — move/copy to assets).
- **A "Built with" section: colored boxes per tool, each with the tool's logo + the exact version we used** (read versions from `pyproject.toml` / `package.json` / lockfiles — real versions, not guessed).
- The four metric families with their figures (7.2 Python + 7.3 Wolfram + 7.4 showcase).
- System overview (the pipeline module map), honest-accuracy framing, the demo-site link (from P6).
- **No em dashes.** High-school-readable but information-dense and high-craft; no filler metrics.
**Step 2:** Adversarial review (filler/AI-prose/unsupported-claim lens); fix. **Step 3: Commit label (no commit):** `docs: high-craft README with metrics, figures, tool badges`.

### Task 7.6: In-app docs page (one source, rendered in all three surfaces)
**Files:** `ui/src/docs/` (markdown source + a `Docs` route/panel component), test.
**Step 1: Failing Playwright test** — a **Docs** route/panel renders the shared markdown (same content family as the README, adapted to look good in-app: styled to DESIGN-SYSTEM.md, the logo, tool badges, key figures). Because the Electron app, web app, and demo site all share the React UI, the Docs page appears in **all three** from one source. Assert the Docs route renders the logo + at least one metric figure + the tool list.
**Step 2-4:** red→green; verify in a plain browser (Chrome DevTools MCP) that it looks good, not just renders. **Step 5: Commit label (no commit):** `feat: in-app docs page (shared source, all three surfaces)`.

### Task 7.7 (OPTIONAL): Publication-quality PDF
**Step 1:** Use gstack **`/make-pdf`** on the documentation markdown to produce a polished PDF artifact (hand-it-to-someone / capstone-submission format). Reuses the content from 7.5 — no new writing. Optional: never blocks the phase green criterion.
**Step 2: Commit label (no commit):** `docs: publication-quality pdf of documentation`.

**Phase 7 green criterion:** README renders with logo + versioned tool badges + all four metric families' figures (Python + Wolfram + showcase) + demo link, no em dashes, every figure traceable to a real artifact; in-app Docs page renders the same content well across app/web/demo; adversarial review confirms no filler and no AI-prose tells. Wolfram scripts handed to the user to run.

---

## Cross-phase notes
- **Determinism:** seed all RNG; MC asserted exact; detector eval on CPU/ONNX in CI with tolerance bands; async-WS timing tests quarantined.
- **Real dataset (~2026-07-01):** when it arrives, add it as a `FileFrameSource`/`SrtFileSource` fixture and re-run P2.5 detection acceptance (per-subclass recall) + P4 localization checks on real data. Capture one raw stream as the golden fixture.
- **Each phase ends with a working `replay-dump`/service/app state observable against the recorded feed.** Never leave a phase red.
- **Deferred to v1.x (explicit, not dropped):** flight recorder (M8 — tied to the live build, which is stubbed in v1); PyInstaller bundling of the Python child (M9 — v1 spawns local dev Python); plus all v1.x items in the design doc's OUT OF SCOPE section.
- **Training environment:** P2.5 fine-tuning runs on the GPU cluster (details filled at the task); inference is local Core ML. Trained weights are a versioned artifact, not committed to git.
