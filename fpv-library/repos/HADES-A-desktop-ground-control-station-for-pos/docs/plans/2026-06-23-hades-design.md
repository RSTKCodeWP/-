# HADES — Design Document (v1)

**Status:** validated via section-by-section brainstorming + multi-agent adversarial
review. **Date:** 2026-06-23. **Scope:** v1 design. Visual design is a separate later
pass. See `CLAUDE.md` for project rules; `docs/plans/` for plans.

## Goal

A desktop ground-control station for post-hurricane search-and-rescue: ingest a live
video feed from an FPV drone over a digital video link, run real-time human detection
on the frames, compute real-world survivor coordinates from each detection, and present
detections plus a live survivor map in a professional coordinator UI. Quality bar:
impressive and genuinely usable — between a demo and a fielded tool.

## Target hardware & data paths (fixed reality)

- **Drone:** Speedy Bee F405 (Betaflight), DJI O4 Air Unit Lite (fixed-mount camera,
  no gimbal), ELRS Nano RX, generic HGLRC M10-class GPS.
- **Video to ground station:** O4 → DJI goggles → HDMI → USB UVC capture. O4 burns an
  OSD and writes a `.srt`/`.osd` telemetry sidecar to the goggles' microSD.
- **Telemetry to ground station:** ELRS radio's USB-C → serial → CRSF (low-rate live;
  full-rate blackbox after landing). **Video and telemetry are on separate radios.**
- **Compute:** Apple Silicon MacBook (M4/M5), macOS. No CUDA — inference via Core ML.

## Architecture (pipeline)

```
FrameSource → Detector → Tracker → Projector → Confirmation → Fuse+Quantify → UI
  (frames)   (boxes)   (tracks)  (per-det     (contacts,    (fused coord +
                                  ground pt)   world-clustered) uncertainty)
```

The Localizer is split to break a dependency cycle (Confirmation needs world position
to cluster, but full fusion should run only on confirmed contacts): a cheap **Projector**
runs a single ground projection per detection *before* Confirmation so it can cluster in
world space; the expensive **Fuse+Quantify** stage (multi-frame averaging + Monte Carlo
uncertainty) runs only on confirmed contacts and on any contact the operator promotes.

Two processes over localhost WebSocket (two channels: binary JPEG frames + JSON
detections/telemetry, aligned by `frame_id`):
- **Detection/localization service (Python):** Ultralytics YOLO, PyAV ingest, Core ML
  inference, georeferencing, fusion.
- **UI shell (Electron + React + TypeScript + Vite):** Tailwind + shadcn/ui, Zustand,
  MapLibre GL. Electron (not Tauri) so the Playwright path is paved and the video path
  uses Chromium. Electron supervises the Python child (PyInstaller-bundled).

Detailed module boundaries and the WS message schema are defined in `docs/DESIGN.md`.

---

## Pillar 1 — DETECTION

**Decomposition: stateless detector in a staged pipeline** (the standard, swappable
decomposition — detector and tracker are separate near-universally).

- **Detector** — stateless `frame → Detection[]` (box, class=`person`, confidence).
  Swappable weights behind a fixed interface (YOLO11s → YOLO26/RT-DETR/thermal). Runs
  ≥10fps. Knows nothing about time or "survivors."
- **Tracker** — detector-agnostic (ByteTrack default). Persistent IDs; bridges 10fps
  detection → 30fps display by predicting positions between inferences. **Ego-motion
  compensation is mandatory** — raw-pixel IoU association collapses on a fast-yawing
  drone at 10fps. **Image-feature GMC (BoT-SORT / optical flow) is primary**; low-rate
  telemetry pose is an optional refinement (telemetry is only a few Hz, so it can't drive
  per-frame homography alone). Known weakness to test: image-GMC degrades over water /
  uniform debris with sparse features — frame-gating must catch these. Interpolated
  overlays render visually distinct from detected ones.
- **Projector** — cheap single ground projection per detection (no Monte Carlo), so
  Confirmation can cluster in world space. Reuses the per-frame ray-to-ground math.
