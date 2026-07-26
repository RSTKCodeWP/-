# Monte Carlo Study — Does Emissions Discipline Actually Decide the Fight?

The README claims the sim's core lesson is that **the side that transmits
less is harder to fix**. The featured scenarios illustrate that claim with
curated seeds; this document backs it with statistics: 22,800 deterministic
engagements across four experiments. The headline results:

- Under stock configuration, the disciplined side (BLUFOR) wins **36.8%** of
  engagements to the continuous emitter's **26.3%** — 58% of all decisive
  fights — and fixes the enemy GCS about **52 s sooner** at the median.
- Give OPFOR the same discipline and the gap vanishes (29.3% vs 29.8%,
  statistically even). Swap the postures outright and the advantage follows
  the discipline, not the team (OPFOR then wins 38.4% to 26.5%).
- The other asymmetry in the stock config — BLUFOR launching 6 s earlier —
  turns out to be worth **nothing** (all rate deltas < 0.5 points at n=2,000).
  EMCON posture explains essentially the entire baseline gap.
- Discipline is dose-dependent: sweeping OPFOR's uplink duty cycle from 14%
  to 86% moves the enemy's win rate from ~24% to ~39% and accelerates the
  enemy's fix timeline by ~160 s.

As everywhere in this project, all data is **notional**. These are
statements about the model, not about any real system (see
[Scope and caveats](#scope-and-caveats)).

An interactive view of these results — including click-to-replay links from
any statistic to the watchable engagement behind it — lives at
**[dashboard.html](https://wasomma.github.io/fpv-sim/dashboard.html)**.

## Method

### Engine

Replications run on the headless engine from
[fpv-sim-mcp](https://github.com/wasomma/fpv-sim-mcp) — the simulation core
of this repo's `index.html` extracted to TypeScript, with behavior parity
proven by that project's golden-master tests (same seed → same engagement,
event-log string-equal, CEPs float-equal). This study deliberately does
*not* reimplement the sim: `index.html` remains the specification, the
engine is its verified headless twin, and re-deriving a third copy here
would only create drift risk.

### Design

A replication is one full engagement: `runEngagement(seed, overrides)` run
to termination — a GCS kill, both drones down (stalemate), or a 3600 s cap
(stalemate; never reached in this study: all 3,683 baseline stalemates are
both-drones-down). Because every engagement draws from one seeded
`mulberry32` stream, a replication is fully determined by
(seed, config overrides), and every number below can be regenerated exactly.

- **Seed lists are contiguous ranges starting at 1**, so each experiment is
  reproducible from its range alone.
- **Paired comparisons (E2)** run two config variants over the *identical*
  seed list — a common-random-numbers design. Per-seed terrain and
  emplacement luck cancel out of the deltas, so 2,000 pairs resolve effects
  that independent samples of that size could not.
- **Uncertainty** is reported as 95% Wilson score intervals on outcome
  proportions.
- **Stalemates are a first-class outcome**, not discarded: an honest
  estimator that refuses to bless a bad fix produces engagements where
  nobody commits, and how often that happens is itself a finding.
- Time-to-fix statistics are **conditional on that side achieving a fix**,
  so the run subsets behind those means differ between variants; treat
  time-to-fix deltas as descriptive, not as tightly identified as the
  outcome-rate deltas.

Stock asymmetries under test: BLUFOR keys its C2 uplink 4 s on / 13 s off
with burst video (3/7); OPFOR keys 10 s on / 4 s off with continuous video.
BLUFOR launches at T+20, OPFOR at T+26. Hardware is otherwise identical.

## E1 — Baseline (10,000 seeds, stock config)

Seeds 1–10,000, no overrides.

| Outcome | Count | Rate | 95% CI |
|---|---|---|---|
| BLUFOR victory (disciplined) | 3,683 | 36.8% | [35.9%, 37.8%] |
| OPFOR victory (continuous) | 2,634 | 26.3% | [25.5%, 27.2%] |
| Stalemate (both drones down) | 3,683 | 36.8% | [35.9%, 37.8%] |

The disciplined side takes **58.3% of the 6,317 decisive engagements**. The
mechanism shows up in the fix race: BLUFOR establishes a fix in 6,850 of
10,000 runs (median 379 s), OPFOR in only 3,274 (median 431 s) — the
continuous emitter is simply available to collect against far more often.
Decisive engagements end at a median of 665 s (p10 172 s, p90 1,156 s);
the fastest kill in the sample is seed 5838 (BLUFOR, T+99.2 s) and the
slowest seed 4189 (OPFOR, T+1900.9 s).

The ~37% stalemate rate matches the development history's finding for the
honest estimator, and it is the model being truthful: when neither side
accumulates enough well-crossed bearings, neither commits, and both drones
exhaust their batteries. (That the BLUFOR-win and stalemate counts are both
exactly 3,683 is coincidence.)

## E2 — Paired comparisons (2,000 same-seed pairs each)

Stock arm over seeds 1–2,000: BLUFOR 37.0% [35.0%, 39.2%], OPFOR 26.5%
[24.6%, 28.4%], stalemate 36.5% — consistent with E1. Each variant below is
compared against this arm on the same seeds.

| Experiment | Variant outcome (B / O / S) | Δ vs stock (points) | Outcome flips |
|---|---|---|---|
| **E2a** OPFOR adopts BLUFOR's duty cycles | 29.3% / 29.8% / 40.8% | −7.7 / +3.4 / +4.3 | 533 / 2,000 |
| **E2b** Full EMCON posture swap | 26.5% / 38.4% / 35.1% | −10.6 / +11.9 / −1.3 | 643 / 2,000 |
| **E2c** Launch stagger equalized (both T+20) | 36.8% / 26.3% / 37.0% | −0.3 / −0.2 / +0.5 | 456 / 2,000 |

**E2a — discipline is worth ~10 points of win rate.** With both sides
disciplined, the fight is statistically even (29.3% vs 29.8%, CIs almost
fully overlapping) and stalemates rise 4.3 points — two quiet emitters give
both estimators less to work with. BLUFOR's mean time-to-fix degrades by
122 s because the uplink it collects against is now keyed 76% less of the
time.

**E2b — the advantage follows the posture, not the team.** With postures
swapped, OPFOR wins 38.4% to 26.5% — the baseline result mirrored, within
confidence intervals (compare the stock arm's 37.0% / 26.5%). If the
asymmetry were anything about the teams other than EMCON (positions,
terrain, search boxes), the swap would not reproduce the gap this cleanly.

**E2c — the launch stagger is a non-factor.** Equalizing launch times moves
every outcome rate by less than half a point — pure noise at this sample
size. This refutes the natural guess (made in fpv-sim-mcp's README example)
that BLUFOR's residual edge in E2a comes from its 6-second-earlier launch;
E2a's near-parity *is* the full story, and the E2b mirror confirms it.
Note the 456 individual seed flips at near-zero net rate change: the
engagement is chaotic — tiny perturbations reroll individual outcomes — but
the *rates* are stable, which is exactly why conclusions here are drawn
from ensembles, not single seeds.

## E3 — Dose response: OPFOR uplink duty cycle (400 seeds per cell)

OPFOR's uplink period fixed at 14 s (matching stock), on-time swept 2–12 s,
at both video postures. Seeds 1–400 per cell. BLUFOR stock throughout.

| OPFOR uplink duty | Video | BLUFOR win | OPFOR win | Stalemate | BLUFOR mean time-to-fix (s) |
|---|---|---|---|---|---|
| 14% (2/12) | continuous | 23.3% | 31.0% | 45.8% | 668 |
| 29% (4/10) | continuous | 30.3% | 29.5% | 40.3% | 575 |
| 43% (6/8) | continuous | 36.5% | 28.0% | 35.5% | 592 |
| 57% (8/6) | continuous | 37.8% | 27.0% | 35.3% | 567 |
| 71% (10/4) | continuous | 35.8% | 28.3% | 36.0% | 495 |
| 86% (12/2) | continuous | 39.0% | 25.8% | 35.3% | 506 |
| 14% (2/12) | burst 3/7 | 24.5% | 34.3% | 41.3% | 647 |
| 29% (4/10) | burst 3/7 | 29.0% | 29.0% | 42.0% | 596 |
| 43% (6/8) | burst 3/7 | 34.8% | 26.0% | 39.3% | 578 |
| 57% (8/6) | burst 3/7 | 36.3% | 25.8% | 38.0% | 532 |
| 71% (10/4) | burst 3/7 | 37.8% | 24.8% | 37.5% | 510 |
| 86% (12/2) | burst 3/7 | 38.3% | 28.8% | 33.0% | 504 |

(The 71%-duty continuous row is the stock OPFOR posture; its rates agree
with E1 within its ±4.7-point cell CI. Per-cell CIs at n=400 are roughly
±4–5 points, which accounts for the mild non-monotonicity between adjacent
cells; the trend across the sweep is far larger than the noise.)

The dose response is clear in both video postures: every additional second
of uplink on-time feeds the enemy's collectors. From quietest to loudest,
the enemy's win rate climbs ~15 points, the enemy's mean fix timeline
accelerates by ~160 s, and OPFOR's own win rate falls ~5 points. At 14%
duty OPFOR actually *out-wins* stock BLUFOR — discipline beyond BLUFOR's
own 24% duty keeps paying. Stalemates rise as the battlefield gets
quieter, for the same reason as E2a: fixes get harder for everyone.

## Scope and caveats

- **Notional throughout.** Parameter values are plausible-magnitude fiction;
  nothing here supports absolute claims about real systems. The defensible
  claim is *directional and internal to the model*: under identical
  hardware, RF availability drives the fix race, and the fix race drives
  outcomes.
- The model's simplifications are inherited unchanged from `index.html`
  (sense-only cUAS, planar geometry, one sortie per side, cosmetic
  frequencies — see [DESIGN_NOTES.md](DESIGN_NOTES.md)).
- Config overrides cannot move emplacements or NAI geometry, so these
  results are conditional on the stock scenario geography.
- One RNG stream per engagement means a config change early in a run
  diverges everything downstream; paired comparisons are valid for outcome
  statistics, but per-tick trajectories under different configs are not
  comparable.

## Reproducing

Every number above is deterministic. Full study (~30 min single-threaded):

```sh
git clone https://github.com/wasomma/fpv-sim.git
git clone https://github.com/wasomma/fpv-sim-mcp.git
cd fpv-sim-mcp && npm install && npm test && cd ../fpv-sim
node scripts/monte-carlo-study.mjs          # writes results/monte-carlo.json
```

`--quick` runs a 1/10-scale smoke pass. A non-sibling engine checkout can
be pointed at with `FPV_SIM_MCP=/path/to/fpv-sim-mcp`.

The committed [results/monte-carlo.json](results/monte-carlo.json) is the
dataset this document was written from.

Spot-checks need no local build: the fpv-sim-mcp MCP server exposes the
same engine, and any sweep within its caps reproduces the corresponding
slice of this study exactly — e.g. `sweep_seeds(start_seed: 1, count:
1000)` for the first thousand baseline seeds, or E2a at 500 pairs via
`compare_configs(start_seed: 1, count: 500, config_a: {}, config_b:
{TEAMS: {OPFOR: {uplinkOn: 4, uplinkOff: 13, videoOn: 3, videoOff: 7}}})`.
Any single engagement cited here (say, seed 5838's 99-second kill) can be
replayed with `run_engagement(5838)` — or watched in the browser by
entering the seed in [the live demo](https://wasomma.github.io/fpv-sim/).

## Provenance

Like everything else in this project, this study was produced with AI
assistance (Anthropic's Claude): the runner script, the experiment design,
and this write-up. The engine it ran on is fpv-sim-mcp's golden-master-
verified extraction of this repository's simulation core.
