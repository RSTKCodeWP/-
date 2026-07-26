# HADES Light Operations Theme — CANDIDATE (for adversarial panel)

Context: HADES is a post-hurricane SAR ground-control station (ATAK/ECDIS/Bloomberg/Anduril
lineage). The existing P5 design system is LOCKED and excellent: B612 (Airbus cockpit
typeface) + IBM Plex Mono, neutral chrome, a closed CVD-safe status palette where
orange=survivor-world-urgency and magenta=system-failure (a hard P0 life-safety split),
tabular numerals everywhere, flat hairline elevation (no shadows). v1 shipped the NIGHT
(dark) palette; a `[data-theme="day"]` stub awaits.

The UI overhaul flips the OPERATIONS theme to LIGHT (the bright end) as the strongest
anti-"AI-dark-dashboard" move, and turns the single screen into a multi-page product. We
are NOT redesigning type/status-semantics/grid/elevation — only (a) the chrome palette
Night→Day, and (b) adding the multi-page shell.

## The candidate LIGHT palette (WCAG-computed, not eyeballed)

Philosophy: a precision-instrument LIGHT chart — cool off-white "paper", NOT pure white
(#fff glares in a field tent and reads as generic SaaS). Raised surfaces step LIGHTER
(paper-on-desk), dialogs float to pure white. Cool near-black ink. Chroma still lives in
data, not chrome.

Canvas/surfaces:
- bg-void #DEE2E8 · bg-base #EAEDF2 (cool off-white paper) · surface-1 #F7F9FC (raised) ·
  surface-2 #EEF1F6 (hover/wells) · surface-3 #DEE6F1 (selected wash, faint blue) ·
  surface-4 #FFFFFF (dialogs) · hairline #C5CDD9 (cool gray)

Text (all clear WCAG AA, hi/mid clear AAA):
- text-hi #151C28 (14.56:1 on base) · text-mid #424D5E (7.29:1) · text-lo #626F83 (4.34:1) ·
  text-disabled #9EA8B6 · text-on-accent #FFFFFF

Structural blue (on light): blue-core #1C64B4 (5.07:1) · blue-bright #2D78CD · blue-track #4682C8

Status (luminance-rechecked for light; nominal/info/caution DEEPENED so both ink-on-paper
≥3:1 AND white-on-fill chip text ≥4.5:1):
- st-nominal #117449 · st-info #0F768E · st-caution #96610C · st-warning #D24012 (survivor) ·
  st-critical #CA1850 (system failure) · st-stale #68628C (off-ramp violet-slate)

Map basemap also flips: light Protomaps theme (light land, slightly-cooler water, faint
roads) so colored detection pins/rings/coverage remain the only saturated marks.

## Multi-page shell (the scope addition)
Persistent left nav (icon+label), 4 pages: Operations (live, the retrofitted current view) ·
Mission Review/Contacts (roomy data-table + detail + clearance workflow + timeline) · Map/
Playback (full-screen map, coverage, scrub/replay, measure) · Settings+Docs. A global
selection spine (one Contact, three projections) survives navigation.

## The anti-slop KILL-LIST (carried from P5, must stay absent on light)
No Inter/Roboto/system-ui (we use B612+Plex Mono) · no generic purple/blue gradient ·
no default Tailwind/Material drop-shadow (flat hairline elevation) · no perfectly-centered
hero · no emoji icons (lucide only) · no three-equal-cards row · no "clean & modern" as a
non-decision · no pure-white #fff canvas · chroma only in data, never chrome.
