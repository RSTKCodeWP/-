# fpv-sim-mcp

An [MCP](https://modelcontextprotocol.io) server that exposes
[fpv-sim](https://github.com/wasomma/fpv-sim) — a deterministic force-on-force
simulation of FPV sUAS vs counter-UAS RF direction finding — as tools an AI
agent can call.

All data is **notional**. The area of operations ("AO KATANA"), unit
positions, sensor parameters, and outcomes are invented for demonstration
purposes. Unclassified throughout.

## Why this exists

The original fpv-sim is a browser tab a human watches. This project
demonstrates the step after that: making the same simulation
**agent-accessible**, so an AI assistant can run engagements, sweep hundreds
of seeds, compare doctrine variants, and explain the results — the workflow
the original developers did by hand during tuning (grid sweeps, 40 seeds per
cell) packaged as five typed, validated, deterministic tools. The simulation
core was extracted from the browser file into a headless TypeScript engine
with **behavior parity proven by golden-master tests**: the same seed
produces the same engagement, tick for tick, as the browser version.

The core lesson is unchanged from the original: **the side that transmits
less is harder to fix.** An agent with these tools can discover that itself —
see the [example transcript](#example-what-an-agent-does-with-this) below.

## Quick start

Requires Node 20+.

```sh
git clone https://github.com/wasomma/fpv-sim-mcp.git
cd fpv-sim-mcp
npm install
npm test        # builds and proves browser-parity + unit tests (17 tests)
npm run demo    # exercises the server through a real MCP stdio client
```

### Claude Code

```sh
claude mcp add fpv-sim -- node /absolute/path/to/fpv-sim-mcp/dist/src/server/index.js
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "fpv-sim": {
      "command": "node",
      "args": ["/absolute/path/to/fpv-sim-mcp/dist/src/server/index.js"]
    }
  }
}
```

(On Windows use a path like `C:\\path\\to\\fpv-sim-mcp\\dist\\src\\server\\index.js`.)

### Remote (no local install)

The server also ships a **Streamable HTTP** entry point
(`dist/src/server/http.js`) for hosting on any box with Node 20+ —
[deploy/DEPLOY.md](deploy/DEPLOY.md) is a complete VPS runbook (systemd,
Caddy TLS, bearer-token auth).

A hosted demo instance runs at `https://wasomma-fpv.duckdns.org/mcp`
(health probe at [/healthz](https://wasomma-fpv.duckdns.org/healthz)). It is
bearer-token protected — it exposes CPU, not secrets, but an open sim
endpoint invites abuse. If you'd like to try it without building anything,
ask me for a token ([GitHub](https://github.com/wasomma) /
[LinkedIn](https://www.linkedin.com/in/wesleyfine/)), then:

```sh
claude mcp add --transport http fpv-sim https://wasomma-fpv.duckdns.org/mcp \
  --header "Authorization: Bearer <token>"
```

Determinism makes the hosted instance verifiable: `run_engagement(20260719)`
returns the same BLUFOR victory at T+311.1s from the cloud that the local
build produces — same seed, same engagement, any machine.

## Tools

| Tool | What it does |
|---|---|
| `run_engagement(seed, config_overrides?)` | One full deterministic engagement: winner (or STALEMATE) with reason, duration, phase timeline, per-team fix quality (CEP breakdown), LOB/intercept counts per DF node, key timestamps, and the complete event log. |
| `sweep_seeds(start_seed, count, config_overrides?)` | Up to 1000 consecutive seeds under one configuration, aggregated server-side: win rates (including stalemates), time-to-fix and time-to-kill distributions, stalemate reasons, and notable seeds to drill into. |
| `compare_configs(start_seed, count, config_a, config_b, labels?)` | Two CONFIG variants over the **same** seeds (paired design — terrain and emplacement luck cancel out), with per-variant stats, outcome flips, deltas, and a plain-language summary generated from the numbers. |
| `describe_model()` | The modeling assumptions: DF error model, RF propagation, fix quality gates, drone FSM, EMCON semantics — and the known simplifications an agent must respect before drawing conclusions. |
| `get_config_schema()` | Every tunable parameter with path, unit, default, and sane range. Generated from the same table that validates inputs, so documentation and enforcement cannot drift. |

Resources: `fpv-sim://design-notes` (the original sim's technical write-up)
and `fpv-sim://mcp-design-notes` (this project's [DESIGN_NOTES.md](DESIGN_NOTES.md)).

Every tool is read-only and side-effect-free. Identical inputs always return
identical outputs — the *server itself* is deterministic, which is what makes
results citable: any number an agent reports can be reproduced by anyone
running the same call.

## Example: what an agent does with this

Abridged transcript (tool results elided; the numbers below are real —
reproduce them with `npm run demo` or the same tool calls):

> **User:** Does emissions discipline actually decide these fights, or is
> that just the demo's marketing? Test it.
>
> **Agent:** *(calls `describe_model`)* The model says the only default
> asymmetry is EMCON posture: BLUFOR keys its uplink 4s on / 13s off with
> burst video, OPFOR 10s on / 4s off with continuous video. I'll test the
> claim by giving OPFOR the same discipline as BLUFOR and comparing across
> identical seeds.
>
> *(calls `get_config_schema`, then `compare_configs(start_seed: 1000,
> count: 200, config_a: {}, config_b: {TEAMS: {OPFOR: {uplinkOn: 4,
> uplinkOff: 13, videoOn: 3, videoOff: 7}}})`)*
>
> Across 200 paired seeds: stock OPFOR (continuous emitter) loses 40.0% to
> 25.5%. When OPFOR adopts BLUFOR's duty cycles, the gap closes to 34.0% vs
> 30.0% — 45 of 200 seeds change outcome, and BLUFOR's mean time-to-fix on
> the OPFOR GCS degrades by ~146 seconds because the uplink it collects
> against is keyed 76% less of the time. So yes: with identical hardware,
> EMCON posture alone moves the win rate by ~10 points and starves the
> enemy's fix timeline. The residual BLUFOR edge is its 6-second earlier
> launch. Worth knowing: ~35% of engagements are honest stalemates — the
> estimator refuses to bless a bad fix, so nobody commits.

That last sentence is the point of the whole exercise: the agent can also
read `describe_model` and report what the simulation *cannot* claim.

**Postscript — one claim above didn't survive a bigger experiment.** The
agent's parting guess that "the residual BLUFOR edge is its 6-second
earlier launch" was later tested directly: a 2,000-pair study run on this
engine ([fpv-sim's MONTE_CARLO.md](https://github.com/wasomma/fpv-sim/blob/main/MONTE_CARLO.md),
experiment E2c) equalized the launch times and found the stagger moves
every outcome rate by less than half a point — a non-factor. EMCON posture
explains essentially the whole gap. The transcript stands as written
because that is how this is supposed to work: a deterministic, citable
claim was cheap to re-test at 10× the sample size, and it lost.

## Determinism and provenance

- **Same seed, same engagement.** All randomness draws from one seeded
  `mulberry32` stream. Golden-master tests prove the extracted engine
  reproduces the browser version's five featured scenarios exactly — event
  log string-for-string, end times to the 0.1s tick, fix CEPs float-for-float
  ([DESIGN_NOTES.md](DESIGN_NOTES.md) describes the three-legged
  verification, including a cross-check against the untouched sim in a real
  browser).
- **Authored with AI assistance** (Anthropic's Claude, via Claude Code), like
  the original fpv-sim. The engine is a faithful port of the original
  simulation code, whose modeling comments are preserved in place; the
  fixtures it is tested against were generated by running the original,
  unmodified simulation source.
- **All simulation data is notional and unclassified.** Numbers are
  plausible-magnitude fiction shaped by doctrine, not measured data. Nothing
  here supports absolute performance claims about any real system.

## Repository layout

```
src/engine/    headless simulation engine (port of fpv-sim's index.html)
src/server/    MCP server: five tools, two resources, zod validation;
               build.ts is shared by the stdio (index.ts) and
               Streamable HTTP (http.ts) entry points
test/          golden-master parity + unit tests (npm test)
examples/      demo MCP client (npm run demo)
scripts/       golden-fixture generator (needs ../fpv-sim checkout)
deploy/        VPS runbook + hardened systemd unit for remote hosting
docs/upstream/ pinned snapshot of the original DESIGN_NOTES.md
```

## License

This repository is public for demonstration, not open source. Licensed under
the [PolyForm Strict License 1.0.0](LICENSE.md): you may read the code and use
it for noncommercial purposes, but no rights are granted to modify,
redistribute, or use it commercially. (Connecting an agent to the hosted MCP
endpoint is exactly the intended use.)

Required Notice: Copyright © 2026 Wesley Fine (https://github.com/wasomma)
