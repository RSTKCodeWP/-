# HADES — Technical Design (DESIGN.md)

> **Status:** skeleton (Phase 0). Sections marked _(TBD: Phase N)_ are filled when that
> phase formalizes them. This is the engineering reference for module boundaries, the
> WebSocket message schema, **coordinate conventions** (filled now — pure reference,
> highest-leverage to fix once), and on-disk data layout.
>
> **Source-of-truth chain:** `CLAUDE.md` (project rules) → `docs/plans/2026-06-23-hades-design.md`
> (approved system design + decisions) → **this file** (concrete schemas/conventions) →
> `docs/DESIGN-SYSTEM.md` (UI aesthetic, written in Phase 5).

---

## 1. Module boundaries

Pipeline (each module = one responsibility; never reaches across a boundary):

```
FrameSource → Detector → Tracker → Projector → Confirmation → Fuse+Quantify → UI
```

| Module | Package | Input → Output | Knows nothing about |
| --- | --- | --- | --- |
| **FrameSource** | `hades.ingest` | — → `Frame(frame, timestamp, seq)` | detection, telemetry |
| **TelemetrySource** | `hades.ingest` | — → `Pose(lat, lon, alt, roll, pitch, yaw/cog, t)` | pixels, detection |
| **Detector** | `hades.detect` | `frame` → `Detection[]` (box, `person`, conf) | time, tracks, world |
| **Tracker** | `hades.track` | `Detection[]` → tracks (persistent IDs) | world coordinates |
| **Projector** | `hades.locate` | detection + pose → cheap ground point | fusion, uncertainty |
| **Confirmation** | `hades.confirm` | tracks + ground points → contacts (tiered) | the projection math |
| **Fuse+Quantify** | `hades.locate` | confirmed contact → fused coord + uncertainty | UI, tracking |
| **WS / IPC** | `hades.ws` | service ↔ UI over two localhost channels | pipeline internals |

**Single source of truth (non-negotiable — guards the convention-divergence failure):**

- The ray→ground math lives in exactly ONE module — `hades.locate.geometry` (built in
  Phase 3, Task 3.4) — and is imported by **both** the Projector and Fuse. Never
  re-implemented.
- The sensor-error / config schema lives in exactly ONE module —
  `hades.locate.error_model` (Phase 4, Task 4.1) — consumed by **both** the geometric
  simulator and the Monte Carlo uncertainty propagation. Shared **schema, never values**
  (anti-circularity).

---

## 2. WebSocket message schema

Source of truth: `hades.ws.schema` (pydantic v2 models). Each model exports JSON Schema
via `model_json_schema()` for the UI side; validation runs at the process boundary so a
malformed message fails loudly here, not as a wrong coordinate downstream (§3.2 bug class).

Two localhost channels, aligned by `frame_id`:

- **Binary channel** — JPEG-encoded frames (one per displayed frame).
- **JSON channel** — `DetectionMessage` (Phase 2, below) and `ContactRecord` (Phase 4).

### 2.1 `DetectionMessage` (Phase 2 — formalized in Task 2.6)

Per-frame detections, aligned to the binary channel by `frame_id` (== FrameSource `seq`).
Boxes are `box_xyxy = (x_min, y_min, x_max, y_max)` in **original (pre-letterbox) frame
pixels** (§3.2); `conf ∈ [0, 1]`; `cls` is `"person"` (single-class v1). An empty `boxes`
list is a valid "nothing detected this frame" message, not an error.

```jsonc
{
  "type": "detection",        // discriminator — routes the message on the UI side
  "frame_id": 42,             // int ≥ 0, the frame this belongs to
  "timestamp": 1.5,           // frame presentation time, seconds
  "boxes": [
    { "box_xyxy": [10.0, 20.0, 30.0, 50.0], "conf": 0.9, "cls": "person" }
  ]
}
```

Validation (enforced by the model, tested in `tests/ws/test_schema.py`): `frame_id ≥ 0`;
`0 ≤ conf ≤ 1`; `box_xyxy` exactly 4 numbers and ordered (`x_max ≥ x_min`, `y_max ≥ y_min`);
`timestamp` required. `DetectionMessage.from_detections(...)` adapts the detector's
`Detection`s onto the wire.

Stub of the taskable `ContactRecord` (full schema in Phase 4, Task 4.6 — see design doc
lines 153–160):

