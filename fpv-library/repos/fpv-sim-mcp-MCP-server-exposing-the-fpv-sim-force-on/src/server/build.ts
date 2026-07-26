/*
 * fpv-sim-mcp — server construction, shared by every transport entry point.
 *
 * buildServer() registers the five tools and two documentation resources on a
 * fresh McpServer. Every call constructs a fresh Simulation, so concurrent
 * calls cannot contaminate each other and identical inputs always return
 * identical outputs. The stdio entry (index.ts) builds one server for the
 * life of the process; the HTTP entry (http.ts) builds one per request,
 * which the engine's statelessness makes safe.
 *
 * All simulation data is notional and unclassified.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  runEngagement, aggregateSweep, comparePaired,
  type ConfigOverrides, type EngagementResult,
} from "../engine/index.js";
import { configOverridesSchema, buildConfigSchemaPayload } from "./params.js";
import { MODEL_DESCRIPTION } from "./model.js";
import { comparisonSummary } from "./summary.js";

export const SERVER_VERSION = "0.1.0";
const SWEEP_MAX = 1000;
const COMPARE_MAX = 500;

/* dist/src/server/build.js -> package root is three levels up. */
const here = path.dirname(fileURLToPath(import.meta.url));
const pkgRoot = path.resolve(here, "..", "..", "..");

const json = (data: unknown) => ({
  content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }],
});

const seedSchema = z.number().int().min(0).max(4294967295)
  .describe("Deterministic engagement seed. The same seed always replays the identical engagement. Featured seeds: 20260719 (standard BLUFOR win), 66 (fast BLUFOR win), 57 (deliberate BLUFOR win), 41 (OPFOR win), 59 (close race, OPFOR).");

const overridesInput = configOverridesSchema.optional()
  .describe("Optional partial CONFIG overrides. Call get_config_schema for the parameter table.");

function sweep(startSeed: number, count: number, overrides?: ConfigOverrides): EngagementResult[] {
  const results: EngagementResult[] = [];
  for (let s = startSeed; s < startSeed + count; s++) {
    results.push(runEngagement(s, overrides));
  }
  return results;
}

