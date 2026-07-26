<!-- GENERATED FILE — do not edit by hand.
     Regenerate with: node scripts/generate-parameters-doc.mjs
     Source of truth: fpv-sim-mcp/src/server/params.ts (which itself reads
     the engine defaults extracted from this repo's index.html CONFIG). -->

# Parameter Reference — the Parametric Database

Every number that drives the simulation, with units, defaults, valid
ranges, and the modeling rationale. The same values live in two
synchronized places:

- **`CONFIG` in [index.html](index.html)** — what the browser sim
  executes, with a rationale comment on every value (see
  [DESIGN_NOTES.md](DESIGN_NOTES.md) for the tuning story).
- **The parameter table in
  [fpv-sim-mcp](https://github.com/wasomma/fpv-sim-mcp)**
  (`src/server/params.ts`) — machine-readable metadata that generates both
  that server's input validation and its `get_config_schema` tool, so what
  the tools document and what they accept cannot drift. This file is
  generated from that table for the same reason.

How to read the groups: **DRONE** and **CUAS** are the *hardware* —
identical for both sides. **FIX** is the *judgment* — how much evidence the
estimator demands before acting. **TEAMS** is the *doctrine* — and the
[Monte Carlo study](MONTE_CARLO.md) showed the outcome asymmetry lives
entirely in that layer.

All values are notional. Change a number, reload, replay the same seed,
and compare outcomes — or override any of them per-engagement through the
MCP server's `config_overrides`.

## DRONE — the aircraft and its attack profile

Flight performance, the endurance economy that sets the engagement's clock
pressure (battery, loiter drain, the bingo-fuel threshold that forces a
final push), and terminal-attack geometry.

| Parameter | Default | Unit | Valid range | Description |
|-----------|---------|------|-------------|-------------|
| `CRUISE_MPS` | 18 | m/s | 5 – 60 | Transit / search airspeed (default approx 35 kts). |
| `LOITER_MPS` | 12 | m/s | 4 – 40 | Holding-orbit airspeed, endurance-optimal. |
| `DASH_MPS` | 36 | m/s | 10 – 80 | Attack-run airspeed after commit. |
| `TERMINAL_MPS` | 45 | m/s | 10 – 100 | Terminal homing airspeed. |
| `TURN_DPS` | 70 | deg/s | 20 – 180 | Maximum turn rate. |
| `ALT_TRANSIT_AGL` | 70 | m AGL | 20 – 300 | Transit altitude, above canopy. |
| `ALT_LOITER_AGL` | 55 | m AGL | 15 – 300 | Holding-orbit altitude. |
| `ALT_TERMINAL_AGL` | 12 | m AGL | 3 – 60 | Terminal dive-to altitude (below canopy). |
| `CLIMB_MPS` | 8 | m/s | 1 – 20 | Altitude change rate. |
| `ENDURANCE_S` | 1200 | s | 180 – 3600 | Battery endurance at cruise. The overall engagement clock pressure. |
| `LOITER_DRAIN` | 0.62 | multiplier | 0.2 – 1.5 | Battery drain multiplier while holding (slower speed). |
| `PUSH_BATT_PCT` | 45 | % | 0 – 90 | Bingo fuel: commit on best available fix at or below this battery level. |
| `HOLD_STANDOFF_M` | 600 | m | 100 – 1500 | Holding orbit sits this far forward of own GCS toward the NAI. |
| `HOLD_RADIUS_M` | 130 | m | 50 – 400 | Holding-orbit radius. |
| `ACQ_RANGE_M` | 220 | m | 50 – 600 | Range at which the FPV operator visually IDs the GCS in the terminal phase. |
| `TERMINAL_SEARCH_GROW` | 22 | m/s | 5 – 60 | Expanding-search radius growth when nothing is acquired at the fix point. |
| `IMPACT_RANGE_M` | 9 | m | 3 – 30 | Detonation range. |
| `WPT_RADIUS_M` | 70 | m | 20 – 200 | Waypoint capture radius. |

## CUAS — the RF direction-finding sensors

The collection model: how often the DF nodes scan, how far they see, how
noisy their bearings are, and how detectable each emitter class is per
scan. The uplink/downlink detection gap (0.4 vs
0.65) is why continuous video is so punishing.

| Parameter | Default | Unit | Valid range | Description |
|-----------|---------|------|-------------|-------------|
| `SCAN_S` | 1.5 | s | 0.5 – 10 | DF scan revisit interval. |
| `MAX_RANGE_M` | 3600 | m | 1000 – 6000 | Max detection range vs this emitter class. Below ~3000 m the sides struggle to see each other at all. |
| `BRG_SIGMA_DEG` | 4 | deg (1-sigma) | 0.5 – 15 | Bearing error in clean conditions; path attenuation inflates it further. |
| `P_DETECT_UL` | 0.4 | probability/scan | 0.02 – 1 | Base per-scan detection probability against the C2 uplink. |
| `P_DETECT_DL` | 0.65 | probability/scan | 0.02 – 1 | Base per-scan detection probability against the FPV video downlink. |
| `MAX_MEAS` | 140 | count | 20 – 400 | LOB history cap per collection effort (FIFO). |
| `CANOPY_HGT_M` | 18 | m | 5 – 40 | Canopy top height above ground used for RF masking. |

## FIX — the estimator's decision gates

CEP quality gates and minimum-evidence rules, including the balanced
multi-sensor gate (`MIN_LOBS_2ND`) that keeps the estimator honest about
single-sensor geometry.

| Parameter | Default | Unit | Valid range | Description |
|-----------|---------|------|-------------|-------------|
| `FIX_CEP_M` | 240 | m | 50 – 600 | Effective CEP required to declare FIX ESTABLISHED. |
| `COMMIT_CEP_M` | 120 | m | 30 – 400 | Effective CEP required for attack commit. Looser gates mean earlier, riskier commits. |
| `PUSH_CEP_M` | 260 | m | 50 – 800 | Looser fix acceptable on a low-battery final push. |
| `MIN_LOBS_SOLVE` | 6 | count | 3 – 30 | Minimum LOBs (from 2+ nodes) before a cut is attempted. |
| `MIN_LOBS_2ND` | 3 | count | 1 – 20 | Minimum LOBs from the second-strongest collector before a fix is trusted (the balanced multi-sensor gate). |
| `MIN_LOBS_FIX` | 10 | count | 4 – 40 | Minimum LOBs before FIX can be declared. |
| `MIN_LOBS_COMMIT` | 12 | count | 4 – 60 | Minimum LOBs before attack commit (operator confidence). |
| `CEP_FLOOR_M` | 35 | m | 5 – 150 | Sensor-limited best-case CEP. |
| `GOOD_CUT_DEG` | 35 | deg | 10 – 90 | LOB crossing angle giving full-confidence geometry. |

## TEAMS — per-side doctrine (EMCON posture and launch time)

The only stock asymmetry between the sides. `videoOff: 0` means
continuous video downlink and forces the CONTINUOUS EMCON label.

| Parameter | BLUFOR default | OPFOR default | Unit | Valid range | Description |
|-----------|----------------|---------------|------|-------------|-------------|
| `uplinkOn` | 4 | 10 | s | 0.5 – 60 | C2 uplink keyed duration per duty cycle. |
| `uplinkOff` | 13 | 4 | s | 0 – 120 | C2 uplink silent duration per duty cycle. 0 = continuous uplink. |
| `videoOn` | 3 | 1 | s | 0.5 – 60 | FPV video downlink keyed duration per duty cycle. |
| `videoOff` | 7 | 0 | s | 0 – 120 | FPV video downlink silent duration. 0 = continuous video (poor discipline; forces the EMCON label to CONTINUOUS). Video also forces on during COMMIT/TERMINAL regardless. |
| `launchT` | 20 | 26 | s | 0 – 300 | Sim time at which this team's drone launches. |

## Not tunable — structural constants and derived values

| Path | Why not |
|------|---------|
| `WORLD_M` | Structural: unit emplacements are absolute coordinates tuned to the 4000 m box. |
| `SIM_DT` | Structural: the fixed 0.1 s tick is part of the determinism contract. |
| `SEED` | Pass the seed as a tool argument instead. |
| `TEAMS.*.emconLabel` | Derived: videoOff === 0 reports CONTINUOUS, anything else INTERMITTENT. |

Fixed structural values: the world is 4000 × 4000 m, the
physics tick is 0.1 s, and terrain plus unit emplacements are
generated from the seed — scenario geography is what a seed *reproduces*,
not a knob.

## Determinism

Identical (seed, config_overrides) inputs always produce identical results — overrides change the engagement, not the reproducibility.
