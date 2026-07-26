/*
 * PARAMETERS.md generator.
 *
 * Renders the parameter reference from fpv-sim-mcp's tunable-parameter
 * table (src/server/params.ts) — the same table that generates that
 * server's input validation and get_config_schema tool output. Generating
 * the doc from the table, rather than writing it by hand, means the doc
 * cannot drift from what the simulation actually accepts.
 *
 * Usage: node scripts/generate-parameters-doc.mjs
 * Requires a built fpv-sim-mcp checkout (sibling directory or $FPV_SIM_MCP).
 */

import { pathToFileURL } from "node:url";
import { resolve, join } from "node:path";
import { writeFileSync } from "node:fs";

const mcpRoot = resolve(process.env.FPV_SIM_MCP ?? join(import.meta.dirname, "..", "..", "fpv-sim-mcp"));
const load = (p) => import(pathToFileURL(join(mcpRoot, "dist", "src", p)).href);
let params, engine;
try {
  params = await load("server/params.js");
  engine = await load("engine/index.js");
} catch (err) {
  console.error("Cannot load the parameter table from " + mcpRoot + ".");
  console.error("Clone and build fpv-sim-mcp first (npm install && npm test), or set $FPV_SIM_MCP.");
  throw err;
}

const payload = params.buildConfigSchemaPayload();
const D = engine.DEFAULT_CONFIG;

const esc = (s) => s.replace(/\|/g, "\\|");
const range = (p) => `${p.range[0]} – ${p.range[1]}`;

function table(rows, header) {
  return [header, header.replace(/[^|]/g, "-"), ...rows].join("\n");
}

function sectionTable(prefix) {
  const rows = payload.parameters
    .filter((p) => p.path.startsWith(prefix + ".") && p.path.split(".").length === prefix.split(".").length + 1)
    .map((p) => `| \`${p.path.slice(prefix.length + 1)}\` | ${p.default} | ${p.unit} | ${range(p)} | ${esc(p.description)} |`);
  return table(rows, "| Parameter | Default | Unit | Valid range | Description |");
}

function teamsTable() {
  const b = payload.parameters.filter((p) => p.path.startsWith("TEAMS.BLUFOR."));
  const o = Object.fromEntries(
    payload.parameters.filter((p) => p.path.startsWith("TEAMS.OPFOR."))
      .map((p) => [p.path.split(".").pop(), p]));
  const rows = b.map((p) => {
    const key = p.path.split(".").pop();
    return `| \`${key}\` | ${p.default} | ${o[key].default} | ${p.unit} | ${range(p)} | ${esc(p.description)} |`;
  });
  return table(rows, "| Parameter | BLUFOR default | OPFOR default | Unit | Valid range | Description |");
}

const doc = `<!-- GENERATED FILE — do not edit by hand.
     Regenerate with: node scripts/generate-parameters-doc.mjs
     Source of truth: fpv-sim-mcp/src/server/params.ts (which itself reads
     the engine defaults extracted from this repo's index.html CONFIG). -->

# Parameter Reference — the Parametric Database

Every number that drives the simulation, with units, defaults, valid
ranges, and the modeling rationale. The same values live in two
synchronized places:

- **\`CONFIG\` in [index.html](index.html)** — what the browser sim
  executes, with a rationale comment on every value (see
  [DESIGN_NOTES.md](DESIGN_NOTES.md) for the tuning story).
- **The parameter table in
  [fpv-sim-mcp](https://github.com/wasomma/fpv-sim-mcp)**
  (\`src/server/params.ts\`) — machine-readable metadata that generates both
  that server's input validation and its \`get_config_schema\` tool, so what
  the tools document and what they accept cannot drift. This file is
  generated from that table for the same reason.

How to read the groups: **DRONE** and **CUAS** are the *hardware* —
identical for both sides. **FIX** is the *judgment* — how much evidence the
estimator demands before acting. **TEAMS** is the *doctrine* — and the
[Monte Carlo study](MONTE_CARLO.md) showed the outcome asymmetry lives
entirely in that layer.

All values are notional. Change a number, reload, replay the same seed,
and compare outcomes — or override any of them per-engagement through the
MCP server's \`config_overrides\`.

## DRONE — the aircraft and its attack profile

Flight performance, the endurance economy that sets the engagement's clock
pressure (battery, loiter drain, the bingo-fuel threshold that forces a
final push), and terminal-attack geometry.

${sectionTable("DRONE")}

## CUAS — the RF direction-finding sensors

The collection model: how often the DF nodes scan, how far they see, how
noisy their bearings are, and how detectable each emitter class is per
scan. The uplink/downlink detection gap (${D.CUAS.P_DETECT_UL} vs
${D.CUAS.P_DETECT_DL}) is why continuous video is so punishing.

${sectionTable("CUAS")}

## FIX — the estimator's decision gates

CEP quality gates and minimum-evidence rules, including the balanced
multi-sensor gate (\`MIN_LOBS_2ND\`) that keeps the estimator honest about
single-sensor geometry.

${sectionTable("FIX")}

## TEAMS — per-side doctrine (EMCON posture and launch time)

The only stock asymmetry between the sides. \`videoOff: 0\` means
continuous video downlink and forces the CONTINUOUS EMCON label.

${teamsTable()}

## Not tunable — structural constants and derived values

${table(payload.not_overridable.map((n) => `| \`${n.path}\` | ${esc(n.reason)} |`),
  "| Path | Why not |")}

Fixed structural values: the world is ${D.WORLD_M} × ${D.WORLD_M} m, the
physics tick is ${D.SIM_DT} s, and terrain plus unit emplacements are
generated from the seed — scenario geography is what a seed *reproduces*,
not a knob.

## Determinism

${payload.determinism_note}
`;

const outPath = join(import.meta.dirname, "..", "PARAMETERS.md");
writeFileSync(outPath, doc);
console.error("wrote " + outPath);