- **Confirmation** — a *rule on the track object* (not a separate framework): persistence
  (seen in N of last M) + accumulated confidence + **world-location clustering** (so
  fragmented tracks at the same ground point corroborate). **Confirmation NEVER gates
  visibility** — every detection above a low threshold surfaces immediately as a faint
  "contact"; persistence/confidence only promote display priority (contact → candidate →
  strong). This preserves recall-first: the one-frame glimpse through a debris gap still
  appears.
- **Fuse+Quantify (Localizer)** — multi-frame fusion + Monte Carlo uncertainty, runs on
  confirmed survivors **and on any contact the operator hovers/promotes** (the human is
  the confirmer; the machine is a contact generator).

**Ingestion behavior under stress:**
- Frame drops / corrupt frames → caught per-frame, skipped, never crash; corrupt-but-
  valid frames pass through.
- Latency spikes → drop-to-latest single-slot buffer; never accumulate backlog.
- Fast camera / motion blur / changing altitude+angle → (a) train with motion blur +
  scale jitter; (b) tracker absorbs transient misses; (c) pose changes feed forward to
  the Localizer.
- Resolution changes mid-stream → never cache dimensions; re-read per frame.

**Quality measurement (defined before model work):**
- *Detector surface (per-frame):* match by **center-distance (or IoU@0.25)**, not
  mAP@0.5 — tiny-object IoU is dominated by 1–2px jitter. mAP@0.5 kept only as a
  HERIDAL-comparability dev proxy. Report **size-stratified recall**. Target: credibly
  in-class vs published SOTA (HERIDAL ≈0.83 mAP@0.5).
- *System surface (temporal):* per-survivor recall + **false confirmed survivors per km²
  searched** (telemetry-swept area — mission-meaningful, altitude-invariant; NOT per-
  minute). Doctrine: **recall-first, bounded FP** — maximize recall subject to the km²
  cap. Report 2–3 points on the recall/FP curve (one tuned operating point shipped).
- *Validation data:* **hand-curated real disaster footage** with presence-interval +
  hard-subclass labels (in-water/head-only, rooftop-prone, debris-occluded, in-vehicle),
  reporting **per-subclass recall floors**. HERIDAL = pretraining/sanity gate, NOT the
  acceptance gate (wilderness ≠ flood domain). VisDrone → pretraining only, then fine-
  tune on HERIDAL+SARD; ablate and report.

**Model (v1):** fine-tune YOLO11s on HERIDAL+SARD, single `person` class. Export to Core
ML `.mlpackage`, FP16, ComputeUnits.all. **Input resolution = 960 (RESOLVED in P2.5).**
P1.5 showed all of {640,960,1280} clear ≥10fps (latency does not bind). P2.5 then measured
held-out HERIDAL-test recall per resolution on the fine-tuned model: recall **peaks at 960
(0.510), ties 1280 within noise (0.511) but with better precision (FP 442 vs 580), and
DEGRADES at 1920** (untrained scale → FP explosion). So 960 is both the recall-best and the
smaller choice — the design's earlier "smallest that meets the floor" and the spike's
"largest recall wants" converge on 960. (1280 was the small-target aspiration but bought no
recall here.) SAHI tiling is an offline high-recall mode for metrics only — NOT the live path.

---

## Pillar 2 — LOCALIZATION (flagship)

**Literature survey (COMPLETED before this design).** A multi-stream SOTA survey on
pixel→ground geolocation, multi-frame fusion + uncertainty, and fixed-camera attitude
estimation was run and is the basis for the decisions below; full findings are recorded
in the project memory note `localization-sota-findings`. The decisions here are survey
*conclusions*, not assertions. **Gate: no localization implementation begins until this
survey is reflected in the design** — satisfied.

**SOTA framing (from the survey):** the projection math is settled/standard
(inverse-collinearity single ray). The flagship is **bias-aware fusion + honest
uncertainty**. Critically, **this system is heading-limited, not algorithm-limited** —
the FPV quad has no usable magnetometer, so heading comes from gyro drift + GPS course-
over-ground (which ≠ true heading; wind crab 5–40°). Heading error → lateral ground
error ≈ 1.75 m / 100 m range / degree. Pitch/roll are fine (~1–2°); boresight cheap
(~0.1°). **Attack heading or nothing.**

