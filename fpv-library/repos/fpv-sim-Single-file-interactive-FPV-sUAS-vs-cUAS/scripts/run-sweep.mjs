/*
 * Ad-hoc sweep runner: run any seed range under any config overrides and
 * save the result as a labeled dashboard dataset.
 *
 * Where monte-carlo-study.mjs produces the canonical multi-experiment
 * study, this produces a single-sweep dataset marked kind:"adhoc" — the
 * dashboard shows these with an AD-HOC prefix in the dataset dropdown and
 * lets viewers filter them out. Commit the written files (the dataset
 * JSON and results/index.json) to publish; uncommitted output is local
 * only.
 *
 * Usage:
 *   node scripts/run-sweep.mjs --label "DF bearing error doubled" \
 *     [--start 1] [--count 1000] [--overrides '{"CUAS":{"BRG_SIGMA_DEG":8}}']
 *
 * Deterministic: identical (start, count, overrides) always reproduces
 * the identical dataset. Overrides are validated by the engine the same
 * way the MCP server validates config_overrides.
 */

import { join, basename } from "node:path";
import { writeFileSync, mkdirSync } from "node:fs";
import { parseArgs } from "node:util";
import { loadEngine, seeds, buildAgg, gitCommit, registerDataset, REPO_ROOT, RESULTS_DIR } from "./sweep-utils.mjs";

const { values: args } = parseArgs({
  options: {
    label: { type: "string" },
    start: { type: "string", default: "1" },
    count: { type: "string", default: "1000" },
    overrides: { type: "string" },
  },
});

if (!args.label || !args.label.trim()) {
  console.error('A --label is required — it names the dataset in the dashboard dropdown.');
  console.error('Example: node scripts/run-sweep.mjs --label "DF bearing error doubled" --overrides \'{"CUAS":{"BRG_SIGMA_DEG":8}}\'');
  process.exit(1);
}
const label = args.label.trim();
const start = Number.parseInt(args.start, 10);
const count = Number.parseInt(args.count, 10);
if (!Number.isInteger(start) || start < 0 || !Number.isInteger(count) || count < 1) {
  console.error("--start must be a non-negative integer and --count a positive integer.");
  process.exit(1);
}
let overrides;
if (args.overrides) {
  try {
    overrides = JSON.parse(args.overrides);
  } catch (err) {
    console.error("--overrides is not valid JSON: " + err.message);
    process.exit(1);
  }
}

const { engine, mcpRoot } = await loadEngine();
const { runEngagement, aggregateSweep } = engine;

console.error(`Sweeping seeds ${start}–${start + count - 1}` +
  (overrides ? ` with overrides ${JSON.stringify(overrides)}` : " (stock config)") + "...");
const t0 = Date.now();
const results = seeds(start, count).map((s) => runEngagement(s, overrides));
const agg = buildAgg(results, aggregateSweep);
console.error(`  ${agg.runs} runs in ${((Date.now() - t0) / 1000).toFixed(1)}s ` +
  `— B ${agg.outcomes.BLUFOR} / O ${agg.outcomes.OPFOR} / S ${agg.outcomes.STALEMATE}`);

const generated = new Date().toISOString();
const slug = label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 48);
const outFile = `adhoc-${slug}-${generated.slice(0, 10)}.json`;

const dataset = {
  kind: "adhoc",
  label,
  quick: false,
  meta: {
    generated,
    sim_commit: gitCommit(REPO_ROOT),
    engine_commit: gitCommit(mcpRoot),
    engine_source: "https://github.com/wasomma/fpv-sim-mcp",
    total_runs: agg.runs,
    seed_range: { start, count },
    overrides: overrides ?? null,
  },
  experiments: { baseline: agg },
};

mkdirSync(RESULTS_DIR, { recursive: true });
const outPath = join(RESULTS_DIR, outFile);
writeFileSync(outPath, JSON.stringify(dataset, null, 2));
registerDataset({
  file: outFile,
  kind: "adhoc",
  label,
  generated,
  sim_commit: dataset.meta.sim_commit,
  engine_commit: dataset.meta.engine_commit,
  total_runs: agg.runs,
  overrides: overrides ?? null,
  baseline: { runs: agg.runs, win_rates: agg.win_rates },
});
console.error(`\nWrote ${outPath} and registered it in results/index.json.`);
console.error(`Commit both to publish on the dashboard; delete the file and its manifest entry to retire it.`);
