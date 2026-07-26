# Development History

UNCLASSIFIED // NOTIONAL DEMONSTRATION

This document records how the demo was designed and built. It was written from
the original authoring conversation (a Claude Project), then reconciled against
the shipped code in this repository. See [DESIGN_NOTES.md](DESIGN_NOTES.md) for
the technical documentation of the code as it stands.

## Original Goal

Build a customer-facing communication tool: a single-file, interactive HTML
visualization of a symmetric force-on-force engagement between two teams
(BLUFOR and OPFOR). Each team operates one armed FPV sUAS from a Ground
Control Station (GCS), paired with a non-kinetic cUAS direction-finding (DF)
capability that detects the opposing team's C2 uplink and video downlink
emissions.

The core tactical thesis the visualization must communicate: **operating your
drone is what exposes you.** RF emissions generate lines of bearing (LOBs)
that accumulate into a geolocation fix on the emitting GCS. First team to fix,
close on, and destroy the opposing GCS wins.

The concept is intended for live execution by the customer with simulated
munitions and in Live Virtual Constructive simulation (FLOWSTATE and VBS4).
The visualization is a demonstration and communication tool for that concept,
not a training system.

## Requirements Definition

Requirements were captured through a structured interview and locked into a
project prompt as the design baseline. Key decisions from that phase and the
rationale behind each:

- **Single self-contained HTML file.** Easy to run, share, and demo with no
  build step or dependencies.
- **Fictional but realistic terrain** — dense jungle island terrain of the
  kind found across western Pacific island chains. Notional location, but the
  environment type (canopy, clearings, trails, elevation) matters tactically
  for both flight profiles and RF propagation.
- **Realism as the priority.** The audience includes knowledgeable operators;
  anything cartoonish or physically implausible undermines credibility.
  Plausible FPV speeds and altitudes, believable DF behavior, and canopy
  masking effects were all required from the start.
- **Full engagement arc animated over time**: emplacement, launch, RF
  collection, fix refinement with visible uncertainty ellipses, attack commit,
  terminal engagement, ENDEX.
- **Interactivity**: playback controls (play, pause, reset, speed), layer
  toggles (RF coverage, LOBs, uncertainty ellipses, flight paths, canopy),
  clickable units with detail panels, and a scrolling event log in concise
  military report style.
- **Hybrid MIL-STD-2525 symbology** on a dark C2-style display. Chosen as the
  sweet spot: credible to operators, readable to non-operator leadership.
- **Subdued company branding** (small OneArc wordmark) and an
  "UNCLASSIFIED // NOTIONAL DEMONSTRATION" banner for credibility.
- **Seeded, deterministic behavior** so the demo replays consistently, with
  randomness available for exploration.
- **Key parameters exposed as named constants** (drone speed, detection
  probability, bearing error, endurance) so the design can be hand-tuned
  without code archaeology.

## Build

The baseline was constructed in one session with the following core systems:

- Terrain generation using seeded value-noise (canopy density, clearings,
  elevation).
- A path-attenuation RF propagation model, so canopy and terrain genuinely
  mask emissions.
- A weighted least-squares DF fix estimator producing geolocation estimates
  with CEP.
- A drone state machine covering launch, search, collection support, attack
  commit, and terminal behavior.
- A layered canvas renderer with the hybrid 2525-inspired symbology and dark
  C2 aesthetic.

## What Was Tried and Changed

### 1. Endurance burn during collection

**Problem:** Drones ran out of battery before their team refined a fix on the
enemy GCS. Diagnosis showed they were burning endurance loitering deep in the
enemy area during the collection phase.

**Change:** Of the candidate fixes, the most tactically realistic option was
chosen: hold the drone near own lines while the ground DF nodes build the fix,
then commit and dash to the target. This mirrors real emissions and endurance
discipline rather than papering over the problem with inflated battery
numbers. (In the shipped code: the HOLD state, orbiting a point 600 m forward
of own GCS at a 0.62× battery drain multiplier.)

### 2. Overconfident DF estimator

**Problem:** Tracing the endurance fix exposed a deeper bug. The estimator
reported tight CEP values (on the order of 150 m) while true fix error reached
2 km, sending drones to attack empty jungle. Root cause: fixes dominated by a
single collector left the along-range dimension nearly unconstrained, and the
reported covariance did not reflect that geometry.

**Changes:**

- A balanced multi-sensor requirement: a minimum number of LOBs from the
  second collector before a fix is trusted (final value: 3, shipped as
  `FIX.MIN_LOBS_2ND`).
- A geometry-aware CEP term weighting by sensor balance and LOB crossing
  angle.
- A fix-stability jitter gate before attack commit.

**Result:** Median true-error to reported-CEP ratio improved from roughly 3.0
to roughly 1.2, meaning the displayed uncertainty ellipse is now an honest
representation of actual fix quality.

### 3. Terminal-phase spiral bug

**Problem:** In the terminal phase the drone began its expanding visual search
from the wrong point.

**Change:** The drone now drives to the fix center first, then begins the
expanding search. Kill timelines became consistent and credible.

### 4. Honest physics vs guaranteed decisive outcomes

**Finding:** A systematic parameter grid sweep (detection probability by
endurance, 40 seeds per cell) showed that with the honest estimator, the
decisive-kill rate caps around 68 percent even at the best operating point.
Roughly 30 percent of seeds are genuine stalemates: disciplined emissions plus
imperfect DF geometry legitimately deny a fix. Raising detection probability
did not help because the balanced multi-sensor gate, not raw detection rate,
was the bottleneck.

**Decision:** This was treated as a demo-philosophy tradeoff and put to the
project lead rather than resolved by engineering fiat. Forcing near-100
percent kills would have required reintroducing the dishonest estimator. The
chosen resolution: **curated featured scenarios** selectable from a dropdown,
with random seeds still available for free exploration. This guarantees a live
demo always shows a decisive engagement without faking the physics.

**Implementation:** 120 seeds were swept and classified by engagement
character. Five were selected and verified end to end (accurate winning fixes,
healthy remaining battery):

| Scenario | Seed |
| --- | --- |
| Fast BLUFOR win | 66 |
| Deliberate BLUFOR win | 57 |
| OPFOR win | 41 |
| Close race | 59 |
| Original default | 20260719 |

**Final configuration:** `P_DETECT_UL` 0.40, endurance 1200 s, minimum 3 LOBs
from the second collector. (All three values verified present in the shipped
`CONFIG`.)

### Validated engagement character

The tuned default run demonstrates the intended asymmetric dynamic. Timeline
on the order of: cross-fix forming around T+01:51 (6 LOBs), FIX ESTABLISHED
around T+03:13 (CEP 122 m), attack commit around T+04:23 (CEP 87 m), impact
around T+05:44. One side running intermittent EMCON wins; the other side,
emitting continuously, is detected quickly on its video downlink and never
accumulates enough LOBs against the disciplined side to build a fix. This is
exactly the teaching point the demo exists to communicate.

## Deployment

The validated file was authored in a sandboxed chat environment that could not
complete the GitHub push itself (token scoping blocked access to the new
repo, and that sandbox does not persist files between sessions). Deployment
was completed separately from a local machine using the GitHub CLI: the file
was committed to this repository as `index.html`, GitHub Pages was enabled
from the `main` branch root, and the live URL was verified serving the demo:

**https://wasomma.github.io/fpv-sim/**

## Current State

- Validated single-file build with honest DF physics, five curated scenarios,
  and full interactivity per the baseline requirements.
- Live on GitHub Pages; documentation (README, design notes, this history) in
  the repository.
- Design baseline locked in project instructions; iteration continues on this
  one visualization.
