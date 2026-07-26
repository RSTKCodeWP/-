# Changelog

All notable changes to fpv-sim-mcp are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/) and match the `version` field in
`package.json`. The engine's behavior contract is exact parity with
upstream [fpv-sim](https://github.com/wasomma/fpv-sim) — any release that
regenerates the golden fixtures against a new upstream commit says so
explicitly and records the commit in `docs/upstream/SNAPSHOT.md`.

## [Unreleased]

### Changed
- **Relicensed from MIT to PolyForm Strict License 1.0.0**
  ([LICENSE.md](LICENSE.md)): the repository stays public to read and
  use noncommercially, but is no longer open source — no modification,
  redistribution, or commercial use. Copies obtained under MIT before
  this change retain their MIT rights.

## [0.2.0] — 2026-07-23

### Added
- **Upstream drift detection** (`.github/workflows/upstream-drift.yml`):
  weekly CI that regenerates the golden fixtures from live fpv-sim `main`
  and fails if engagement outcomes differ from the committed ones —
  distinguishing engine regressions (`npm test`) from upstream
  behavior changes (fixture comparison). Also warns when the pinned
  design-notes snapshot falls behind upstream.

### Fixed
- `npm test` now works on Node 20, the stated minimum: the test glob is
  shell-expanded instead of relying on `node --test` pattern expansion,
  which only Node 21+ performs. Caught by the drift workflow's first CI
  run.

### Docs
- README example transcript: added a postscript correcting the agent's
  closing guess that the 6-second launch stagger explained the residual
  BLUFOR edge — a 2,000-pair study on this engine
  ([fpv-sim's MONTE_CARLO.md](https://github.com/wasomma/fpv-sim/blob/main/MONTE_CARLO.md),
  experiment E2c) found the stagger moves outcome rates by less than half
  a point.

## [0.1.0] — 2026-07-21

### Added
- Initial release: headless TypeScript engine extracted from fpv-sim's
  `index.html` with float-exact behavior parity, proven by golden-master
  fixtures generated from the original browser source running in a Node
  `vm` (plus a real-browser cross-check).
- MCP server with five read-only, deterministic tools (`run_engagement`,
  `sweep_seeds`, `compare_configs`, `describe_model`, `get_config_schema`)
  and two documentation resources, with zod validation generated from the
  same parameter table as the schema tool.
- Stdio and Streamable HTTP transports, an MCP client demo
  (`npm run demo`), a VPS deployment runbook (`deploy/`), and the
  golden-fixture generator (`scripts/generate-goldens.mjs`).
- Headless-only additions to the sim's semantics: guaranteed termination
  (winner, both-drones-down, or 3600 s cap — the latter two reported as
  first-class `STALEMATE` outcomes) and flag timestamps for aggregation.

[Unreleased]: https://github.com/wasomma/fpv-sim-mcp/compare/6a49d61...HEAD
[0.2.0]: https://github.com/wasomma/fpv-sim-mcp/compare/50b02d3...6a49d61
[0.1.0]: https://github.com/wasomma/fpv-sim-mcp/commits/50b02d3