```
ContactRecord {
  track_id, coord (lat, lon),
  sweep_radius_m, actionability_class (PINPOINT | SWEEP | AREA | CUE-ONLY),
  priority_tier (contact | candidate | strong),
  detection_confidence, localization_confidence,   # separate axes
  convergence (CONVERGING | STABLE),
  snapshot_on_dispatch_coord, delta_from_dispatched_m,
  time_last_seen, age, clearance_state,
  source (drone/pass/frame_range), heading_limited, cluster_info
}
```

---

## 3. Coordinate conventions (FILLED — read before writing any geometry)

> These exist to kill the named, highest-consequence bug classes the design fears
> (design doc lines 213–214): **lat/lng order, datum, radians vs degrees, image-axis
> origin.** Every coordinate-bearing function states which convention it uses. The
> end-to-end test (Phase 5, Task 5.9) is the backstop; these conventions are the
> prevention.

### 3.1 Geodetic / world

- **Datum:** WGS84 everywhere. No other datum enters the system.
- **Order:** geographic coordinates are **(latitude, longitude)** in that order in all
  Python APIs, dataclasses, and the WS schema. Degrees, not radians, at every interface
  boundary. _(MapLibre GL consumes `[lon, lat]` — that flip happens ONLY at the map-render
  edge in the UI, behind a single named adapter so the "one sanctioned place" is
  enforceable in review, never a silent inline swap.)_
- **Angles:** **degrees** at every public interface and serialized field. Radians are
  permitted only inside a single function body and never cross a boundary. The two
  trig-heavy interior conversions that MUST `deg→rad` at function entry: building
  `R_world_body` from `(roll, pitch, yaw)` (§3.3), and the `cos(lat)` scaling in the
  lat/lon↔meters conversion below (feeding degrees to a radian `cos` is a silent
  latitude-dependent scale error).
- **World frame (local tangent plane):** flat-earth v1, **ENU** (East, North, Up),
  right-handed, **+z up**, origin at the per-mission operator reference. ("ENU-ish" is
  banned — the world frame is committed ENU.) Small-angle lat/lon ↔ ENU-meters uses the
  per-mission origin. (No UTM/grid in v1; documented if added.)
- **Altitude:**  meters. **⚠ DATUM OF `alt` IS AN OPEN DECISION — see §3.5.** The flat-earth
  geometry only needs the *scalar AGL* (drone-to-ground-plane vertical distance), not an
  absolute height, so the implementation derives `AGL = drone_alt − ground_elev` **only
  when both share one vertical datum.** `Pose.alt` therefore carries an explicit
  `alt_datum` tag set at the `TelemetrySource` boundary; the operator's
  ground-elevation input carries the same tag; `ray_to_ground` asserts they match (or
  converts) before subtracting. The tag is a string with allowed values
  `HAE` | `MSL` | `REL_TAKEOFF` | `UNKNOWN` — **a two-value `HAE`/`MSL` tag is insufficient**
  because the highest-quality real source (DJI O4 `.srt` `rel_alt`) is height-above-takeoff,
  which is *neither* HAE nor MSL; forcing it into one of those would fabricate a tag and
  silently defeat the assert this tag exists to power (§3.5). `ray_to_ground` must refuse to
  subtract across `REL_TAKEOFF` vs an absolute datum, or `UNKNOWN`, rather than assert-equal. `σ_h` (ground-elevation uncertainty) is sampled in the
  Monte Carlo alongside GPS σ, attitude σ, heading σ, and time-sync offset (full list in
  `error_model`, Phase 4).

### 3.2 Image / pixel

- **Origin:** top-left **(0, 0)**; **+x right, +y down** (OpenCV/standard image
  convention). Detection boxes are `box_xyxy = (x_min, y_min, x_max, y_max)` in **pixels**
  of the **original (pre-letterbox) frame**. Any letterbox/scale applied for inference is
  undone before a pixel leaves the detector.
- **Projection reference point (v1, committed — no "default"):** the box's
  **bottom-center** `((x_min+x_max)/2, y_max)`, on the feet-on-ground assumption. This is
  the seam the detector→localizer glue test (Task 4.8) guards.
  - **Known bias (feeds the uncertainty radius, design "fail loud"):** bottom-center
    assumes the bottom pixel sits at the §3.1 ground plane. A **prone / in-water survivor**
    (the literal target domain) violates this — the contact surface is the water/body
    surface, not terrain — so bottom-center is an arbitrary extremity, not a ground-contact
    point. This is a named bias source, larger at oblique pitch, not a silent error.