**v1 method (lean + honest):**
- Per-frame: undistort pixel → `K⁻¹` camera ray → rotate by camera world attitude
  (`R_world_body · R_body_cam`, boresight-calibrated) → intersect **flat-earth plane at
  operator-set ground elevation** (σ_h sampled in Monte Carlo) → lat/lon.
- **Fusion:** geometry-weighted **average** of per-frame ground intersections for a
  stationary survivor (oblique/long-range frames down-weighted). NOT a recursive bias
  filter, NOT triangulation in v1.
  - **Load-bearing assumption — stationary target.** The average assumes the survivor
    doesn't move between frames. Survivors in moving water / drifting / walking violate
    this; fusion then smears across positions. **v1 failure mode (accepted, not hidden):**
    a moving target shows a non-converging estimate → stays low CONVERGING, larger radius,
    never promoted to a tight PINPOINT. Moving-target tracking is explicitly v1.x.
- **Heading:** honestly **large heading sigma (15–30°)**, justified by no-compass +
  crab. *Not estimated* — heading bias is systematic and unobservable on a single
  straight pass; estimating it as a free filter state produces a confident wrong answer
  ("smug filter"). Behind a `HeadingSource` interface for later upgrade.
- **Uncertainty:** **Monte Carlo** propagation of all input sigmas → 2×2 ground
  covariance. Expect it elongated down-range.
- **Frame gating:** hard-gate bad geometry / high angular-rate / |accel|≠1g / high-
  vibration frames *out of the fused estimate*; still surface those detections as
  CUE-ONLY contacts with a large radius.

**Output — taskable contact record** (not a bare coordinate):
`{ track_id, dispatch-grade coordinate, sweep_radius + actionability_class
(PINPOINT/SWEEP/AREA/CUE-ONLY), detection_confidence AND localization_confidence
(separate axes), CONVERGING/STABLE flag, snapshot-on-dispatch coordinate +
delta-from-dispatched event, time_last_seen/age, clearance_state
(NEW/ASSIGNED/EN-ROUTE/SEARCHED-NEGATIVE/FOUND), source drone/pass/frame-range,
heading_limited flag, association/cluster info }`. The elongated 95% ellipse is an
expert-detail layer; the primary act-on object is **sweep circle + actionability class**.

**Validation:**
- **Geometric simulator (primary):** known camera pose + target coords, inject
  configured sensor noise, check recovered meter-error + **empirical 95% coverage**.
  NOT photorealistic — feeds ground-truth detections, tests geometry only.
