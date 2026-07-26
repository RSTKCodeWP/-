# FPV sUAS vs cUAS — Force-on-Force Demonstration

**Live demo: https://wasomma.github.io/fpv-sim/** ·
**Results dashboard: https://wasomma.github.io/fpv-sim/dashboard.html**

A single-file, zero-dependency interactive simulation of a force-on-force engagement
between two teams, each fielding an armed FPV small-UAS (sUAS) and a pair of
counter-UAS (cUAS) radio-frequency direction-finding nodes. Everything — terrain,
RF propagation, DF geolocation math, drone behavior, and rendering — lives in one
HTML file (`index.html`) with no external libraries, build step, or server.

All data is **notional**. The banner says it and it's true: the area of operations
("AO KATANA"), unit positions, sensor parameters, and outcomes are invented for
demonstration purposes. Unclassified throughout.

## Why this exists

This was built as a lightweight, shareable demonstration piece for customer
conversations about small-UAS and counter-UAS training. The customer's sUAS/cUAS
community of interest wanted to see how the *detect → fix → commit → strike*
timeline plays out when two sides hunt each other's ground control stations by
their RF emissions — and, critically, how **emissions discipline (EMCON)**
changes who wins. A browser tab that anyone can open beats a slide deck for
making that point.

The core lesson the sim dramatizes: **the side that transmits less is harder to
fix.** Both teams have identical hardware. The only meaningful asymmetry is
EMCON posture — one side keys its C2 uplink intermittently and its video
downlink in short bursts; the other transmits nearly continuously. Run the
featured scenarios and watch which ground control station dies first.

## In plain English

No radio or simulation background needed — this is the whole thing:

Two teams each field an attack drone and radio-listening gear, and hunt
each other's control stations. The catch: every time your equipment
transmits, the enemy's listening posts get a rough bearing on where the
signal came from. Enough bearings, and they can pinpoint your control
station and send their drone to destroy it. So the game is a race — find
the enemy before they find you — and the core lesson is that **the team
that talks less on the radio is harder to find, and usually wins.**

The demo's featured scenarios show that lesson in single battles — but
hand-picked examples are a highlight reel, and a fair skeptic can ask
whether the games were picked because the idea looks good in them. So the
claim was put to a real test: the same battle played **22,800 times**
automatically, counting who wins. The results, in
**[MONTE_CARLO.md](MONTE_CARLO.md)**:

- Played as shipped, the disciplined team wins 37% of battles, the chatty
  team 26%, and 37% are draws where neither side ever finds the other —
  about 3 wins for every 2 of the loud team's.
- Give both teams the same radio discipline and the fight goes dead even;
  swap the two teams' radio habits and the advantage swaps with them.
  Whoever talks less wins more, regardless of which team it is.
- The more a team transmits, the more it loses — smoothly, like a dial,
  not a coin flip.
- One team's drone launches 6 seconds earlier, and that head start turns
  out to matter not at all. Radio discipline explains essentially the
  entire gap.

And because every battle is exactly repeatable from its seed number,
anyone can rerun the same 22,800 battles and get the same numbers — the
results are checkable, not "trust me."

## Quick start