### 3.3 Body / camera frames

- **Handedness (global):** all frames are **right-handed**; all `R` are **proper
  rotations** (orthonormal, det = +1). The composition convention is **active rotation of
  column vectors**: `v_world = R_world_body · R_body_cam · v_cam`. (Passive rotations or
  row-vector math silently transpose everything.)
- **Body frame (FRD):** x-forward, y-right, z-down (standard aerospace body frame).
  Airframe attitude `(roll, pitch, yaw)`: pitch/roll from the FC IMU, yaw/heading from the
  `HeadingSource`. `R_world_body` (FRD body → ENU world) is built from the **Z-Y-X
  intrinsic (yaw→pitch→roll) aerospace Euler sequence** with **+pitch = nose-up,
  +roll = right-wing-down, yaw clockwise from true North**, then the fixed FRD(z-down) ↔
  ENU(z-up) axis adapter. Concretely: `Rotation.from_euler("ZYX", [yaw, pitch, roll],
  degrees=True)` composed with the NED↔ENU swap (or the direct ENU construction) — the
  exact call is fixed in `geometry` (Task 3.4) and unit-tested against analytic truth.
- **Camera optical frame:** **+z along the optical axis (into the scene), +x right,
  +y down**, matching the image axes. `K⁻¹·pixel` yields the optical-frame ray
  `[(u−cₓ)/fₓ, (v−cᵧ)/fᵧ, 1]ᵀ`.
- **Boresight `R_body_cam`:** maps **camera-optical → FRD-body**. For the O4's fixed
  forward-down mount this is a **full axis permutation** (optical +z → body +x, etc.), NOT
  near-identity — the O4 is hard-mounted, no gimbal; camera pitch = fixed mount angle +
  airframe pitch. Boresight-calibrated config held in `CameraModel` (Task 3.4).
- **Intrinsics `K`** + distortion are camera config; pixels are undistorted before forming
  the ray.

### 3.4 The one ray→ground recipe (canonical — design doc lines 132–134)

```
undistort(pixel)
  → K⁻¹ · pixel                       # optical-frame ray (+z into scene)
  → R_world_body · R_body_cam · ray   # active rotate optical → ENU world
  → require ray·Up < 0, else REJECT   # ray must point toward the ground, not the sky
  → intersect flat-earth plane at the operator-set ground elevation (§3.1 AGL)
  → ENU offset → (lat, lon)           # WGS84, (lat, lon) degrees order
```

A ray with `ray·Up ≥ 0` (pointing at/above the horizon) must NOT produce a phantom
ground pin behind the drone — a real high-pitch-oblique failure mode. The dominant
ground-error term is **heading** (no magnetometer → 15–30° sigma; ≈ 1.75 m lateral error
per 100 m range per degree — design doc lines 127, 143): "attack heading or nothing."
Not every ray becomes a *fused* coordinate — **frame-gating** (Task 3.3) excludes
bad-geometry frames from the fused estimate while still surfacing them as CUE-ONLY
contacts with a large radius.

Implemented once in `hades.locate.geometry.ray_to_ground(pose, pixel, ground_elev)`.
Verified against analytic truth with every convention above explicit (Task 3.4).

### 3.5 OPEN DECISION — vertical datum of GPS altitude (⚠ resolve before Phase 3/4)