export function buildServer(): McpServer {
  const server = new McpServer({ name: "fpv-sim-mcp", version: SERVER_VERSION });

  server.registerTool(
    "run_engagement",
    {
      title: "Run one engagement",
      description:
        "Run a single deterministic force-on-force engagement to completion and return the full record: winner " +
        "(or STALEMATE) with reason, duration, phase timeline, per-team fix quality (CEP breakdown), LOB and " +
        "intercept counts per DF node, key event timestamps, drone/GCS end states, and the complete event log. " +
        "Notional data.",
      inputSchema: {
        seed: seedSchema,
        config_overrides: overridesInput,
      },
      annotations: { readOnlyHint: true },
    },
    async ({ seed, config_overrides }) => json(runEngagement(seed, config_overrides)),
  );

  server.registerTool(
    "sweep_seeds",
    {
      title: "Sweep a seed range",
      description:
        "Run count consecutive seeds (start_seed .. start_seed+count-1) under one configuration and return " +
        "aggregate statistics only: win rates by team including STALEMATE, time-to-fix and time-to-kill " +
        "distributions (mean/median/p10/p90), duration distribution, stalemate reasons, and notable seeds worth " +
        "drilling into with run_engagement. Aggregation is computed server-side; per-run event logs are not " +
        `returned. Max count ${SWEEP_MAX}.`,
      inputSchema: {
        start_seed: seedSchema,
        count: z.number().int().min(1).max(SWEEP_MAX).describe("Number of consecutive seeds to run."),
        config_overrides: overridesInput,
      },
      annotations: { readOnlyHint: true },
    },
    async ({ start_seed, count, config_overrides }) =>
      json(aggregateSweep(sweep(start_seed, count, config_overrides))),
  );

  server.registerTool(
    "compare_configs",
    {
      title: "Compare two configurations over the same seeds",
      description:
        "Run two CONFIG variants over the SAME consecutive seed range (a paired experimental design: terrain and " +
        "emplacement luck cancel out, so a few hundred seeds resolve real effect differences) and return each " +
        "variant's aggregate statistics, the paired outcome deltas, the seeds whose outcome flipped, and a " +
        "plain-language summary generated from those numbers. Use it to test doctrine questions, e.g. what happens " +
        `to win rates when OPFOR adopts EMCON discipline. Max count ${COMPARE_MAX}.`,
      inputSchema: {
        start_seed: seedSchema,
        count: z.number().int().min(1).max(COMPARE_MAX).describe("Number of consecutive seeds run under BOTH variants."),
        config_a: configOverridesSchema.describe("Variant A overrides (may be {} for the stock configuration)."),
        config_b: configOverridesSchema.describe("Variant B overrides (may be {} for the stock configuration)."),
        label_a: z.string().max(80).optional().describe("Human-readable name for variant A."),
        label_b: z.string().max(80).optional().describe("Human-readable name for variant B."),
      },
      annotations: { readOnlyHint: true },
    },
    async ({ start_seed, count, config_a, config_b, label_a, label_b }) => {
      const labelA = label_a ?? "variant A";
      const labelB = label_b ?? "variant B";
      const runsA = sweep(start_seed, count, config_a);
      const runsB = sweep(start_seed, count, config_b);
      const summaryA = aggregateSweep(runsA);
      const summaryB = aggregateSweep(runsB);
      const paired = comparePaired(runsA, runsB);
      return json({
        seeds: { start: start_seed, count },
        variant_a: { label: labelA, overrides: config_a, ...summaryA },
        variant_b: { label: labelB, overrides: config_b, ...summaryB },
        paired,
        summary: comparisonSummary(labelA, labelB, summaryA, summaryB, paired),
      });
    },
  );

  server.registerTool(
    "describe_model",
    {
      title: "Describe the simulation model",
      description:
        "Return the modeling assumptions: DF measurement and bearing-error model, RF propagation, fix estimation " +
        "and its quality gates, drone state machine, EMCON semantics, outcome definitions, and the known " +
        "simplifications. Read this before drawing conclusions from simulation results — it states what the model " +
        "can and cannot support.",
      inputSchema: {},
      annotations: { readOnlyHint: true },
    },
    async () => json(MODEL_DESCRIPTION),
  );

  server.registerTool(
    "get_config_schema",
    {
      title: "Get the tunable-parameter schema",
      description:
        "Return every parameter accepted in config_overrides: path, unit, default, sane range, and description — " +
        "plus the parameters that are deliberately not overridable and why. This is generated from the same table " +
        "that validates tool inputs, so it cannot drift from actual behavior.",
      inputSchema: {},
      annotations: { readOnlyHint: true },
    },
    async () => json(buildConfigSchemaPayload()),
  );

  /* ------------------------------ resources ------------------------------ */

  server.registerResource(
    "design-notes",
    "fpv-sim://design-notes",
    {
      title: "Original simulation design notes",
      description:
        "Technical write-up of the original browser simulation this server wraps: terrain and RF models, the DF " +
        "fix math and its honesty gates, drone behavior, tuning guide, and known simplifications.",
      mimeType: "text/markdown",
    },
    async (uri) => ({
      contents: [{ uri: uri.href, mimeType: "text/markdown", text: readDesignNotes().text }],
    }),
  );

  server.registerResource(
    "mcp-design-notes",
    "fpv-sim://mcp-design-notes",
    {
      title: "MCP server design notes",
      description:
        "How this project extracted the browser sim into a headless engine, how determinism parity is verified, " +
        "and why the MCP interface looks the way it does.",
      mimeType: "text/markdown",
    },
    async (uri) => ({
      contents: [{
        uri: uri.href,
        mimeType: "text/markdown",
        text: readFileSync(path.join(pkgRoot, "DESIGN_NOTES.md"), "utf8"),
      }],
    }),
  );

  return server;
}

function readDesignNotes(): { text: string; origin: string } {
  // Prefer a live sibling checkout of the original repo; fall back to the
  // snapshot bundled with this package (see docs/upstream/SNAPSHOT.md).
  const sibling = path.resolve(pkgRoot, "..", "fpv-sim", "DESIGN_NOTES.md");
  if (existsSync(sibling)) {
    return { text: readFileSync(sibling, "utf8"), origin: sibling };
  }
  const snapshot = path.join(pkgRoot, "docs", "upstream", "DESIGN_NOTES.md");
  return { text: readFileSync(snapshot, "utf8"), origin: snapshot };
}