- **Anti-circularity:** sim and Monte Carlo share the config **schema, never the
  values** — tests deliberately mismatch them (biased/heavy-tailed/time-sync errors the
  MC doesn't model) and measure coverage degradation. Real test flights with GPS-tagged
  targets, **held out** from noise-tuning, give the un-circular real-world number.
- Sensor-error params (GPS σ, attitude σ, heading σ/crab, time-sync offset, σ_h) =
  explicit swappable config, shared by sim + Monte Carlo.

**Honest accuracy claim:** ~1.5–5 m near-nadir/low; ~10 m nominal; 20–100+ m oblique/
long/windy/single-pass. Reported, never hidden. Fails **loud** (big circle, CUE-ONLY)
rather than a confident wrong pin.

**Deferred to v1.x ("shrink the ellipse, defensibly"):** DEM ray-march; Schmidt-Kalman
*consider*-state heading bias gated on observed aspect diversity; recursive information
filter; camera↔IMU time-offset estimation; flight-tuned noise calibration.

---

## Pillar 3 — TESTABILITY

**Governing rule:** *test what can be numerically wrong (the math) and what touches
real data we have (recorded clips); defer what only hardware can verify.*

- **Abstractions:** `FrameSource` + `TelemetrySource` interfaces. v1 ships **recorded/
  replay impls** (synthetic + **real recorded O4 video + `.srt`/blackbox** — real dataset
  arriving ~2026-07-01, must replay robustly). **Live capture impls stubbed**, built with
  hardware in hand.
- **Geometric sim** (not rendered) for localization. Detector validated on real imagery
  only; localizer on sim with ground-truth detections; a glue/wiring test checks
  detector→localizer plumbing (units, axis conventions, coordinate origin).
- **Anti-circularity** (shared schema not values) + **mandatory non-zero injected
  time-sync error** so the dominant real failure is exercised.
- **Per-component bar (EVERY component in the pipeline has one):**
  - FrameSource/TelemetrySource → parser correctness on recorded bytes/files (`.srt`,
    blackbox, CRSF), and **frame↔telemetry time-alignment** produces the right `frame_id`
    pairing under injected offset/jitter. (The "genuinely wrong-able" code — test it.)
  - Detector → precision/recall + presence-interval temporal.
  - Tracker → ID-consistency invariants (stable ID across occlusion, no resurrection),
    incl. a low-feature (water/debris) clip where image-GMC is expected to struggle.
  - Projector → projection unit test (known pose+pixel → known ground point) vs analytic truth.
  - Frame-gating → asserts good-geometry frames pass and bad ones (oblique / high-rate /
    |accel|≠1g / high-vibration) are rejected at the configured thresholds.
  - Confirmation → decision truth-table + false-confirm rate on adversarial flicker (test hardest).
  - Fuse+Quantify (localizer) → meters error + coverage under mismatched noise.
  - WS → shared schema (pydantic→JSON Schema) + round-trip smoke.
  - UI → functional Playwright happy-path over a mock-WS fixture (DOM/behavior asserts).
- **One mandatory end-to-end test:** replay a recorded fixture → Python service → real WS
  → headless UI → assert a survivor pin lands at the correct map coordinate with the
  expected uncertainty. This is the ONLY test that catches coordinate-convention bugs
  (lat/lng order, datum, radians/degrees, image-axis origin) — the highest-consequence
  silent failure in the system. Few and golden, not a suite.
- **Cheap high-value additions:** flight recorder in the live build (field failure →
  replay fixture); capture one raw real stream as the golden fixture.
- **Determinism:** seed all RNG (MC asserted exact); detector eval on CPU/ONNX in CI
  (no GPU/ANE on runners) with tolerance bands; quarantine async-WS timing tests.

**Deferred to v1.x:** rendered sim, live source impls, full HERIDAL harness, held-out
flight harness, contract suite, visual-regression across viewports.

---

## Pillar 4 — UI / UX (requirements; visual design is a later pass)

**The spine: one Contact, three projections.** Map, video, list are views of a single
global selection — **bidirectional** (row ↔ pin ↔ overlay), hover-preview vs click-
commit, **survives data updates**. **Built first** — it's the architectural spine and the
#1 signal separating a tool from a generic dashboard.

- **Layout (fixed responsive grid):** **map primary** (SAR is spatial); list a
  persistent rail; video a docked, selection-bound panel. No draggable panels.
- **Attention (recall-first → alarm fatigue is the systemic risk):** detections
  **latch**; **tiered alerts** (loud only for PINPOINT/SWEEP high-confidence; CUE-ONLY
  posts silently); explicit per-contact ack; coalesce bursts; no repeat-chime.
- **Core loop one-click under stress:** clearance-state transitions single-click +
  **reversible** (life-safety undo); dispatch snapshots coordinate, later motion →
  delta alert; track ID always visible/radio-usable.
- **Map:** offline cached basemap; drone position+heading+track; **live camera footprint
  + accumulated searched-area coverage** (most important non-pin layer); pins encode
  class+clearance+confidence, SWEEP/AREA drawn at true radius; clustering + filter by
  state/class; operator reference markers.
- **Video:** instant rewind/pause (rolling buffer); snapshot to contact; **manual contact
  creation for AI misses** (hard requirement for a recall-first tool); loud LINK-LOST
  (frozen frame never looks live); overlays show ID + both confidences, fresh vs coasting.
- **List:** algorithm proposes, operator disposes (re-sort/filter/pin-override); columns
  non-negotiable: track ID, class, **detection-conf AND localization-conf separately**,
  clearance, age, CONVERGING/STABLE, heading-limited. Cleared contacts demote, not vanish.
- **Trust — degrade visibly, never silently:** always-on system-health strip (link/
  telemetry/GPS state, time-since-fix); stale telemetry → localization-confidence visibly
  collapses; coordinates radio-speakable, single-format, datum-explicit; never hide
  link-lost, telemetry-stale, the confidence gap, age, delta, heading-limited.
- **Craft signals (anti-AI-generated):** consistent interaction grammar; canonical
  Contact detail/command panel with one primary-action verb per state; status as a
  closed state-machine with one encoding across pin/row/panel; **tabular numerals**, one
  coordinate/unit/time format; **eased pin motion, never teleport**; no scroll-yank
  re-sorts; heartbeat liveness; designed empty/loading/error states; keyboard-first nav +
  `?` shortcut sheet.
- **Memory layer:** **append-only mission log in v1** (timestamped detections, state
  changes, snapshots, notes, link events). Polished export + shift-handoff view → v1.x.

---

## OUT OF SCOPE for v1

**Deferred to v1.x (improve a working v1, don't fix a broken one):** DEM ray-march;
Schmidt-consider heading-bias estimation; recursive information filter; camera↔IMU
time-offset estimation; flight-tuned noise calibration; temporal/video-input detector;
standalone Confirmation framework; full HERIDAL harness; live FrameSource/TelemetrySource
impls; photorealistic sim; cross-language contract suite; held-out flight harness;
visual-regression across viewports; polished export + handoff view; multi-pass
reconciliation; drone/battery panel; spatial-audio alerts; saved filters; command
palette; activity-feed; density toggle; multi-select.

**Rejected — wrong for this platform (not merely deferred):** real-time VIO (O4 video
not time-synced to FC IMU clock); SfM/bundle adjustment in-loop (hours; fails on blur/
low-overlap/changed terrain); GCP homography (post-disaster landmarks destroyed); deep
cross-view geolocation (solves drone self-location, not survivor; fragile); RTK/gimbal
as a v1 assumption (highest-value *future* hardware upgrade for sub-meter).

**Scope boundaries — what v1 is NOT:** not a flight controller / tasking system (operator
commands teams by radio); single drone / operator / feed; not a live real-time hardware
integration (proves algorithms + UX against recorded/synthetic + real *recorded* data;
live real-time capture is its own phase).

**Demo website (IN scope — Phase 6):** the same React UI, built as a static browser site
fed by a baked canned-mission data file (no Electron, no backend, no in-browser inference),
for GitHub credibility + click-a-link demo-ability. Reuses the mock-WS data path; it's
packaging + data-baking, not new UI. Live in-browser inference and server-side upload
processing are explicitly NOT this (v2 / rejected — the latter contradicts on-device ethos).

## v1 definition-of-done gates (from CLAUDE.md, per pillar)

- **Detection + localization:** tests pass; detection metrics on curated real footage
  (per-subclass recall, FP per km²); localization error in meters + validated coverage.
- **Real-time:** two distinct constraints, both gated. **Throughput:** ≥10fps detection
  on Apple Silicon via Core ML/ANE (video displays at full 30fps; detection decoupled).
  **Latency:** in-app glass-to-glass ≤120ms (frame on socket → painted overlay + map pin),
  measured — the CLAUDE.md sub-budget (decode / inference / georeference / render). These
  are different (sustained rate vs per-frame delay); both must hold.
- **UI:** design review vs `docs/DESIGN-SYSTEM.md` + functional Playwright over mock-WS.

## Unresolved / to-confirm before/while building

- **Detector input resolution + real-time feasibility (spike, do FIRST):** measure ANE
  latency + post-export recall at {640,960,1280}; this resolves the 1280-vs-≥10fps
  tension. The plan must order this before committing detection resolution.
- **Incoming real dataset pose completeness:** does the ~2026-07-01 dataset include
  synchronized altitude + pitch/roll + position? If only altitude+heading, v1 localization
  scopes to near-nadir. Confirm on arrival.
- **FP budget target value:** confirm `≤ N false survivors / km²` against the curated set.
- **Moving-survivor handling:** v1 accepts smearing (non-converging → big radius). Confirm
  this is acceptable for the curated footage, or whether floodwater drift is common enough
  to pull basic moving-target handling forward from v1.x.
- **Image-GMC over water/debris:** confirm the low-feature failure mode is caught by
  frame-gating rather than silently producing bad tracks (named test exists; needs real data).
