# CLAUDE.md — working notes for fpv-sim

Single-file browser sim of an FPV sUAS vs counter-UAS engagement, plus its
evidence: a Monte Carlo study, a results dashboard, and generated docs.
All data is notional. Start with README.md; deep docs: DESIGN_NOTES.md,
DEVELOPMENT_HISTORY.md, MONTE_CARLO.md, PARAMETERS.md, CHANGELOG.md.

## The one invariant that matters

**Same-seed determinism is this project's API.** The sibling repo
[fpv-sim-mcp](https://github.com/wasomma/fpv-sim-mcp) contains a TypeScript
port of the simulation core in `index.html` (lines ~218–999: `CONFIG`
through `stepSim()`), with parity proven by golden-master fixtures
generated FROM this file. Consequences:

- Any edit that changes engagement outcomes for a given seed is a
  **breaking change**: it invalidates fpv-sim-mcp's fixtures AND the
  committed `results/` datasets. Flag it "Behavior-changing" in
  CHANGELOG.md, regenerate fixtures there (`npm run goldens`), update its
  `docs/upstream/SNAPSHOT.md`, and rerun the study here.
- UI-only edits are safe but must not touch the RNG draw order, and the
  whole `<script>` block must still *load* headlessly: fpv-sim-mcp's
  fixture generator runs it in a Node vm with only `document`/`window`
  (inert proxies), `performance`, `console` — no `location`,
  `URLSearchParams`, etc. Guard browser-only APIs with try/catch (see the
  deep-link init code for the pattern). fpv-sim-mcp's weekly
  `upstream-drift` workflow catches violations after the fact; testing
  `npm run goldens` there before merging catches them before.

## Layout

- `index.html` — the entire sim application (zero deps, GitHub Pages
  serves it at the root URL). Supports `?seed=<n>&play=1` deep links.
- `dashboard.html` — companion results viewer, equally single-file; reads
  `results/index.json` (manifest) and the datasets it lists.
- `scripts/monte-carlo-study.mjs` — the canonical study runner (the four
  experiments). `--quick` for a 1/10-scale smoke pass (~4 min); full run
  ~25 min, 22,800 engagements. Writes `results/monte-carlo.json`,
  `kind:"study"`.
- `scripts/run-sweep.mjs` — ad-hoc single-sweep runner: `--label` (req),
  `--start`, `--count`, `--overrides` (JSON). Writes an
  `adhoc-<slug>-<date>.json` dataset, `kind:"adhoc"`, and registers it.
  The dashboard prefixes these AD-HOC and offers a STUDY/AD-HOC filter;
  ad-hoc datasets carry only a `baseline` sweep, so the dashboard's dose
  and paired cards render only when those experiments exist.
- `scripts/sweep-utils.mjs` — shared helpers (engine load, Wilson CIs,
  histograms, manifest upsert) both runners use, so they can't drift.
- `scripts/generate-parameters-doc.mjs` — regenerates PARAMETERS.md.
- `results/` — committed datasets + manifest (`index.json`; each entry
  has a `kind` and `label`). Quick-run output (`monte-carlo-quick.json`)
  is a dev artifact, gitignored and never registered. Retire an ad-hoc
  dataset by deleting its file and its manifest entry.

Both scripts import the **built** engine from a fpv-sim-mcp checkout:
sibling directory `../fpv-sim-mcp` by default, or `$FPV_SIM_MCP`. Build it
there first (`npm install && npm test`). Do not reimplement the engine
here — index.html is the spec, fpv-sim-mcp is the verified headless twin.

## Conventions

- CHANGELOG.md: Keep a Changelog + semver; accumulate under
  `[Unreleased]`, roll into a version on release. Compare links currently
  use commit SHAs (tags pending — see open issues).
- Dashboard chart colors are the sim's hues darkened to pass CVD/contrast
  validation on the dark surface (see the `:root` comment in
  dashboard.html); the sim's original brighter hues are for chrome only.
- GitHub Pages auto-deploys `main`; auto-delete of merged branches is on.
- Scheduled workflows (in fpv-sim-mcp) pause after ~60 days of repo
  inactivity — GitHub emails a one-click re-enable.

## Open work

Check the repo's open issues first — outstanding owner actions (version
tags/releases, etc.) are tracked there, not in this file.
