/*
 * Shared helpers for the study runner (monte-carlo-study.mjs) and the
 * ad-hoc sweep runner (run-sweep.mjs): engine loading, aggregation
 * post-processing (Wilson CIs, histograms), provenance, and manifest
 * registration. One implementation so the two runners cannot drift.
 */

import { pathToFileURL } from "node:url";
import { resolve, join } from "node:path";
import { writeFileSync, readFileSync, existsSync, mkdirSync } from "node:fs";
import { execSync } from "node:child_process";

export const REPO_ROOT = join(import.meta.dirname, "..");
export const RESULTS_DIR = join(REPO_ROOT, "results");

export async function loadEngine() {
  const mcpRoot = resolve(process.env.FPV_SIM_MCP ?? join(REPO_ROOT, "..", "fpv-sim-mcp"));
  const enginePath = join(mcpRoot, "dist", "src", "engine", "index.js");
  try {
    return { engine: await import(pathToFileURL(enginePath).href), mcpRoot };
  } catch (err) {
    console.error(`Cannot load engine at ${enginePath}.`);
    console.error("Clone and build fpv-sim-mcp first (npm install && npm test), or set $FPV_SIM_MCP.");
    throw err;
  }
}

export const seeds = (start, count) => Array.from({ length: count }, (_, i) => start + i);

/* 95% Wilson score interval for a binomial proportion — preferred over the
   normal approximation because win rates sit well away from 0.5 and sweep
   sizes vary. */
export function wilson(successes, n) {
  if (n === 0) return null;
  const z = 1.959963984540054, p = successes / n;
  const denom = 1 + (z * z) / n;
  const center = (p + (z * z) / (2 * n)) / denom;
  const half = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / denom;
  const r = (v) => Math.round(v * 10000) / 10000;
  return { p: r(p), lo: r(center - half), hi: r(center + half) };
}

/* Fixed-width binning so the dashboard can draw distribution shapes; the
   summary stats alone (mean/median/p10/p90) hide bimodality. */
export const HIST_BIN_S = 60;
export function histogram(values) {
  if (values.length === 0) return null;
  const counts = [];
  for (const v of values) {
    const bin = Math.floor(v / HIST_BIN_S);
    counts[bin] = (counts[bin] ?? 0) + 1;
  }
  for (let i = 0; i < counts.length; i++) counts[i] = counts[i] ?? 0;
  return { bin_width_s: HIST_BIN_S, counts, n: values.length };
}

/* aggregateSweep output extended with CIs and histograms — the aggregate
   shape the dashboard renders. */
export function buildAgg(results, aggregateSweep) {
  const agg = aggregateSweep(results);
  const n = agg.runs;
  agg.ci95 = {
    BLUFOR: wilson(agg.outcomes.BLUFOR, n),
    OPFOR: wilson(agg.outcomes.OPFOR, n),
    STALEMATE: wilson(agg.outcomes.STALEMATE, n),
  };
  agg.histograms = {
    time_to_fix_s: {
      BLUFOR: histogram(results.map((r) => r.teams.BLUFOR.fix_established_t_s).filter((t) => t !== null)),
      OPFOR: histogram(results.map((r) => r.teams.OPFOR.fix_established_t_s).filter((t) => t !== null)),
    },
    time_to_kill_s: histogram(results.filter((r) => r.outcome.result !== "STALEMATE").map((r) => r.duration_s)),
  };
  return agg;
}

export function gitCommit(dir) {
  try {
    return execSync("git rev-parse HEAD", { cwd: dir, encoding: "utf8" }).trim();
  } catch {
    return null;
  }
}

/* Upsert a dataset entry (keyed by file) into the manifest the dashboard
   reads. Newest first. */
export function registerDataset(entry) {
  mkdirSync(RESULTS_DIR, { recursive: true });
  const manifestPath = join(RESULTS_DIR, "index.json");
  const manifest = existsSync(manifestPath)
    ? JSON.parse(readFileSync(manifestPath, "utf8"))
    : { datasets: [] };
  manifest.datasets = manifest.datasets.filter((d) => d.file !== entry.file);
  manifest.datasets.unshift(entry);
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
  return manifestPath;
}
