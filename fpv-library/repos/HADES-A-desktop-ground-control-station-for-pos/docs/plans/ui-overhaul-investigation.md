# UI Overhaul — Stage 0 Investigation (empty map + black video root cause)

> Gate document for `docs/plans/2026-06-26-hades-ui-overhaul-plan.md` Task 0.2.
> **No map/video fix may begin until the real cause is named here.** It is named.

Method: ran the dev app (`pnpm dev:web`, the baked-`mission.json` demo source that the
original screenshot showed) at 1440×900 and drove **Chrome DevTools MCP** at it — console
log, full network trace, and direct DOM/canvas introspection via `evaluate_script`. No
guessing; every claim below is backed by a measurement.

Evidence screenshot: `docs/plans/_investigation/00-running-app.png` (reproduces the memo'd
empty-map / black-video screenshot exactly).

---

## Finding 1 — The map is empty BY DESIGN, not broken (no failed request)

**Root cause: there is no PMTiles basemap file, so `operationalStyle()` emits only a flat
background layer. The map renders a valid, alive canvas filled with the `LAND` color
(`#101418`) and nothing else.** It is not a sizing bug, not a mount failure, not a 404.

Measured facts that rule out every other hypothesis:

| Hypothesis | Verdict | Evidence |
|---|---|---|
| Map container is `height:0` / flex-collapsed | **RULED OUT** | `[data-testid="map-view"]` measures **1019×737**, `display:block`. |
| MapLibre canvas never mounted | **RULED OUT** | `canvas.maplibregl-canvas` present at **1019×737** (2038×1474 @2× DPR). |
| WebGL unavailable → fallback shown | **RULED OUT** | `[data-testid="map-unavailable"]` is **absent**; the map constructed fine. |
| A tile / style / glyphs request 404'd | **RULED OUT** | Full network trace: the **only** 404 is `/favicon.ico`. Zero tile/style/PMTiles requests are even made. |
| Real cause: no basemap source | **CONFIRMED** | `ui/public/` contains `mission.json` + docs only — **no `.pmtiles`**. `src/map/style.ts` explicitly: "with no PMTiles file, the style is just a flat operational background (zero network sources)." `MapView` is mounted as `<MapView />` with **no `pmtilesUrl` prop**, so the basemap branch never runs. |

So the green coverage wedge + floating pins sit on a flat dark fill because **the basemap
was never acquired**. The code is correct and offline-safe; the asset is simply missing.

**Fix (Stage 1.1):** acquire a real coastal-AO `.pmtiles` extract (the map is already
centered on `[-88.52, 30.215]` — Mississippi Gulf Coast, Biloxi, a real hurricane AO),
bundle an offline Protomaps style with local glyphs/sprites, and pass `pmtilesUrl` into
`MapView`. No container/sizing/protocol change needed — the protocol is already registered
and the style already has the (currently-dormant) pmtiles branch.

---

## Finding 2 — The video panel is NOT broken; the demo frame is a near-black synthetic image

**Root cause: the panel paints correctly. The baked demo replays ONE shared synthetic JPEG
(`mission.json.frame_jpeg_b64`, reused for all 90 frames) that is itself a near-uniform very
dark frame — so it merely *looks* like a black void.** This is a content problem, not a panel
bug.

Measured facts:

- Frames **are** flowing and decoding: the network trace shows ~180 `blob:` object-URL GETs
  (reqid 70, 74–254) — exactly `VideoPanel.paint()` doing `URL.createObjectURL(jpegBlob)`
  per frame. None failed.
- The canvas **has painted content**, not the `#06080C` void: center pixel `[40,45,41,255]`
  (a desaturated gray-green, ≠ the void `[6,8,12]`); 520 non-black samples across the frame.
- Luminance histogram over 1567 samples: min 37 / mean 42 / max 122, with **1565 of 1567
  samples in the 32–64 bucket** → a near-uniform dark field with a few brighter pixels. That
  is the synthetic frame's own content, faithfully drawn.
- `mission.json` carries a single `frame_jpeg_b64` string reused across all 90 `frames` — so
  every painted frame is the same dark synthetic image (matches the P6 "honest synthetic
  scene" note in memory).

**Fix (Stage 1.3):** the panel itself needs no repair. Per the plan, give demo mode either
brighter canned frames OR — the honest, lower-risk move — a **designed placeholder/empty
state** ("no live feed · demo mode") so the surface never reads as a broken black void. The
real Electron+service path already shows live frames; this only concerns the demo source.

---

## Findings 3 — Palette reads AI-generated (the cosmetic driver, addressed in Stage 2/4)

Not a bug; the deliberate near-black chrome (`bg-bg-void` / `#06080C`, `LAND #101418`) is the
"reads AI-generated" problem the overhaul exists to fix. Out of scope for the Stage-1
functional fixes; resolved by the Stage-2 light-design-system lock + Stage-4 retrofit.

---

## Gate decision

Both broken-looking surfaces have a **named, evidence-backed root cause**:
1. **Map** — missing PMTiles basemap asset (acquire + wire it; Stage 1.1).
2. **Video** — correct panel, dark synthetic demo frame (placeholder/empty state; Stage 1.3).

Neither is a rendering/sizing/WebGL fault. Stage 1 may proceed.
