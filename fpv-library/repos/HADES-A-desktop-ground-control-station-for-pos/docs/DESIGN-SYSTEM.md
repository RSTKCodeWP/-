# HADES — Design System (DESIGN-SYSTEM.md)

> **Status:** LOCKED (Phase 5, Task 5.0 gate — hardened by a 4-lens adversarial panel +
> a grounded mission-control research brief). **REVISED at UI-overhaul Stage 2** (2026-06-26):
> the **Day (light) palette is now the DEFAULT operations theme** (§2.5), Night stays reachable
> via toggle, and a **multi-page console shell** is specified (§11) with a map-on-light retune
> (§12) — both folded through a second 4-lens adversarial panel. This is the UI source of truth:
> aesthetic spec, design tokens, the anti-AI-slop ruleset, and the implementation contract. No UI
> component code is written until this exists and is locked (impl-plan Task 5.0).
> Behavioral/product intent lives in `docs/plans/2026-06-23-hades-design.md`; cross-process
> schema/conventions live in `docs/DESIGN.md`. **This file governs how it LOOKS and FEELS.**
>
> Tokens here are the contract. Components reference token names, never raw hex / raw px.
> If a value isn't in this file, it doesn't go in the UI.
>
> **Provenance:** palette/type/cartography/motion grounded in ECDIS (IHO S-52), FAA-ATC &
> EUROCONTROL HMI human-factors, Okabe-Ito / Paul Tol CVD work, CARTO Dark Matter, IBM
> Carbon motion, and the real C2 lineage (ATAK/WinTAK, MIL-STD-2525, Bloomberg, Anduril
> Lattice). Color math (WCAG contrast + CIELAB ΔE) computed against the locked hexes, not
> eyeballed; the measured table is §2.6.

---

## 0. The one-line aesthetic