Open the [live demo](https://wasomma.github.io/fpv-sim/) or just open
`index.html` in any modern browser. Press **Play**.

| Control | What it does |
|---|---|
| Play / Reset | Start, pause, or restart the current engagement |
| 1x / 2x / 4x / 8x | Playback speed (simulation steps at fixed 0.1 s physics ticks) |
| RF Coverage | Dashed rings showing each DF node's maximum detection range |
| LOBs | Recent lines of bearing from DF intercepts (fade over 30 s) |
| Ellipses | Each side's error ellipse and CEP for its fix on the enemy GCS |
| Flight Paths | Breadcrumb trails behind each drone |
| Canopy | Vegetation overlay (canopy also degrades RF in the model) |
| Status HUD | Team status cards in the upper map corners: drone state, battery, LOBs held, fix CEP, and engagement status — the race-to-fix at a glance |
| Scenario | Curated seeds with known outcomes (see below) |
| Random | Any seed; same seed always replays the identical engagement |

Click any unit on the map (GCS, DF node, or drone) for a live detail panel:
airspeed, altitude, battery, link state, intercept counts, current fix quality.
The event log on the right narrates the engagement in message-traffic style.

### Featured scenarios

The dropdown ships five curated seeds:

- **Standard Engagement (BLUFOR)** — the default; a representative disciplined win
- **Discipline Wins, Fast (BLUFOR)** — EMCON advantage converts quickly
- **Deliberate Fix (BLUFOR)** — a slower, methodical collection problem
- **OPFOR Prevails** — the continuous emitter gets lucky and wins the race
- **Close Race (OPFOR)** — both sides commit nearly simultaneously

Because the RNG is fully deterministic (seeded `mulberry32`), these are simply
seeds whose engagements were observed to produce instructive outcomes. The
Random button explores the full space; interesting seeds can be added to the
dropdown as new featured scenarios.

## What's being simulated

One engagement, four phases (tracked live in the header):

1. **Emplacement** — each side places a ground control station (GCS) and two
   cUAS DF nodes, with the DF baseline deliberately spread perpendicular to the
   expected threat axis so the two collectors produce well-crossed bearings.
2. **Search and Collect** — drones launch and hold in an endurance-optimal
   orbit forward of their own GCS while the ground DF nodes collect lines of
   bearing (LOBs) on the enemy's emissions: C2 uplink intercepts locate the
   enemy **GCS**; FPV video downlink intercepts track the enemy **drone**.
3. **Fix** — accumulated LOBs are fused by weighted least squares into a
   position estimate with an honest error ellipse and CEP.
4. **Attack** — once the fix is tight enough (or battery forces a "final push"
   on the best available fix), the drone dashes to the estimated point,
   descends below canopy, visually acquires, and strikes. Destroying the enemy
   GCS severs their drone's C2 link — it crashes shortly after. ENDEX.

The interesting failure modes are real ones: a fix built mostly from one sensor
has weak along-range constraint and can miss badly; a drone that arrives on a
bad fix burns battery flying an expanding search; a drone that waits too long
for a perfect fix runs out of endurance.

See **[DESIGN_NOTES.md](DESIGN_NOTES.md)** for the full technical write-up:
the DF measurement model, the least-squares fix and covariance inflation, the
terrain and RF propagation models, the drone state machine, and the tuning
rationale behind every number in `CONFIG`. See
**[DEVELOPMENT_HISTORY.md](DEVELOPMENT_HISTORY.md)** for how the project was
made: the requirements baseline, the bugs found and fixed along the way
(including the overconfident-estimator fix), and why the featured-scenario
approach was chosen over forcing decisive outcomes. See
**[MONTE_CARLO.md](MONTE_CARLO.md)** for the statistical backing behind the
EMCON lesson: 22,800 engagements run on the headless engine from
[fpv-sim-mcp](https://github.com/wasomma/fpv-sim-mcp), showing the
disciplined side wins 36.8% to 26.3% under stock config, that the advantage
follows the EMCON posture when postures are swapped, and that win rate
responds dose-dependently to uplink duty cycle.

## Tuning

Every simulation parameter is in the `CONFIG` object at the top of the script
block in `index.html` — drone speeds and endurance, DF scan rate and bearing
error, fix-quality gates, and each team's EMCON duty cycles. Units are meters,
meters/second, simulated seconds, and degrees. Change a number, reload, replay
the same seed, and compare outcomes. **[PARAMETERS.md](PARAMETERS.md)** is the
full reference — every tunable with default, unit, valid range, and rationale,
generated from the same machine-readable table that validates inputs to the
[fpv-sim-mcp](https://github.com/wasomma/fpv-sim-mcp) tools.

## Provenance and repo notes

- The demo was authored with AI assistance (Anthropic's Claude) as a
  single-file deliverable. The design notes were reconstructed from the code
  itself, which is extensively commented; the development history was written
  from the original authoring conversation and reconciled against the shipped
  code.
- `index.html` is the entire simulation application. It is named `index.html`
  so GitHub Pages serves it at the repository root URL. `dashboard.html` is
  its companion results viewer — equally single-file and dependency-free,
  reading the committed datasets in `results/`.
- No build, no dependencies, no network calls. It runs from a `file://` URL.

## License

This repository is public for demonstration, not open source. Licensed under
the [PolyForm Strict License 1.0.0](LICENSE.md): you may read the code and use
it for noncommercial purposes, but no rights are granted to modify,
redistribute, or use it commercially. (Opening the hosted demo and dashboard in
your browser is exactly the intended use.)

Required Notice: Copyright © 2026 Wesley Fine (https://github.com/wasomma)
