/*
 * Demo: exercise the fpv-sim-mcp server over stdio exactly the way an MCP
 * client (Claude Desktop, Claude Code, ...) would.
 *
 *   1. Run one featured engagement and print its story.
 *   2. Run a 200-seed paired comparison: stock OPFOR (continuous emitter)
 *      vs OPFOR adopting BLUFOR's EMCON discipline — the doctrine question
 *      the original demo was built to answer — and print the win-rate table.
 *
 * Run with: npm run demo
 */

import path from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const here = path.dirname(fileURLToPath(import.meta.url));
// Compiled location is dist/examples/; the server entry sits in dist/src/server/.
const serverPath = path.resolve(here, "..", "src", "server", "index.js");

interface ToolResponse { content: { type: string; text: string }[]; }

function parseTool<T>(res: unknown): T {
  const first = (res as ToolResponse).content[0];
  if (!first || first.type !== "text") throw new Error("unexpected tool response shape");
  return JSON.parse(first.text) as T;
}

const client = new Client({ name: "fpv-sim-mcp-demo", version: "0.1.0" });
await client.connect(new StdioClientTransport({ command: process.execPath, args: [serverPath] }));

/* ---------------- 1. single engagement ---------------- */

console.log("=".repeat(72));
console.log("run_engagement // seed 20260719 (featured: Standard Engagement)");
console.log("=".repeat(72));

interface RunResult {
  outcome: { result: string; reason: string };
  duration_s: number;
  phase_timeline: { t: number; phase: string }[];
  teams: Record<string, {
    emcon_label: string;
    fix_established_t_s: number | null;
    commit_t_s: number | null;
    lobs_held: number;
    fix: { cep_m: number } | null;
    drone: { end_state: string; battery_pct: number };
  }>;
  events: { t: number; side: string; text: string }[];
}

const run = parseTool<RunResult>(
  await client.callTool({ name: "run_engagement", arguments: { seed: 20260719 } }),
);

console.log(`outcome : ${run.outcome.result} (${run.outcome.reason}) at T+${run.duration_s}s`);
for (const [side, t] of Object.entries(run.teams)) {
  console.log(
    `${side.padEnd(6)} : EMCON ${t.emcon_label.padEnd(12)} fix@${String(t.fix_established_t_s ?? "--").padStart(6)}s ` +
    `commit@${String(t.commit_t_s ?? "--").padStart(6)}s LOBs ${String(t.lobs_held).padStart(3)} ` +
    `CEP ${t.fix ? Math.round(t.fix.cep_m) + "m" : "none"}  drone ${t.drone.end_state} @ ${Math.round(t.drone.battery_pct)}%`,
  );
}
console.log("\nphases  :", run.phase_timeline.map((p) => `${p.phase} @ ${p.t}s`).join(" -> "));
console.log("\nlast events:");
for (const e of run.events.slice(-5)) {
  console.log(`  T+${String(e.t).padStart(6)} [${e.side.padEnd(6)}] ${e.text}`);
}

/* ---------------- 2. paired EMCON comparison ---------------- */

console.log();
console.log("=".repeat(72));
console.log("compare_configs // 200 seeds // stock vs OPFOR adopting EMCON discipline");
console.log("=".repeat(72));

interface CompareResult {
  variant_a: { label: string; win_rates: Record<string, number>; outcomes: Record<string, number> };
  variant_b: { label: string; win_rates: Record<string, number>; outcomes: Record<string, number> };
  paired: { flips_total: number };
  summary: string;
}

const cmp = parseTool<CompareResult>(
  await client.callTool({
    name: "compare_configs",
    arguments: {
      start_seed: 1000,
      count: 200,
      config_a: {},
      config_b: { TEAMS: { OPFOR: { uplinkOn: 4, uplinkOff: 13, videoOn: 3, videoOff: 7 } } },
      label_a: "stock (OPFOR continuous emitter)",
      label_b: "OPFOR adopts BLUFOR's EMCON discipline",
    },
  }),
);

const col = (v: string | number, w: number): string => String(v).padStart(w);
const pct = (v: number): string => (v * 100).toFixed(1) + "%";
console.log(`\n${"variant".padEnd(42)}${col("BLUFOR", 10)}${col("OPFOR", 10)}${col("STALEMATE", 12)}`);
for (const v of [cmp.variant_a, cmp.variant_b]) {
  console.log(
    `${v.label.padEnd(42)}${col(pct(v.win_rates.BLUFOR), 10)}${col(pct(v.win_rates.OPFOR), 10)}${col(pct(v.win_rates.STALEMATE), 12)}`,
  );
}
console.log(`\noutcome flips across the same 200 seeds: ${cmp.paired.flips_total}`);
console.log(`\nsummary:\n${cmp.summary}`);

await client.close();