**An operational instrument, not a dashboard.** HADES looks like equipment a rescue
coordinator trusts with a life for a 6-hour shift in a field tent — dense, legible,
honest, and quiet until something genuinely needs attention. Closer to ATAK / ECDIS /
an ATC strip board than to a SaaS analytics dashboard. **The map IS the application;** the
list and video are projections of it (ATAK's defining lesson). Every pixel earns its place.

**The feeling we are buying:** *calm authority.* **The feeling we are refusing:**
*decorated, generic, "AI-generated dashboard."* The discipline below — neutral chrome,
scarce reserved accent, redundantly-encoded status, motion only as physical truth — is how
that refusal is won. Not by ornament.

---

## 1. Aesthetic direction (the committed point of view)

Mission-control instrument panel. Reference set + the one lesson taken from each:
- **ATAK/WinTAK** (SAR-proven across thousands of hurricane rescues) → *the map is the
  application, not a panel.*
- **MIL-STD-2525 symbology** → *encode state in color AND shape, never color alone, and
  reserve the status colors so nothing else competes.*
- **Bloomberg Terminal** → *one dark high-contrast palette where the bright accent is scarce
  and always means something.*
- **Anduril Lattice** (closest peer to our detect→localize→display loop) → *one Contact
  entity, rendered identically everywhere; selecting it anywhere lights it up everywhere.*
- **ECDIS (IHO S-52)** → *a desaturated operational chart so colored hazards read instantly;
  calibrated day/night palettes.*

Concretely, that commits us to:

- **Neutral, near-achromatic dark chrome.** The background ramp is cool charcoal, **not**
  saturated navy — saturation in the chrome is the #1 "AI dark-dashboard" tell and it
  competes with the only thing that should carry chroma: status + detections. Chroma is
  spent on data, not on the frame.
- **One structural hue (steel blue) + one rationed hazard hue (orange), kept apart from
  the closed status set.** Blue is *the interface* (chrome, selection, the drone). Orange
  is *world-urgency* (a survivor needs you) — and **only that** (see §2.4 P0 rule). System
  failure is magenta, not orange. A screen where orange means four things is a screen the
  operator stops trusting in exactly the wrong second.
- **Tabular everything, in a mono with instrument provenance.** Every value that must align
  (coords, IDs, confidence, age, radius, timestamps) is monospaced with tabular figures and
  slashed zero, right-aligned.
- **Flat, not glassy.** Elevation = one lighter surface step + a 1px hairline. No drop
  shadow, no blur, no frosted glass. (Gradients exist in exactly two *data* places: the map
  coverage wash and the uncertainty fill. Never as chrome.)
- **Density with rhythm,** on an 8px base + 4px/2px sub-grid, so dense reads as *engineered*.
- **Switchable-theme architecture from day one.** Tokens are semantic and theme-swappable
  (the deployment is sometimes a dark ops room, sometimes a sunlit field tent — ECDIS ships
  day/dusk/night for this exact reason). v1 ships the **Night (dark) palette**; a **Day
  (high-contrast) palette is stubbed in the same token contract** so it's a palette swap,
  not a component rewrite, when v1.x needs it.

---

## 2. Color tokens

Authored as **space-separated RGB channels** on `:root` (e.g. `--bg-base: 13 17 23;`) and
consumed through Tailwind as `rgb(var(--token) / <alpha-value>)` — this is the only form
that preserves Tailwind's opacity modifier, which §5.1 needs for the translucent map fills
without minting separate alpha tokens (see §9.1). Hex shown for human reference; the
**semantic name is the contract**, the channel triplet is the lock.

### 2.1 Canvas & surface ramp — NEUTRAL cool charcoal (chroma lives in data, not chrome)
```
--bg-void:    #06080C   /*  6   8  12  — deepest field behind all panels        */
--bg-base:    #0B0E14   /* 11  14  20  — app background (near-neutral, faint cool) */
--surface-1:  #141821   /* 20  24  33  — raised: cards, list rows, status strip   */
--surface-2:  #1C222E   /* 28  34  46  — hover / nested / input wells             */
--surface-3:  #28303E   /* 40  48  62  — active-pressed AND selected-row wash     */
--surface-4:  #333C4B   /* 51  60  75  — top elevation (dialogs, popovers)        */
--hairline:   #33456A   /* 51  69 106  — the elevation/divider border (tuned light
                           enough to stay crisp on mid surfaces — measured §2.6)  */
```
> Selected-row wash is **`--surface-3`** (single source — the old `--blue-dim` /
> `--hairline-soft` duplicates were removed; ΔE collisions, §2.6). Low-emphasis separation
> uses *spacing*, not a second invisible hairline (§6.1).

### 2.2 Text ramp (4 steps, contrast-verified §2.6)
```
--text-hi:        #E6EDF3   /* 230 237 243 — primary readout, coords, headings (off-white,
                              not #fff: cuts halation for the ~30-60% with astigmatism)   */
--text-mid:       #AAB4C0   /* 170 180 192 — labels, secondary data                       */
--text-lo:        #8593AD   /* 133 147 173 — meta/units/timestamps (lightened from the
                              original #6B7A94, which FAILED 4.5:1 on raised surfaces)     */
--text-disabled:  #565E69   /*  86  94 105 — inactive / N/A (intentionally sub-AA)        */
--text-on-accent: #06080C   /* text/glyph sitting ON a filled light status (orange/amber) */
```

### 2.3 Structural / brand blue — STEEL, not cobalt (desaturated off Tailwind-blue)
```
--blue-core:    #3B7BC8   /* 59 123 200 — primary action, selection ring, focus, the drone */
--blue-bright:  #5E9BD6   /* 94 155 214 — selected/active emphasis, live-link OK           */
--blue-track:   #6FA8DE   /* drone flight track on the map (cool, recedes vs warm pins)    */
```

### 2.4 Status palette (closed set — ONE encoding everywhere, CVD-safe, glyph-backed)
Each status is a single token reused identically across pin / row / panel / strip (§6.4),
and is **always** paired with a non-color channel (the §6.5 glyph alphabet) so it survives
CVD and glare. Separation is by **luminance + hue-axis**, never red-vs-green.
```
--st-nominal:   #2FB67C   /* teal-green: healthy, link OK, STABLE, searched-negative      */
--st-info:      #33C5E0   /* TRUE CYAN: informational, CONVERGING, candidate — pushed off
                            the structural blues so chrome-blue ≠ status-blue (§6.4)       */
--st-caution:   #E6A23C   /* amber: caution, SWEEP-grade, telemetry aging                 */
--st-warning:   #E8531F   /* HAZARD ORANGE (brand): WORLD-URGENCY ONLY — new high-priority
                            survivor, PINPOINT-urgent. NEVER system state. (P0 rule below) */
--st-critical:  #F5326B   /* MAGENTA-RED: SYSTEM-INTEGRITY FAILURE — link-lost,
                            telemetry-failed, service-down — AND dispatch-delta. (P0 rule) */
--st-stale:     #7E78A8   /* COLD DESATURATED VIOLET-SLATE: STALE / UNKNOWN / DEGRADED —
                            deliberately OFF the green→amber→orange→red severity ramp, so
                            "we don't know" can never read as "fine" or as "bad".         */
```

> **P0 RULE — the orange/magenta split (life-safety, hard, do not cross):**
> `--st-warning` (orange) = **world-urgency: a survivor needs you → lean in, dispatch.**
> `--st-critical` (magenta) = **system-integrity failure: do NOT trust the feed → the
> system went blind.** These demand *opposite* operator actions and live on different
> surfaces (survivor → list/map; failure → status strip). Binding one hue to both — the
> original draft's mistake — means an operator can't tell in <1s whether a person was found
> or the drone went dark. Orange in the rail = save someone; magenta in the strip = trust
> nothing here. The glyphs (§6.5) for these two are maximally distinct shapes because under
> glare the glyph may be the only surviving channel.

> **Why `--st-stale` is off the ramp:** the cardinal SAR sin is a smug confident-wrong
> readout (DESIGN.md / P4 bias-floor). "Degraded/unknown" is epistemically orthogonal to
> "good/bad," so it gets its own visual category. It is the LOWEST-contrast status and the
> weakest CVD case (violet can drift toward grey/blue), so it carries the STRONGEST
> non-color backup: dashed/hatched + de-rendered, never a small violet dot or violet body
> text alone (§6.5). The shared token still distinguishes "decayed fix" (was-good-now-old)
> from "never had a fix / CUE-ONLY" via *glyph/pattern*, not color (map: dashed-no-dot vs a
> decayed pin; the list mirrors it).

### 2.5 DAY palette — the DEFAULT operations theme (UI-overhaul Stage 2, LOCKED)
The `:root` tokens above are the **Night** palette (still shipped, reachable via the theme
toggle). The **Day** palette overrides the same channel variables under `[data-theme="day"]`
and is now the **default operations theme** (set on `<html>`). Both ECDIS-style modes ship —
Day default for sunlit field tents, Night for dark ops rooms — because a SAR GCS deploys in
both. This was hardened by a **4-lens adversarial panel** (design-skeptic / mission-control-
domain / AI-slop-detector / simplicity); the rationale below records the calls that survived.

**Point of view:** a precision-instrument LIGHT chart — a worn field document, NOT a light
SaaS admin panel. The discipline that keeps it out of slop:

- **WARM-neutral stone paper, never cool blue-gray.** `--bg-base #E6E3DD` carries a whisper of
  warmth. A cool-blue-gray ramp (`#F7F9FC`-class) is the exact Linear/Notion/Tailwind-`slate`
  light-dashboard tell *and* it imports chroma into the chrome — both forbidden. Chroma still
  lives in DATA, not the frame.
- **Elevation INVERTED for light:** base is the soft stone GROUND; raised surfaces step toward
  white (`--surface-1 #F3F1ED`); dialogs float to off-white `--surface-4 #FAF9F6` (**never
  `#fff`** — kill-list). "Raised = whiter card on a gray ground," not "lighter than base."
- **Selection leads with the steel ACCENT BAR, not a body wash.** `--surface-3 #E0DED6` is a
  NEUTRAL (warm, not blue) wash; the 2px `--blue-core` left bar + inset ring (§4.4) is the
  primary selection signal. Hover stays neutral — the only steel tint in a row means *selected*.
- **Re-steeled structural blue** (`--blue-core #2B5E8E`), desaturated off Tailwind cobalt, used
  ONLY for selection/focus/drone — never a surface tint.

```
--bg-void:   #D6D2CB   /* recessed gutter (darkest warm gray)           */
--bg-base:   #E6E3DD   /* app GROUND — warm stone (NOT white, NOT blue)  */
--surface-1: #F3F1ED   /* raised: cards/rows/strip (steps toward white)  */
--surface-2: #ECE9E4   /* hover / nested / input wells                   */
--surface-3: #E0DED6   /* NEUTRAL selected/pressed wash (bar carries it) */
--surface-4: #FAF9F6   /* dialogs/popovers (off-white, NOT #fff)         */
--hairline:  #9E978A   /* warm structural keyline (sole elevation carrier) */
--text-hi:   #201E1A   --text-mid: #4E4A43   --text-lo: #706B62   --text-disabled: #AAA59C
--text-on-accent: #FFFFFF
--blue-core: #2B5E8E   --blue-bright: #3A72A6   --blue-track: #4A749E
--st-nominal:#117449   --st-info: #0F768E   --st-caution: #C58E10   /* GOLD, dark-ink chip */
--st-warning:#D03E10   --st-critical: #C4164E   --st-stale: #68628C
--shadow-float: 0 1px 2px / 0 4px 12px-2px @ rgb(32 30 26 / .08–.10)  /* dialogs/popovers ONLY */
```

**Measured (WCAG, computed — not eyeballed):** text-hi 13.0–15.8:1 (AAA) on all surfaces;
text-mid 6.5–8.4:1; text-lo 3.9–5.0:1 (AA). Steel blue 4.0–6.0:1. Status hues clear ≥3:1 as
ink/stroke and ≥4.5:1 as white-on-fill chips — **except caution**, which stays a genuine
**gold** (white-on-gold is only 2.9:1) and therefore renders as a **dark-ink-on-gold** chip
(5.75:1). This is deliberate: deepening caution toward ochre to win white-chip contrast would
collapse it onto survivor-orange under CVD — a **P0 hazard**. Keeping caution bright gold also
restores the P0 luminance separation (gold L\*0.31 > orange L\*0.17 > magenta L\*0.13).

**The P0 split holds on light** — but on a light ground, **glyph + position carry the survivor/
failure distinction; color corroborates** (the dark theme's luminance-bloom of a magenta pin on
charcoal is weaker on light, so the §6.5 glyph alphabet is now the lead channel, not the backup).

**One sanctioned shadow exception:** the no-shadow rule earns `--shadow-float` for floating
layers ONLY (dialogs/popovers/toasts), because a hairline alone can't anchor a near-white card
on near-white paper. Never on in-flow chrome.

### 2.6 Measured color facts + constraints any change MUST preserve
- **Contrast (computed, WCAG):** `--text-hi` ≥ 13:1 (AAA) on all surfaces; `--text-mid`
  ≥ 7:1 (AAA) through surface-2; `--text-lo` ≥ 4.6:1 on surface-1/2 (AA — fixed from the
  failing #6B7A94). Body ≥ 7:1, smallest meta ≥ 4.5:1 is the lock; **re-run + paste the
  measured table at 5.12** (this section states intent + the math done at gate; 5.12 is the
  on-screen verification).
- **Removed redundant tokens:** `--hairline-soft` (ΔE 1.4 vs surface-2 → invisible) and
  `--blue-dim` (duplicate of surface-3's selected-row job). Do not re-add.
- Background stays neutral cool charcoal (glare + the "chroma in data only" rule). Status
  set stays CVD-separable; every status keeps a glyph backup. Orange stays world-urgency
  only; magenta stays system-failure only. `--st-stale` stays off the severity ramp.
- Hairline is tuned light (`#33456A`) because the no-shadow rule makes it the SOLE carrier
  of elevation; against two abutting `--surface-2` regions, separate by spacing, not a
  hairline (its contrast there is marginal).

---

## 3. Typography

Two families, both **freely licensed** (SIL OFL) so the offline-only constraint holds
(fonts are bundled via `@fontsource`, never fetched at runtime — §9.2). Distinctive and
professional — explicitly NOT Inter / Roboto / Arial / system-ui / Space Grotesk, and NOT
JetBrains Mono (the most over-used mono in AI-generated tooling — a tell).

```
--font-ui:   "B612", "IBM Plex Sans", system-ui, sans-serif;
--font-mono: "IBM Plex Mono", "B612 Mono", ui-monospace, monospace;
```

### 3.1 Family lock (with provenance — the anti-slop argument)
- **UI / display — B612 Sans.** Literally designed by **Airbus + ENAC for aircraft cockpit
  screens**, validated for legibility under degraded conditions and reduced cognitive load.
  It carries genuine instrument provenance that reads as *trustworthy*, not decorative — a
  humanist-grotesque with maximized glyph distinction. This provenance is the point: it's a
  characterful, defensible, non-default choice for a control surface. Fallback: **IBM Plex
  Sans** (single-provenance safety, loses the cockpit story). Weights used: 400 / 500 / 700
  (B612 ships Regular+Bold; use Plex Sans 500/600 where a mid weight is needed).
- **Data / mono — IBM Plex Mono.** Industrial-instrument character (IBM built Plex for
  exactly this register), true tabular figures, **no ligatures** (so `->` in a coordinate
  never fuses), excellent digit disambiguation. This is the workhorse: every coordinate, ID,
  confidence, radius, timestamp, and telemetry value is set in it. Fallback: B612 Mono.

### 3.2 Type scale (sparing — a control surface needs few sizes; hierarchy from weight +
color + sans/mono split, not size jumps)
```
--text-2xs:  11px;  /* secondary meta, unit suffixes, dense overlay labels   */
--text-xs:   12px;  /* dense table cells, captions, status-strip readouts     */
--text-sm:   13px;  /* default body / label (base)                           */
--text-base: 14px;  /* primary readouts, panel body                          */
--text-lg:   16px;  /* panel titles, selected-contact secondary readout      */
--text-xl:   20px;  /* the single headline coordinate / most important value */
--text-2xl:  24px;  /* reserved: the one hero value in a full-screen view     */
--line-tight: 1.2;  --line-normal: 1.4;  --line-relaxed: 1.5;
```
- weights: 400 body · 500 labels/selected values · 600 headings · 700 only for an active
  alert. No 800/900 — instrument, not poster. (Off-grid `12.5px` from the draft removed.)
- **All numeric data:** `font-variant-numeric: tabular-nums slashed-zero;` +
  `font-feature-settings: "tnum" 1, "zero" 1;` (fallback). Mandatory, applied via a single
  `.tabular` / `font-mono` utility. A digit changing must never shift its neighbors.
- **sans = language; mono = every value that must align**, right-aligned in tables.

---

## 4. Space, radius, elevation, motion

### 4.1 Spatial grid — 8px base + 4px/2px sub-grid (high-density bucket)
```
--sp-0: 0;   --sp-px: 1px; --sp-0_5: 2px; --sp-1: 4px;  --sp-2: 8px;
--sp-3: 12px; --sp-4: 16px; --sp-6: 24px; --sp-8: 32px; --sp-12: 48px;
```
Panel padding `--sp-3`/`--sp-4`; dense table cell padding `--sp-1`–`--sp-2`; section gaps
`--sp-6`. Inside dense components (cells, badges, overlay labels) use only `≤--sp-2`. Every
margin/padding is a token. No `13px`, no `7px`.

### 4.2 Hit targets (Fitts — a field tool used under stress; was missing, now hard)
```
--hit-min:     32px;  /* any interactive control floor (clears WCAG 24px)        */
--hit-primary: 40px;  /* primary verbs (DISPATCH, undo) — large, stress/glove-safe */
--row-h:       34px;  /* list/contact row (dense-pro 32-40 band)                  */
--row-h-log:   30px;  /* mission-log row                                          */
--strip-h:     38px;  /* status strip                                            */
```
Density reduces row *height*, never padding (padding = the hit target).

### 4.3 Radius — restrained, instrument-like
```
--radius-sm: 3px;  --radius-md: 5px;  --radius-lg: 8px;  --radius-pill: 999px;
```
sm = inputs/chips/controls; md = cards/panels/detail panel; lg = outermost frame only;
pill = status dots / count badges only. No fully-rounded "friendly" cards.

### 4.4 Elevation — hairline only, NO shadow; + the state matrix & z-index
```
--border-1:     1px solid rgb(var(--hairline));
--ring-focus:   0 0 0 2px rgb(var(--bg-base)), 0 0 0 4px rgb(var(--blue-core)); /* kbd focus */
--ring-selected: inset 0 0 0 2px rgb(var(--blue-bright));                       /* selected  */
--alert-glow:   0 0 0 1px rgb(var(--st-warning)), 0 0 12px -2px rgb(var(--st-warning) / 0.6);
```
**No `box-shadow` for elevation, ever.** Depth = surface step + hairline. The ONLY sanctioned
glows: `--ring-focus` (a11y) and `--alert-glow` (the single rationed tier-3 alert pin/row).

**State matrix (resolves focus/hover/selected/pressed collisions — precedence top-wins):**
| State | List row | Button / chip | Map pin |
| --- | --- | --- | --- |
| **selected** (highest) | `--surface-3` wash + 2px left accent bar `--blue-bright` + `--ring-selected` | `--ring-selected` | ring weight +1, label revealed (Full Data Block) |
| **keyboard-focus** | `--ring-focus` (composes over selected) | `--ring-focus` | `--ring-focus` on the pin hit-area |
| **pressed/active** | `--surface-3` (no animation) | `--surface-3` bg | — |
| **hover** (lowest) | `--surface-2` | `--surface-2` | label preview (hover ≠ commit) |
A row can be selected AND focused: selected wash + focus ring stack (ring on top). Hover never
overrides selected. This four-state table is itself an anti-AI move — generated UIs never
resolve it.

**Z-index scale (this is a layered app shell — needed before the first dialog):**
```
--z-base: 0; --z-map-overlay: 10; --z-docked: 20; --z-status-strip: 30;
--z-popover: 40; --z-dialog: 50; --z-shortcut-sheet: 55; --z-toast-alert: 60;
```

### 4.5 Motion — physical truth only (IBM Carbon Productive; short end)
```
--ease-standard: cubic-bezier(0.2, 0, 0.38, 0.9);  /* workhorse: pin move, re-sort       */
--ease-entrance: cubic-bezier(0,   0, 0.38, 0.9);  /* element entering                   */
--ease-exit:     cubic-bezier(0.2, 0, 1,    0.9);  /* element leaving                    */
--dur-micro:  90ms;   /* hover, toggle, chip                                    */
--dur-select: 140ms;  /* selection highlight across panes                      */
--dur-base:   200ms;  /* panel/content transitions                             */
--dur-pin:    400ms;  /* eased pin glide on coordinate refine (retarget mid-flight) */
--dur-enter:  340ms;  /* new confirmed survivor: gentle fade+scale, ONCE        */
--dur-cross:  120ms;  /* fresh↔coasting overlay + value crossfade               */
```
**Animate ONLY:** pin position refinement (eased glide, never teleport; if a new fix lands
mid-glide, RETARGET — never queue/stack); uncertainty radius tightening; selection highlight
across panes; hover affordance; fresh↔coasting overlay cross-fade; the liveness heartbeat; a
single tier-3 alert entry. **NEVER animate:** a coordinate/confidence/count *value* (crossfade
or snap — never tween a magnitude; a tweened number briefly displays a value it never was);
status color changes (instant — truth is instant); critical alerts (snap in at full salience —
a slow fade *delays* safety info); list re-sorts that move the selection out of view
(forbidden, §6.6); the video feed; anything decorative. **Zero ambient motion** — no breathing
glows, parallax, shimmer (trust-erosion + cognitive load over a long shift). Never `linear`
(except a determinate progress bar); never overshoot/bounce.
**`prefers-reduced-motion`:** pin glide → instant (or ~100ms fade); heartbeat → static dot;
alert blink → steady high-contrast state (still fully salient — WCAG 2.3.1/2.3.3).

### 4.6 Liveness heartbeat
A single calm ~2s opacity pulse (0.5↔1.0, `--ease-standard`) on one canonical status-strip
indicator, **bound to real frame arrival, not a CSS loop** — if the stream stops, the
heartbeat stops. BUT a frozen heartbeat is only *corroboration*: link-loss is signaled by a
**positive** failure indicator (strip slot → `--st-critical`, banner appears, §7.4), because
"absence of motion" is a poor primary alarm (looks like a pause for ~3-4s — forever in this
loop).

### 4.7 Alert escalation ladder (3 tiers — the alarm-fatigue contract; built in 5.7b)
Recall-first → a detection firehose → alarm fatigue is the systemic risk. The visual system
defines three tiers; **only tier 3 may glow or animate.**
1. **Ambient** — present in list/map, no motion, no glow, no sound. Most detections
   (candidates, CUE-ONLY) live here. CUE-ONLY posts silently.
2. **Attention** — a static accent (status color + glyph), still no motion/sound. Confirmed
   but not urgent.
3. **Alert** — `--alert-glow` + single entry animation + one rationed audio cue (§4.8).
   Reserved for confirmed high-priority PINPOINT/SWEEP. **Rate-limited/coalesced:** N
   contacts arriving within a short window → ONE "N new contacts" pulse, never N glows.
   **Acknowledge** quiets the glow (→ attention tier) WITHOUT requiring dispatch, so the
   operator can silence the board without being forced into premature action; unack count
   never silently resets.

### 4.8 Audio (the channel the eyes-on-video operator actually needs; rules here, built 5.7b)
A single, distinct, **rationed** audio cue for **tier-3 only**, following the same scarcity
as orange. No per-track repeat-chime; coalesced with the visual burst. Mutable, with a
visible mute-state indicator (mute is itself a never-hidden trust field).

---

## 5. Component → token mapping & the shadcn-vs-bespoke split

Records which components ride accessible primitives vs. are bespoke viz (impl-plan Task 5.0
Step 3). **shadcn MCP is NOT connected this session** (todo.md tooling status) → "primitive"
means a hand-built, accessible, token-driven component (focus ring, ARIA, keyboard nav) in
the role shadcn would fill; swappable to shadcn in v1.x without changing the token contract.

| Surface | Build as | Tooling |
| --- | --- | --- |
| Survivor **list/table** | Accessible primitive (sortable header, roving focus, ARIA grid) | hand-built to tokens; Magic MAY refine row/cell *within* tokens |
| **Contact detail / command panel** | Accessible primitive (one primary verb per state) | hand-built to tokens |
| **Dialogs / confirm** (clearance undo, manual-contact, `?` sheet) | Accessible primitive (focus-trap, ESC, ARIA) | hand-built to tokens |
| **Select / filter chips / toggles / layer toggles** | Accessible primitive | hand-built to tokens |
| **Status strip** | Bespoke readout row | hand-built |
| **Map + all overlays** (basemap, pins, sweep/area, coverage, track, footprint, clustering) | **Bespoke viz — MapLibre GL.** NO shadcn/Magic. | hand-built to tokens |
| **Video panel + canvas overlays** | **Bespoke — canvas/2D.** NO shadcn/Magic. | hand-built to tokens |
| **Mission log** | Bespoke append-only list | hand-built to tokens |

**Iconography:** one SVG set — **Lucide** (MIT, has crosshair/target, rewind/pause, GPS,
link/link-off, navigation glyphs) — plus a **custom SVG reticle** for the contact pin. No
literal-Unicode glyphs in shipped UI (the ASCII mocks in §7 use Unicode only as
placeholders). Status glyphs are the §6.5 designed shape alphabet, drawn from Lucide +
custom, NOT emoji-of-convenience.

**Magic MCP rule:** only to refine an *already-token-constrained* component (feed it §2–§4
tokens + §6 rules); never to invent aesthetic or generate map/video viz; never to add
"tactical" decoration (§6.10). Skip it where a component is trivial.

### 5.1 Pin & uncertainty visual language (bespoke map — the heart of the tool)
Cartography follows the figure-ground rule: **desaturated basemap recedes, data is the only
figure; warm = contacts, cool = context.**
- **Basemap:** grayscale land `#0e0e0e`–`#141414` (dark gray, NOT black — black swallows pin
  halos), water `#2C353C` (darker, recedes), roads mid-grays w/ dark casing, labels cool-gray
  with **dark** halos at ~50% (dark halos on a dark map; white halos jar). Low map-label
  density so pin labels win.
- **Pin = a target reticle** (echoes the logo crosshair; a teardrop is the #1 generic-map
  tell): center dot + thin ring, ring color = status token, 1–2px dark outline for pop on
  dark land, **screen-space constant size** (cluster at low zoom, never shrink below legible),
  position eased on refine.
- **Uncertainty = the EDGE carries the meaning:** low fill (0.08–0.15) + strong stroke
  (0.6–0.9) at the true `r95_m` (equal-coverage radius — DESIGN.md/P4), same hue as its pin
  so it reads as that pin's region, never a second object. Opacity maps to confidence
  (tighter/high-confidence ring slightly stronger; large/low-confidence fainter — honest
  uncertainty, never false precision). **PINPOINT** = tight reticle + small circle;
  **SWEEP/AREA** = real radius; **CUE-ONLY** = large dashed circle, NO center dot (we never
  claim a point we don't have). The expert ellipse (`semi_major/minor/orientation`) is a
  separate toggleable thin outline.
- **Coverage layer (the most important non-pin layer):** accumulated searched-area as a
  low-opacity (fill 0.12–0.20) cool low-chroma wash, **union/dissolved into one geometry
  before render** (never stack per-pass polygons — alpha compounds to mud). At most one large
  translucent fill is "loud" at a time.
- **Z-order (MapLibre, symbols last):** basemap → coverage fill → coverage outline →
  uncertainty → track/footprint → pins → labels. (A point estimate sits *above* its own
  fuzzy region; contacts above all geometry; labels top.)
- **At scale:** filled rings only for selected/confirmed; the rest collapse to graded dots;
  cluster at low zoom; two-tier labels (Full Data Block for confirmed/selected vs Limited
  Data Block — dot+ID — for the rest); one-action "reset to standard view."

### 5.2 Confidence encoding (glance-ability — two raw decimals are NOT scannable)
The list shows **det and loc confidence as two short horizontal micro-bars** (banded fill:
low/med/high), `--st`-tinted, pre-attentively comparable down a column. The **exact numeric
0.00–1.00 value lives only in the detail panel** (§7.3), where precision matters and there's
one. The two axes are NEVER merged (a high-detection / low-localization contact is a real,
important state — that gap is a never-hidden trust field, §6.8).

---

## 6. The anti-AI-slop ruleset (the contract that wins "doesn't look AI-generated")

Testable rules, not vibes. 5.12 audits against them. Each notes how it's checked.

1. **No default shadows/gradients as chrome.** Elevation = surface step + hairline. Gradients
   only in map coverage + uncertainty fills (data). *Check:* grep — any `box-shadow` outside
   `--ring-focus` / `--ring-selected` / `--alert-glow` is a bug; any chrome `background:
   linear-gradient` is a bug.
2. **Tabular mono for all data.** Every coord/ID/conf/age/radius/timestamp in `--font-mono`
   with tabular figures + slashed zero. *Check:* assert `font-variant-numeric`/`font-mono`
   class on data nodes; a reflowing column is a bug.
3. **One canonical format PER ROLE, used identically everywhere.** Coordinates have TWO
   roles, both required (§6.3a): grid (MGRS/USNG) and geographic (WGS84). One time format,
   one distance unit (meters). *Check:* single formatter function per role; lint for raw
   coordinate/number strings in components. (This replaces the draft's wrong "two formats =
   bug" — see §6.3a.)
4. **Status is a closed state-machine, ONE encoding** across pin/row/panel/strip, each backed
   by a §6.5 glyph. Same state ≠ two colors in two places. *Check:* one `statusToken(state)`
   map; Playwright asserts the same token+glyph in all three surfaces for a given state.
5. **Eased pin motion, never teleport; never animate a value.** Position glides (retarget
   mid-flight); numbers crossfade/snap; colors switch instantly. *Check:* pin uses transform
   transition; no `transition` on text nodes carrying values.
6. **No scroll-yank re-sorts; the selected object never silently leaves the viewport.**
   *Check:* Playwright — after a data update/re-sort, the selected row's bounding box stays in
   view.
7. **Designed empty / loading / error / link-lost / no-fix states.** No bare spinners, no
   blank panels. "No contacts yet," "Connecting to service," "LINK LOST — frozen frame,"
   "No fix (CUE-ONLY)" are each intentionally drawn. *Check:* each state has a named component
   with copy; a spinner-on-blank is a bug.
8. **Never hide a trust field.** A `REQUIRED_TRUST_FIELDS` list is load-bearing: link-state,
   telemetry-age, det-conf, loc-conf, confidence GAP, age, dispatch-delta, heading-limited,
   altitude datum, audio-mute-state. *Check:* Playwright asserts each is present+visible in
   the contact panel for every contact state. (Cleanliness never beats honesty.)
9. **Keyboard-first.** Every primary action has a key; `?` opens a shortcut sheet; visible
   `--ring-focus` on every focusable; roving tabindex in the list. *Check:* Playwright drives
   the core loop by keyboard only.
10. **Forbid AI/ops-cosplay clichés BY NAME.** No scan-lines, CRT glow/curvature, glowing
    corner brackets, animated radar sweeps, hexagon-grid backgrounds, "tactical HUD"
    ornament, grain/noise overlays, parallax, custom cursors (cursor ∈
    {default,pointer,crosshair,text} only), diagonal/tilted layout containers
    (`transform: rotate()` forbidden on layout). *Check:* grep for noise/grain assets,
    `rotate(`, exotic `cursor`. This is the part of the generic "make it look techy" instinct
    we explicitly REFUSE — for a life-safety instrument, ornament reads as untrustworthy.
11. **Min hit targets (§4.2).** Primary verbs ≥40px, controls ≥32px, rows ≥34px. *Check:*
    Playwright measures bounding boxes of interactive elements.

### 6.3a Coordinate format (CORRECTED domain rule — replaces "one format only")
US ground SAR runs on **USNG/MGRS** (FEMA's national incident grid; the CalTopo/SARTopo
ecosystem teams actually field), and grid is far more **radio-robust** than decimal degrees
(digit-pairing makes a dropped digit self-evident; no hemisphere signs to flip). Air assets
(helicopter/Coast Guard) navigate by **lat/long, spoken as degrees-decimal-minutes (DDM)**.
HADES therefore shows **two canonical formats, by role, in fixed labeled positions:**
- **Primary (headline, largest):** MGRS/USNG — the ground-team dispatch coordinate.
- **Secondary (labeled line):** WGS84 lat/lon in **DDM** for the spoken/air form, plus the
  **datum tag** (e.g. `WGS84 · HAE`) — always shown (never-hidden trust field).
The forbidden thing is the *same role* appearing in two formats in two places — not showing
both roles. Both are tabular mono, fixed precision, radio-speakable.

### 6.5 Status-glyph alphabet (the CVD/glare backup — a designed shape set, not emoji)
A distinct shape per status so the non-color channel is a real alphabet. Drawn from Lucide +
custom; warning vs critical are maximally distinct shapes (glare survival):
```
nominal  ● filled disc        info     ◆ filled diamond / "i"
caution  ▲ triangle           warning  ◉ filled target/reticle (world-urgency, survivor)
critical ■ filled square + !  stale    ◌ dashed hollow ring (+ de-render/hatch on rows)
```
CUE-ONLY (never-had-a-fix) uses the stale dashed ring with NO center; a decayed-but-real fix
uses a filled status glyph dimmed — color shared, shape/treatment distinct.

---

## 7. Reference mockups (the five key views)

ASCII reference layouts fix the *structure*; pixel craft is verified against tokens at 5.12.
Glyphs here are placeholders for the §6.5 Lucide/custom set.

### 7.1 App shell — fixed grid (map primary, list rail, video docked, log foot)
```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ● LINK OK   ◆ TEL 0.3s   ⊕ GPS 3D·11   FPS 30/det 12   ⏱ 14:22:07Z      ♥     │  status strip (--strip-h)
├───────────────┬──────────────────────────────────────────────┬───────────────┤
│ CONTACTS      │                                              │  VIDEO        │
│ (list rail)   │                                              │ (docked,      │
│ ◉ 042 ▮▮▮▯ ▮▯ │              MAP  (primary, the app)          │ selection-    │
│ ▲ 037 ▮▮▯▯ ▮▮ │   desat basemap · reticle pins · uncertainty │ bound, 16:9)  │
│ ◌ 019 ▮▯▯▯ ─  │   edges · coverage wash · drone track ·      │ ┌───────────┐ │
│   …           │   camera footprint · cluster · reset-view    │ │frame+box  │ │
│ [filter ⌄]    │                                              │ │● FRESH    │ │
│ [reset view]  │                                              │ └───────────┘ │
├───────────────┴──────────────────────────────────────────────┴───────────────┤
│ MISSION LOG ▾  14:22:01 trk042 NEW PINPOINT · 14:21:54 trk037 dispatched · …   │  append-only drawer
└──────────────────────────────────────────────────────────────────────────────┘
  Splitter-resizable between regions (enforced min sizes) + full-screen toggle for map/video.
  Min window 1280×800. The ONLY reconfiguration is splitters + full-screen + declutter/layers.
```

### 7.2 Survivor list row (tabular, status-glyph anchor, confidence as micro-bars)
```
 GLYPH│ TRK │ CLS    │ DET    │ LOC    │ CLR    │ AGE  │ CONV │ HDG
 ──────────────────────────────────────────────────────────────────
 ◉ war│ 042 │ person │ ▮▮▮▯   │ ▮▮▯▯   │ NEW    │ 0:03 │ STBL │ ⚠HL
 ▲ cau│ 037 │ person │ ▮▮▯▯   │ ▮▮▮▯   │ ASSGND │ 0:41 │ CONV │ —
 ◌ stl│ 019 │ person │ ▮▯▯▯   │  ─     │ CUE    │ 2:18 │  —   │ ⚠HL   (row de-rendered/hatched)
   det & loc are SEPARATE micro-bars (numbers live in the panel) · all mono tabular ·
   default sort = actionability (NEW high-priority → top) · cleared rows demote (never vanish) ·
   selected row stays in view across re-sort
```

### 7.3 Contact detail / command panel (one primary verb per state; numbers live here)
```
┌── CONTACT trk 042 ───────────────────────────[ × ]┐
│ ◉ PINPOINT          DET 0.94  ▮▮▮▯   LOC 0.71 ▮▮▯▯ │  two conf axes: bar + exact value, never merged
│                                                   │
│ 16R FU 1234 5678                  (MGRS · 10 m)   │  PRIMARY: grid, headline, --text-xl mono
│ N30 12.892  W088 31.262           (WGS84 DDM·HAE) │  SECONDARY: lat/lon DDM + datum, labeled
│                                                   │
│ R95  18 m   SWEEP-grade           ▢ ellipse       │  honest radius; expert ellipse toggle
│ age 0:03 · STABLE · ⚠ heading-limited             │  never-hidden trust fields
│ ┌───────────────────────────────────────────────┐│
│ │            ▸ DISPATCH                          ││  one primary verb (≥40px); reversible
│ └───────────────────────────────────────────────┘│
│   ↺ undo      ⤴ promote→fuse      ⌖ snapshot      │
└───────────────────────────────────────────────────┘
```

### 7.4 Status strip (always-on; orange≠system, magenta=system per P0)
```
 ● LINK OK         ◆ TEL 0.3s            ⊕ GPS 3D·11sv        ⏱ 14:22:07Z        ♥
 (nominal teal)    (caution amber aging) (info/caution by fix) (mono UTC)        (heartbeat, frame-bound)
 — LINK LOST → link slot flips to --st-CRITICAL (magenta) + "LINK LOST" banner + heartbeat freezes —
 — note: link-lost is a SYSTEM failure (magenta), NOT the survivor-orange. They never share a hue. —
```

### 7.5 Video panel (overlays + honest link state)
```
┌── VIDEO · trk 042 selected ───────────────┐
│  ┌───────────────────────────────────────┐│
│  │   [frame painted to canvas]           ││
│  │      ┌────┐ 042                        ││  box overlay aligned by frame_id
│  │      │ ▢  │ DET 0.94                   ││  overlay: ID + both confidences
│  │      └────┘                            ││
│  │   ● FRESH                              ││  fresh vs coasting distinct
│  └───────────────────────────────────────┘│
│  ⏮ rewind  ⏸ pause   ⌖ snapshot   ✛ manual │  rolling buffer · manual contact (AI-miss backstop)
│  — LINK LOST → frozen frame dimmed + "LINK LOST / FROZEN" banner; never looks live —       │
└────────────────────────────────────────────┘
```

---

## 8. Layout & limit behavior
- **Fixed splitter-resizable grid** (every C2 reference converges on fixed, not draggable —
  draggable geometry is a solo-maintenance/QA sink and not what operators tune). Operators
  tune *information density / layers / declutter*, not panel geometry. Min window 1280×800;
  `BrowserWindow.minWidth/minHeight` enforce it; full-screen toggle for map and video.
- **At the limit (the part that defines an instrument):** list **virtualizes** past ~50 rows;
  map **clusters** pins at low zoom and collapses non-selected uncertainty rings to dots;
  coverage is union-dissolved; a coordinate that won't fit truncates the *label*, never the
  panel value. Silent caps are forbidden — if the view declutters, it says so.

## 9. Implementation contract (locks plumbing so 12 TDD tasks can't drift)
### 9.1 Tailwind ← tokens
Tokens authored as RGB channels in `:root` (`src/styles/tokens.css`). `tailwind.config.ts`
`theme.extend` maps each to `rgb(var(--token) / <alpha-value>)` for colors, and `var(--sp-*)`,
`var(--radius-*)`, `var(--text-*)`, `var(--font-*)` for the rest. Components use **utilities**
(`bg-surface-1`, `text-text-hi`, `font-mono`), not arbitrary `[var(--x)]` values (which bypass
the scale and invite off-token drift §6 forbids). Multi-layer box-shadows (`--ring-*`,
`--alert-glow`) ship as a small `boxShadow` extend / utility classes.
### 9.2 Offline fonts
`@fontsource/b612` + `@fontsource/b612-mono` (or IBM Plex Sans/Mono fallbacks via
`@fontsource`), imported in the renderer entry; Vite fingerprints+bundles the woff2 → zero
runtime network (hard offline constraint, by construction). **`vite.config` MUST set
`base: './'`** or packaged-app `file://` font URLs 404 silently → system-ui fallback (the
failure §3 forbids). Bundle only weights §3.2 names (16 GB Air target).
### 9.3 Scrollbars
Thin custom `::-webkit-scrollbar` (Chromium/Electron): 8px track transparent, thumb
`--surface-3` → `--surface-4` on hover, `--radius-pill`. Default OS scrollbars on the dark
dense lists read as "unfinished" and break the aesthetic.

## 10. Open items folded at lock (record)
### 10.1 Design-review closure (Task 5.12 — flagship close)
Final audit of the RUNNING UI (screenshots in `docs/assets/p5/`) by an adversarial
"does this look AI-generated?" lens + a judgment pass against these tokens. Chrome DevTools
MCP / shadcn MCP / Web Guidelines + gstack `/design-review`+`/qa` were NOT connected this
session (tooling gap, per `ui-design-tooling` memory → proceeded with screenshots + judgment +
adversarial panel; gstack live-UI review deferred to when those tools are available).
**Findings triaged → fixed:** panel confidence bars now show the exact numeral beside the bar
(§5.2/§7.3); heartbeat dot → teal nominal (was blue — a status-encoding slip, §4.6); detail
command block separates the clearance STATUS line from the verb row (killed the "fourth button"
ambiguity); map auto-fits the viewport to the data ONCE on first appearance so the scene
composes (was scattering pins in dead space); FRESH chip got a background for contrast.
**Findings rejected with reason:** `REL_TAKEOFF` datum is CORRECT for the `.srt` validation
path (DESIGN.md §3.5 — forcing HAE/MSL would fabricate a tag); the "2 new" vs 3-log-events
"mismatch" is the alarm-fatigue design working (CUE_ONLY posts silently, §4.7).
**Logged v1.x:** coverage union-dissolve (simple accumulation now); real video feed + PMTiles
basemap tiles (P6); software-GL banding is a headless-render artifact, not a product defect.

### 10.2 Open items folded at the 5.0 lock (history)
All four adversarial lenses + the research brief folded. Resolved at gate: chrome
neutralized (was navy/cobalt — the top AI tell); mono → IBM Plex Mono (was JetBrains, a
tell); UI → B612 (cockpit provenance, was the safer Archivo); orange/magenta life-safety
split (P0); `--text-lo` contrast fixed; redundant tokens removed; coordinate format
corrected to MGRS-primary/WGS84-DDM-secondary (domain); confidence → micro-bars; added
hit-targets, state matrix, z-index, status-glyph alphabet, icon set, alert ladder/ack/audio,
day-palette architecture, Tailwind/font/scrollbar contracts. Deferred to v1.x (recorded, not
load-bearing): day-palette components, label de-confliction force-layout, compact/comfortable
density modes. **Remaining gate verification → 5.12:** paste the on-screen measured contrast
table; confirm glyph set is CVD-distinct as shapes; confirm basemap legibility under load.
```

---

## 11. Multi-page shell (UI-overhaul Stage 3 — LOCKED)

> The single-screen Operations view is no longer the whole app — it's the primary mode of a
> small instrument console. **The map IS still the application (§0); the shell must not demote
> it to one tab among four.** The nav is a thin *mode-switcher* (a console rail), NOT a CRUD
> admin sidebar with a content pane beside it. This survived the simplicity + slop lenses on
> the explicit condition that it reads as instrument modes, not a SaaS sitemap.

### 11.1 The console rail (persistent left nav)
- A **narrow vertical rail** (`--surface-1`, hairline-right), full height, below the status
  strip. Each item = a lucide glyph + a short **mono** label (`OPS`, `REVIEW`, `MAP`, `SET`),
  not sentence-case product names. The active item carries the **steel accent bar** (the same
  selection primitive as a contact row — one selection language everywhere).
- Width is fixed (`--rail-w: 56px` collapsed-icon / optional labelled at `148px`); it never
  steals map width meaningfully. No logo lockup, no avatar, no "upgrade" footer — the anti-CRUD
  rule. The rail is bound to system state (a page with an unacked alert shows the alert glyph).

### 11.2 The page set (four modes)
| Mode | What it is | Why it earns a mode (not a dialog) |
|---|---|---|
| **OPS** (Operations) | the live instrument: status strip · contact rail · map · video · log. The retrofitted current view. | the running mission; default landing. |
| **REVIEW** (Mission Review / Contacts) | a roomy full-page contact manager: sortable/filterable data-table + detail + one-click reversible clearance workflow + mission timeline. | post-mission triage/audit is a genuinely different task from live ops — needs room the rail can't give. |
| **MAP** (Map / Playback) | map-dominant: full-bleed survivor map, coverage layers, timeline scrub/replay, measure tool. | the map deserves a full-screen analytical mode (the existing fullscreen toggle, promoted). |
| **SET** (Settings + Docs) | sensor-error config, confirmation thresholds, basemap/AO selection, **the day/night theme toggle**, demo-vs-live; Docs renders the shared P7 markdown (one source). | config + reference; lowest-frequency, correctly last. |

### 11.3 The selection spine survives navigation (the Lattice lesson, §0)
One `Contact`, the same `selectedId` store, across every mode. Select trk 042 on OPS → switch
to REVIEW → it's still the focused row; → MAP → it's the framed pin. Selection is global state,
never per-page. This is the one cross-page invariant the multi-page split must preserve — it's
*why* the split is safe (the operator never loses their contact when changing mode).

### 11.4 Page chrome consistency
The status strip + demo banner are **above** the rail and persist on every page (link state and
demo provenance are never mode-specific — a P0 concern). Each page owns only the region right of
the rail and below the strip. No page re-implements the strip, the clock, or the theme.

---

## 12. Map on LIGHT (Stage 4 retune — data layers were tuned for dark land)

The §5.1 cartography opacities assumed dark land; on the Day basemap they wash out. Locked
retune (the "edge carries the meaning" doctrine is *more* true on light):
- **Basemap:** the light Protomaps theme (light land, slightly-cooler water, faint roads) so
  pins/rings/coverage stay the only saturated marks. (The flat fallback's `LAND/WATER` hexes get
  a light-mode pair.)
- **Coverage:** lead with a crisp dissolved **outline** + raise fill alpha (~0.18–0.25) or hatch;
  a 0.10 cool wash is invisible on paper.
- **Uncertainty rings:** drop fill toward ~0, let the **stroke** carry it.
- **Drone track:** add a thin dark casing OR darken to `--blue-core` — cool blue vanishes on cool
  paper.
- **Pins:** the dark outline still pops on light land (safest layer); swap any white halo for a
  subtle dark/translucent ring.
- **Label halos:** flip dark→light (white/light halo around dark label text).
