# HADES UI Overhaul Plan (P5 rework)

> **For Claude:** REQUIRED SUB-SKILL: superpowers:executing-plans. Inherits all HADES rules — NO git commits (treat "Commit:" as a done-label), auto-adversarial review instead of confirmation prompts, one-phase-per-session.

**Why this plan exists:** the initial P5 UI has a good mission-control IA (dense contact table, status strip, event log) but three real problems seen in the running app: (1) **the map center renders empty** — no basemap, just a drone wedge + floating pins on black (a functional bug, the most damaging issue); (2) the **video panel is also empty/black**; (3) the **palette is near-black** and reads AI-generated. Plus a scope addition: it must feel like **a proper multi-page product**, not one bare screen.

**Decided directions:**
- Investigate the empty map's real cause FIRST (don't guess).
- **Light/neutral operations theme** (the bright end — strongest anti-AI-dark move; full palette flip).
- **Pre-downloaded PMTiles for a real area-of-operations** (real coastline/streets under the pins).
- **Multi-page app:** Operations (live, the current view) · Mission Review / Contacts · Map / Playback · Settings + Docs. Shared nav. Built in one overhaul pass.

**Tooling (verify connected at session start; proceed with what's live if not):** shadcn MCP (accessible primitives: nav, tables, dialogs, selects, settings forms), Magic MCP (components constrained by the locked design system), Chrome DevTools MCP (investigate the map + de-slop verify the running app), frontend-design + impeccable (judgment: the light design system + IA), Web Design Guidelines (audit). Sequence stays **judgment → constrained generation → verify**; tools never invent the aesthetic.

---

## Stage 0 — Verify tools + investigate the empty map (NO code yet)

### Task 0.1: Verify MCP/skills connected
**Step 1:** Confirm shadcn MCP + Chrome DevTools MCP are connected (`/mcp`) and the Web Design Guidelines skill is available. If any is missing, note it and proceed with the connected set (frontend-design + impeccable + Magic are the floor). Do not block.

### Task 0.2: Investigate WHY the map is empty (Chrome DevTools MCP)
**Step 1:** Run the dev app; use Chrome DevTools MCP to inspect: console errors, failed network/tile requests (404 on tiles/PMTiles/style?), whether the MapLibre canvas mounted at all, and the map container's computed size (a `height:0`/flex bug renders a valid map into nothing). Also check the video panel's blank cause.
**Step 2:** Write findings to `docs/plans/ui-overhaul-investigation.md` — the ACTUAL root cause(s), not a guess. **Gate: no map fix until the cause is named.**
**Commit label (no commit):** `docs: ui-overhaul investigation (empty map root cause)`.

---

## Stage 1 — Fix the broken surfaces (a styled-empty map is still empty)

### Task 1.1: Acquire + serve a real-AO PMTiles basemap
**Step 1:** Pick a hurricane-prone coastal area-of-operations; download a PMTiles extract for it; place under `ui/public/` (or served locally). Add a Protomaps offline style (bundled glyphs/sprites). Scope the bbox/zooms so the file is sane.
**Step 2:** Wire MapLibre to load it (pmtiles protocol). **Failing test → green:** the map renders actual basemap tiles (coastline/streets), asserted via a Playwright/DevTools check that the canvas has non-empty tile content, not just our overlays.
**Commit label (no commit):** `fix: real-AO PMTiles basemap renders (map no longer empty)`.

### Task 1.2: Fix whatever else the investigation found
**Step 1:** Apply the root-cause fix from 0.2 if it's separate from the basemap (container sizing, style URL, protocol registration). Regression test that reproduces the empty state → green.
**Commit label (no commit):** `fix: <root cause> — map content renders`.

### Task 1.3: Video panel — show real content or an honest empty state
**Step 1:** If the panel is blank because no frames flow in demo mode, give it either the canned demo frames or a **designed empty/placeholder state** ("no live feed — demo mode") — never a raw black void. Playwright assert the panel shows content or the designed empty state.
**Commit label (no commit):** `fix: video panel content / designed empty state`.

**Stage 1 green:** map shows real terrain with pins on top; no blank black surfaces anywhere; the "looks broken" feeling is gone before any palette work.

---

## Stage 2 — Lock the LIGHT design system (the 5.0 gate, done right)

### Task 2.0 (JUDGMENT GATE): light operations design system — REFERENCE-DRIVEN, OPINIONATED
**Not component code. The goal is a real human designer's output: a distinctive point of view built from real references — NOT the statistical-average AI dashboard.** Revises the existing P5 system (neutral chrome / B612 + Plex Mono / orange=survivor, magenta=system) toward lighter + multi-page; doesn't start from scratch.

**Step 1 — References + point of view (the anti-slop foundation):** Pull SPECIFIC real-world references (real mission-control / ops tools — ATC, Palantir Gotham, Linear, Bloomberg/flight-ops, Foreground/instrument UIs). For each, name *what specifically works* and why. Then write a one-paragraph **design point of view** — a real opinion (e.g. "precision instrument: tight modular grid, hairline rules, intentional density, a restrained signal palette where every color carries meaning, monospace for all machine values"). Slop happens when there's no reference and no opinion; this step forbids both.

**Step 2 — Anti-slop KILL-LIST (the system must violate these by design):** no Inter / default system-ui font (pick distinctive, intentional type); no generic purple/blue gradient; no default Tailwind/Material shadow; no perfectly-centered hero; no emoji icons (coherent custom/lucide icon approach); no three-equal-cards row; no "clean and modern" as a non-decision. Write the kill-list into DESIGN-SYSTEM.md as hard rules.

**Step 3 — The system:** distinctive type scale (tabular numerals for all coords/IDs/timers), spacing rhythm, radius, REAL elevation, **purposeful motion/micro-interactions** (not decorative), and a coherent icon strategy. A **distinctive aesthetic spine**, not a neutral theme.

**Step 4 — Multi-page shell spec:** top/side nav, the page set, consistent page chrome, the "one Contact, three projections" selection spine preserved across pages.

**Step 5 — Reference mockups** for each page + nav, evaluated AGAINST the Step-1 references (does ours hold up next to them?).

**Step 6 (adversarial):** subagent panel — design-skeptic / mission-control-domain / **AI-slop-detector (explicit: "name every cliché present")** / simplicity — before locking. Fold in.
**Gate: no retrofit/new-page code until DESIGN-SYSTEM.md is locked AND the kill-list + point-of-view are in it.**
**Commit label (no commit):** `docs: locked light operations design system + multi-page spec`.

---

## Stage 3 — Multi-page shell + navigation

### Task 3.1: App shell + router + nav
**Files:** `ui/src/app/` (router, layout, nav), test.
**Step 1: Failing Playwright test** — a persistent nav (Operations / Mission Review / Map / Settings+Docs) renders; routes switch; the **global selection spine survives navigation** (select a contact on one page, it's still selected on another). Styled to DESIGN-SYSTEM.
**Step 2-4:** red→green (shadcn nav primitives). **Commit label (no commit):** `feat: multi-page shell + nav + cross-page selection`.

---

## Stage 4 — Retrofit + build the four pages (to the locked system)

> **⛔ EVERY page in this stage uses the ITERATE-AGAINST-THE-RENDER loop — not build-once.** This is the single biggest anti-slop behavior (it's what a human designer does and AI skips). For each page: **build → Chrome DevTools MCP screenshot the running page → critique it honestly against the Stage-2 references + kill-list (what looks AI? what's lazy? what would a designer fix?) → refine → re-screenshot.** Minimum 2 refine passes per page; do not move on while it still trips the kill-list. Functional Playwright is the floor, not the bar — "tests pass" ≠ "looks human-designed."

### Task 4.1: Operations page (retrofit the existing view)
**Step 1:** Recolor/retrofit the current live view to the light system — status strip, contact rail, event log, map, video. Keep the good IA; fix the palette, spacing, elevation, empty states. Playwright: renders to the new tokens; DevTools spot-check.
**Commit label (no commit):** `feat: operations page retrofit to light system`.

### Task 4.2: Mission Review / Contacts page
**Step 1: Failing tests** — full-page contact manager: complete sortable/filterable table (shadcn data-table), per-contact detail panel, clearance workflow (one-click reversible transitions), mission timeline/log. Roomier than the rail; shares the selection spine.
**Step 2-4:** red→green. **Commit label (no commit):** `feat: mission review / contacts page`.

### Task 4.3: Map / Playback page
**Step 1: Failing tests** — map-dominant page: full-screen survivor map, coverage layers, scrub/replay the mission timeline, measure tool. Reuses the basemap + map components.
**Step 2-4:** red→green. **Commit label (no commit):** `feat: map / playback page`.

### Task 4.4: Settings + Docs page
**Step 1: Failing tests** — Settings (sensor-error config, confirmation thresholds, basemap/AO selection, demo-vs-live toggle) via shadcn form primitives; Docs route renders the shared markdown (ties into P7's in-app docs — one source).
**Step 2-4:** red→green. **Commit label (no commit):** `feat: settings + docs pages`.

---

## Stage 5 — De-slop audit + green (Chrome DevTools MCP)

### Task 5.1: Running-UI verification across all pages
**Step 1:** Chrome DevTools MCP drives every page — screenshot each, measure spacing/contrast/type against DESIGN-SYSTEM tokens, catch AI-look tells (inconsistent spacing, default shadows, non-tabular numerals, generic gradients, blank surfaces). Fix what it finds.
**Step 2 (kill-list audit):** go through the Stage-2 kill-list item by item on the running app and assert each is absent (no Inter/default font, no generic gradient, no default shadow, no centered-hero, no emoji icons, no three-equal-cards, etc.). Any hit = fix before green.
**Step 3 (side-by-side):** screenshot our pages NEXT TO the Stage-1 reference tools; honestly answer "does ours hold up, or does it look like a generated template beside them?" Refine until it holds.
**Step 4:** impeccable + frontend-design design review (+ Web Design Guidelines); adversarial "name every cliché / does this look AI-generated?" panel; fold in fixes.
**Step 5:** functional Playwright happy-path suite green across all pages.
**Commit label (no commit):** `test: multi-page de-slop audit + playwright green`.

**Plan green criterion:** map renders real terrain (no blank surfaces); light operations theme locked + applied; a proper multi-page app (Operations / Mission Review / Map / Settings+Docs) with shared nav + cross-page selection; **the kill-list is provably absent, the design holds up beside its real references, and the iterate-against-render loop ran (min 2 passes/page)**; passes DevTools de-slop audit + design review + functional Playwright; nothing reads AI-generated or broken.

---

## Notes
- This reworks/replaces the original P5 single-screen scope; the demo website (P6) and docs (P7) inherit the new multi-page UI + light system automatically (shared UI code).
- Investigation (Stage 0) gates the fix — the map's real cause must be named before fixing.
- Light theme = full palette flip → Stage 4 retrofit is the heavy part; budget for it.
