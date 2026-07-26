# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This repo is named `bobberdolle1`, matching the GitHub username — GitHub renders its `README.md` directly on the user's profile page (github.com/bobberdolle1). The profile is a generated art piece: a PS2-boot / PS3-XMB inspired scene (cold blue-white light in a black void, no console-UI literalism) built entirely from SVGs that `generate_assets.js` renders from live GitHub data. Edits to the profile's look belong in `generate_assets.js`, not in the SVGs (they are overwritten every 6 hours by CI) and mostly not in `README.md` (its card grid section is also generated).

There is no test suite; `node generate_assets.js` (with `GITHUB_TOKEN` set) is the whole build.

## Structure

- `generate_assets.js` — the single source of truth for the profile's look. Fetches repos/user/contribution-calendar/language bytes (REST + GraphQL) and commit timestamps (GraphQL history walk), then writes every SVG in `assets/` and rewrites the clickable project-card grid in `README.md` between the `<!-- projects:start -->` / `<!-- projects:end -->` markers. Decorative randomness (dust, beam flicker) is seeded via `mulberry32` so identical data produces byte-identical files. Every animation must keep a fully visible resting state (GitHub may render frame 0 only) and be listed in the shared `prefers-reduced-motion` block.
- `README.md` — mostly a stack of `<img>` blocks pointing at `assets/*.svg`; only the footer tagline and block order are hand-edited. The card grid between the projects markers is machine-written — never edit it by hand.
- `assets/` — generated output only (header, towers, signal, telemetry, label-work, card-0..5, link chips). Never hand-edit.
- `.github/workflows/generate.yml` — cron (every 6h) + push-triggered Action that runs the generator and commits `assets/` and `README.md` when the data changed.
- `termvibes/vibes.py` — standalone, dependency-free Python 3 script: a terminal ANSI/ASCII animation toy (matrix rain, fire, plasma, starfield, DVD-bounce logo). Single file, no package structure; not imported by anything else in the repo.

## Design rules for the profile SVGs

- Palette is strict: `#cfeeff` / `#7fd4ff` / `#1d6fb8` / `#0a2c55` on near-black. No magenta/synthwave pink (tried, rejected); no brand colors (shields.io badges were removed for this reason).
- The towers block is the page's only loud element and its only large number. New blocks must stay quiet: thin strokes, mono captions, one idea each.
- No literal console UI: no menus, memory cards, crossbars, HUD chrome.

## Working with termvibes/vibes.py

Run it directly — no dependencies beyond the Python 3 standard library (`termios`/`tty`, so it needs a real TTY, not a piped/non-interactive shell):

```bash
python3 termvibes/vibes.py
```

Keys: `1`-`5` switch effects (matrix/fire/plasma/starfield/dvd), `space` pauses, `q`/Ctrl-C quits.

Each effect is a small self-contained class in `EFFECTS` with `__init__(w, h)`, `resize(w, h)`, and `frame(t) -> rows` (a `[[(char, (r,g,b) or None), ...]]` grid). `render_rows` collapses a frame into one escape-coded string, only emitting a new `\x1b[38;2;r;g;bm` when the color actually changes. Adding a new effect means adding a class with that interface and registering it in `EFFECTS`.

To sanity-check syntax without a TTY:

```bash
python3 -m py_compile termvibes/vibes.py
```