The M10-class GPS can emit altitude as **HAE** (height above WGS84 ellipsoid) **or
MSL/orthometric** (geoid-corrected) depending on FC firmware and the CRSF telemetry frame
(CRSF's GPS-altitude field carries **no datum tag**). The geoid undulation on Gulf/Atlantic
hurricane coasts is ≈ **−25 to −35 m**, so a blind `drone_alt − ground_elev` that mixes
datums injects a fixed ~30 m AGL error → a direct down-range bias at oblique slant,
swamping the design's ~10 m nominal target. The `alt_datum` tag (§3.1) makes the mismatch
*detectable*; the open decision is **which canonical datum HADES normalizes to** and
**how the operator enters ground elevation**. Resolved against the real `.srt`/CRSF data
when the dataset arrives (~2026-07-01) and recorded here. Tracked as the fork raised in
the Phase 0 session.

**Phase 1 finding (DJI O4 `.srt`):** the recorded `.srt` sidecar carries `rel_alt`
(barometric height **above the takeoff point** — the stable, trustworthy value) and
`abs_alt` (firmware-unreliable, datum undocumented; the field is known to glitch — the
`clip_2s.srt` fixture plants a `-32.309` outlier on one frame to exercise this). The `.srt`
also carries **no attitude or gimbal fields at all** (confirmed across DJI O-series), so a
`Pose` from `SrtFileSource` is **position-only**: `roll`/`pitch`/`yaw` are `None`, and
`yaw` is never back-filled with GPS course-over-ground (course ≠ heading — the
heading-limited problem). Consequently `SrtFileSource` emits `alt = rel_alt`,
`alt_datum = "REL_TAKEOFF"`, and surfaces `abs_alt` only as flagged advisory metadata. The
canonical-datum decision above is unaffected: it governs how the *absolute* altitude path
(live CRSF) normalizes; the validation replay path stays on `rel_alt`/`REL_TAKEOFF` and
sidesteps the geoid question entirely.

---

## 4. Data layout

_(Fixtures landed in Phase 1; model artifacts in Phase 2.5.)_

```
service/
  src/hades/            # the pipeline packages (table in §1)
    ingest/             # FrameSource / TelemetrySource impls + time-sync (Phase 1)
    cli/                # `hades` umbrella CLI (replay-dump = observable ingestion)
  tests/
    fixtures/           # tiny committed clips + .srt sidecars (Phase 1)
      make_fixtures.py  # regenerates clip_2s.mp4/.srt, res_change.ts, clip_corrupt.h264
ui/
  src/                  # renderer (React) + electron/ main+preload
  tests/                # Playwright (mock-WS driven; Phase 5)
models/                 # .mlpackage / .onnx artifacts — GITIGNORED, not committed
data/                   # datasets (HERIDAL/SARD), recorded missions — GITIGNORED
docs/                   # this file, DESIGN-SYSTEM.md (P5), plans/
```

- **Model weights** (`*.mlpackage`, `*.onnx`, `*.pt`) and **datasets/recordings** are
  versioned artifacts, **not** committed to git (see `.gitignore`). Trained weights are a
  cluster/release artifact (Phase 2.5).
- **Fixtures** (tiny clips, `.srt` lines, golden JSON) ARE committed so tests stay
  offline + deterministic.

## 5. Detection resolution (latency-bounded — Phase 1.5)

The detector's input resolution is bounded by a **latency spike** (Phase 1.5): export
stock YOLO11s to CoreML at {640, 960, 1280} (FP16, `ComputeUnits.all`) and measure
**sustained** ANE ms/frame, judged on the **MacBook Air M4** field-laptop floor (fanless
→ throttles → honest worst case; ANE is ~identical across the M4 line). Gate: detection
≥ **10 fps** (decoupled from the 30 fps video path).

- **Feasible (≥10fps) set: {640, 960, 1280} — ALL THREE PASS** (MacBook Air M4, 2026-06-24;
  full table + ANE-placement verification in `docs/plans/spike-latency-results.md`). Median
  fps: 640→293, 960→63, 1280→57. Even 1280 clears the 10 fps gate by 5.7×. **ANE placement
  verified** (`ALL` ≈ `CPU_AND_NE` ≈ 3.5 ms ≪ `CPU_ONLY` 20 ms at 640).
- **Latency is no longer the binding constraint — recall is.** Since every candidate
  resolution passes, the **final single resolution** is chosen in **P2.5 Task 2.5.5**
  purely against *fine-tuned* per-subclass recall (pick the **largest** resolution recall
  wants; latency does not constrain it). Picking against stock-COCO recall now would tune a
  model we're about to replace (review note F5).
- **Tooling:** `hades-export-coreml` + `hades-bench-latency` (`hades.bench`, `bench`
  dependency-group). The benchmark's stats/gate logic is offline-unit-tested; the ANE
  measurement is a manual `@pytest.mark.ane` run. numpy is pinned `<2` for the spike —
  coremltools 9.0 crashes the export on numpy 2.x (`tasks/lessons.md`).
