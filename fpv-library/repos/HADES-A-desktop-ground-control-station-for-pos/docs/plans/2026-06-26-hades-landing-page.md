# HADES Landing / Demonstration Site — Blueprint

> A front-facing **demonstration** site for HADES, in the CuboCruise aesthetic (clean white,
> huge restrained display type, maximal whitespace, rounded image cards, one black moment).
> NOT a hardware-sales page — it *presents and demonstrates* the SAR system and leads into the
> live demo. Reverse-engineered from cubocruise.com (screenshots: docs/plans/_investigation/
> reference/cubo-*.png).

## Reverse-engineered Cubo DNA (the rules we adopt)
- **Palette:** `#FFFFFF` primary bg · `#F7F7F7` alternating section bg · `#000000` for the hero
  product zone, the CTA pill, and the footer block (the single dark moment). Black text on white.
- **Type scale:** display H1 ≈ **96–120px / 700** (one giant word/phrase per hero), section H2
  **48px / 600**, body **16px / 400**, small-caps labels. Generous line-height.
- **CTA:** a **full-pill** button (`radius 999px`), black bg / white text, arrow suffix ("Demo →").
- **Layout DNA:** huge whitespace; one idea per section; product shot floats centered with air;
  rounded (16–20px) image cards; a right-side vertical word-nav in the hero; sticky product
  image beside the FAQ accordion; big black footer with an oversized headline + link columns.
- **Motion (implied):** quiet scroll-reveal (fade/translate-up as sections enter), smooth.

## HADES adaptations (the "few HADES touches")
- **Display font = B612** (the cockpit face already bundled) instead of Cubo's Inter — keeps the
  clean feel but is distinctive + ties to the app. Body = IBM Plex Sans. **Mono = IBM Plex Mono
  for the real metric numbers** (mAP, meters, fps) — the one place HADES's instrument character
  shows through.
- **Accent = survivor-orange** (`#E8531F`/`#D03E10`), used VERY sparingly (one word, the live
  dot, a link hover) — the HADES signal color, the rest stays black/white like Cubo.
- **Hero visual = HADES_logo.png** for now (placeholder for a real product/drone shot later),
  floating on the dark hero zone like Cubo's device.
- **Content = demonstration, not sales.** Real numbers only (honest, per HADES rules).

## Section plan (top → bottom)
1. **Hero** — white; giant "HADES" display word; the logo floating center on a dark rounded
   panel; a one-line what-it-is; right-side word-nav (Detect / Localize / Coordinate / Offline);
   a black pill CTA "See the live demo →" (→ the existing P6 demo site / embedded).
2. **What it is** — one big H2 + a restrained paragraph: post-hurricane SAR ground-control;
   ingest FPV drone video → detect survivors → real-world coordinates → live map.
3. **The pipeline** — 3–4 rounded cards (Detect · Localize · Coordinate · Offline-by-design),
   each a short title + line. (Cubo's feature rhythm.)
4. **Proof / metrics** — the real validated numbers as big mono figures (detection mAP on HERIDAL,
   localization error in meters, live fps, glass-to-glass latency). Honest, sourced.
5. **See it in action** — a 2-up "on the news"-style card row: a detection-overlay still + an
   app screenshot, linking to the live demo. (Mirrors Cubo's detection-overlay image.)
6. **FAQ** — accordion (what is it / does it work offline / how accurate / what hardware /
   privacy) beside a sticky logo/product image.
7. **Footer** — the black block: oversized "Find them faster." headline + link columns (Demo,
   Docs, GitHub) + honest project provenance line.

## Build
- New route in the SAME vite app under `--mode web` is wrong (that's the demo). Build the landing
  as its own lightweight surface: `ui/src/landing/` with its own entry, OR a separate minimal
  static page. DECISION: a self-contained React page (`landing/LandingPage.tsx`) rendered at a
  distinct build target so it stays decoupled from the operational app bundle. Reuses the design
  tokens for color/type but has its OWN marketing layout (not the console).
- Scroll-reveal via IntersectionObserver + CSS (no heavy animation lib; offline-safe).
- Verify with Playwright (sections render, CTA links, accordion opens) + screenshot iterate
  against the Cubo reference (min 2 passes), per the anti-AI-slop method.
