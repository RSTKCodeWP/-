# TODO

## 1. Publish the `fpv-fleet-update` skill publicly

Make the skill installable by others via a Claude Code plugin marketplace. Currently it's
project-scoped (`.claude/skills/fpv-fleet-update/`), so it only loads inside this repo.

Steps:
- [ ] Decide on a marketplace repo (e.g. `github.com/irom77/claude-plugins`) — separate repo, or reuse this one.
- [ ] Scaffold the plugin layout:
  ```
  plugins/fpv-fleet-update/
  ├── .claude-plugin/plugin.json      # name, description, version, author
  └── skills/fpv-fleet-update/
      ├── SKILL.md
      └── scripts/update_fleet.py
  ```
- [ ] Add the marketplace manifest `.claude-plugin/marketplace.json` listing the plugin.
- [ ] Fix the script path in SKILL.md: `.claude/skills/...` → `${CLAUDE_PLUGIN_ROOT}/scripts/update_fleet.py`
      (the repo-relative path breaks once installed as a plugin).
- [ ] Validate: `claude plugin validate .`
- [ ] Push the marketplace repo to GitHub.
- [ ] Test install from a clean checkout: `/plugin marketplace add irom77/claude-plugins` then
      `/plugin install fpv-fleet-update@<marketplace-name>`.
- [ ] Note in README how to install it.

Caveat to resolve: the skill writes its output (CSVs, FLEET_SUMMARY.md) into the current working
directory and is built around Betaflight dumps, so it's mainly useful to people who keep BTFL
backups. Consider documenting that expectation, or generalizing the script (e.g. an input/output
flag) before publishing.

## 2. Make use of blackbox logs

Betaflight blackbox flight logs (`.bbl` / `.bfl`) capture per-flight telemetry. First pass is
implemented: `update_flights.py` decodes logs (via `orangebox`) into `flights.csv`, and
`update_fleet.py` folds a per-quad Flights section into FLEET_SUMMARY.md.

Done:
- [x] Logs live in `blackbox/` (gitignored); only derived `flights.csv` is committed.
- [x] Per-flight summary: duration, battery start/min/sag, cell count, avg/peak current, mAh,
      avg throttle & motor, motor saturation %. Units calibrated from log headers.
- [x] Link each flight to its quad (craft name from log header) and per-quad rollup in the summary.
- [x] Wired into the `fpv-fleet-update` skill.

- [x] Motor desync / thrust-loss detection (motor commanded high while its eRPM collapses vs peers),
      surfaced as `MOTOR_DESYNC(m#)` in flights.csv flags + ⚠️ in the summary. Validated against the
      Kronos crash log (motors 0 & 3) vs the clean post-repair log.
- [x] `hardware.csv` for per-quad build details (ESC, motors, props) not present in dumps.

Next / ideas to extend:
- [ ] More metrics: max gyro / vibration (noise), PID error / tracking, RC dropout & failsafe events,
      throttle histogram, per-motor imbalance (worn motor / prop detection).
- [ ] More auto-flags: excessive sag → aging pack (partial: LOW_CELL); motor saturation →
      underpowered/overweight. Roll flagged flights up into the summary's "needs attention".
- [ ] Distinguish real flights from bench tests (both current logs are short bench hops).
- [ ] Handle logs whose filename lacks a craft label; match to a quad another way.

## Auto-link ordered parts to builds (fpv-orders-update)

The `fpv-orders-update` skill currently leaves the `build` column blank for the pilot to fill.
Future: propose a best-guess `build` from order timing vs. quad dump dates (e.g. motors bought
just before a Kronos dump → `Kronos?`), left as a `?`-flagged suggestion to confirm.
