/*
 * Monte Carlo study of fpv-sim using the headless engine from fpv-sim-mcp.
 *
 * The browser sim (index.html) runs one watchable engagement per seed. This
 * script turns that into a statistical experiment: thousands of independent
 * replications, aggregated. It deliberately does NOT reimplement the engine —
 * it imports the extracted, golden-master-verified engine from a checkout of
 * https://github.com/wasomma/fpv-sim-mcp (behavior parity with index.html is
 * proven by that repo's tests).
 *
 * Usage:
 *   node scripts/monte-carlo-study.mjs [--quick]
 *
 * The fpv-sim-mcp checkout is located via $FPV_SIM_MCP, defaulting to a
 * sibling directory (../fpv-sim-mcp). It must be built (`npm install && npm
 * test` there) first. --quick runs ~1/10th the replications for a smoke pass.
 *
 * Everything is deterministic: fixed seed lists, one RNG stream per
 * engagement inside the engine. Rerunning this script reproduces every
 * number in MONTE_CARLO.md exactly.
 */

import { join } from "node:path";
import { writeFileSync, mkdirSync } from "node:fs";
import { loadEngine, seeds, buildAgg, gitCommit, registerDataset, REPO_ROOT, RESULTS_DIR } from "./sweep-utils.mjs";

const { engine, mcpRoot } = await loadEngine();
const { runEngagement, aggregateSweep, comparePaired } = engine;

const QUICK = process.argv.includes("--quick");
const scale = (n) => (QUICK ? Math.max(50, Math.round(n / 10)) : n);

/* Seed lists are contiguous ranges so any result is reproducible from the
   range alone (also directly reproducible via the MCP server's sweep_seeds /
   compare_configs tools for counts within their caps). */

let totalRuns = 0;

function sweep(seedList, overrides, label) {
  const t0 = Date.now();
  const results = seedList.map((s) => runEngagement(s, overrides));
  totalRuns += results.length;
  const agg = buildAgg(results, aggregateSweep);
  console.error(`  ${label}: ${agg.runs} runs in ${((Date.now() - t0) / 1000).toFixed(1)}s ` +
    `— B ${agg.outcomes.BLUFOR} / O ${agg.outcomes.OPFOR} / S ${agg.outcomes.STALEMATE}`);
  return { results, agg };
}

const study = {
  quick: QUICK,
  kind: "study",
  label: "Full study",
  meta: {
    generated: new Date().toISOString(),
    sim_commit: gitCommit(REPO_ROOT),
    engine_commit: gitCommit(mcpRoot),
    engine_source: "https://github.com/wasomma/fpv-sim-mcp",
  },
  experiments: {},
};

/* ---------------------------------------------------------------- E1
 * Baseline: stock CONFIG over a large seed range. The headline number:
 * how often does the disciplined side actually win? */
console.error("E1 baseline (stock config)...");
{
  const list = seeds(1, scale(10000));
  const { agg } = sweep(list, undefined, "stock");
  study.experiments.baseline = agg;
}

/* ---------------------------------------------------------------- E2
 * Paired same-seed comparisons. Terrain, emplacement jitter, and noise
 * draws are seed-determined, so comparing variants on identical seed lists
 * is a common-random-numbers design: per-seed luck cancels out of the
 * deltas, and a couple thousand pairs resolve effects that would need far
 * more independent runs. */
const pairList = seeds(1, scale(2000));
const BLUFOR_EMCON = { uplinkOn: 4, uplinkOff: 13, videoOn: 3, videoOff: 7 };
const OPFOR_EMCON = { uplinkOn: 10, uplinkOff: 4, videoOn: 1, videoOff: 0 };

console.error("E2 stock arm (shared across paired comparisons)...");
const stockArm = sweep(pairList, undefined, "stock arm");

function paired(label, overridesB) {
  console.error(`E2 ${label}...`);
  const b = sweep(pairList, overridesB, "variant");
  return { variant: b.agg, paired: comparePaired(stockArm.results, b.results) };
}
study.experiments.pairedStockArm = stockArm.agg;

/* E2a — OPFOR adopts BLUFOR's duty cycles (launch stagger kept). Isolates
   what discipline is worth to the currently-undisciplined side. */
study.experiments.opforAdoptsDiscipline =
  paired("OPFOR adopts BLUFOR discipline", { TEAMS: { OPFOR: BLUFOR_EMCON } });

/* E2b — full posture swap (launch stagger kept). If EMCON is the causal
   asymmetry, the win-rate gap should follow the discipline, not the team. */
study.experiments.postureSwap =
  paired("full EMCON posture swap",
    { TEAMS: { BLUFOR: OPFOR_EMCON, OPFOR: BLUFOR_EMCON } });

/* E2c — launch stagger equalized (both launch T+20), EMCON stock. Sizes the
   one non-EMCON asymmetry so E2a/E2b residuals are interpretable. */
study.experiments.launchEqualized =
  paired("launch stagger equalized", { TEAMS: { OPFOR: { launchT: 20 } } });

/* ---------------------------------------------------------------- E3
 * Sensitivity: OPFOR uplink duty cycle. Fixed 14 s period (matching the
 * stock postures' period), on-time swept 2..12 s, at both video postures.
 * Yields the "how much does discipline buy" curve behind the headline. */
console.error("E3 uplink duty-cycle sensitivity...");
{
  const cellSeeds = seeds(1, scale(400));
  const PERIOD = 14;
  const cells = [];
  for (const video of [{ label: "continuous", videoOn: 1, videoOff: 0 },
                       { label: "burst", videoOn: 3, videoOff: 7 }]) {
    for (const on of [2, 4, 6, 8, 10, 12]) {
      const ov = { TEAMS: { OPFOR: { uplinkOn: on, uplinkOff: PERIOD - on, videoOn: video.videoOn, videoOff: video.videoOff } } };
      const { agg } = sweep(cellSeeds, ov, `uplink ${on}/${PERIOD - on} video ${video.label}`);
      cells.push({
        opfor_uplink_on_s: on, opfor_uplink_off_s: PERIOD - on,
        opfor_uplink_duty: Math.round((on / PERIOD) * 1000) / 1000,
        opfor_video: video.label,
        n: agg.runs, outcomes: agg.outcomes, win_rates: agg.win_rates, ci95: agg.ci95,
        opfor_mean_ttf_by_blufor_s: agg.time_to_fix_s.BLUFOR?.mean ?? null,
      });
    }
  }
  study.experiments.uplinkDutySensitivity = { period_s: PERIOD, seeds_per_cell: cellSeeds.length, cells };
}

study.meta.total_runs = totalRuns;

mkdirSync(RESULTS_DIR, { recursive: true });
const outFile = QUICK ? "monte-carlo-quick.json" : "monte-carlo.json";
const outPath = join(RESULTS_DIR, outFile);
writeFileSync(outPath, JSON.stringify(study, null, 2));
console.error(`\nWrote ${outPath} (${totalRuns} engagements)`);

/* Register full runs in the manifest the dashboard reads. Quick runs are
   dev smoke passes and stay out of it. */
if (!QUICK) {
  const manifestPath = registerDataset({
    file: outFile,
    kind: "study",
    label: "Full study",
    generated: study.meta.generated,
    sim_commit: study.meta.sim_commit,
    engine_commit: study.meta.engine_commit,
    total_runs: totalRuns,
    baseline: {
      runs: study.experiments.baseline.runs,
      win_rates: study.experiments.baseline.win_rates,
    },
  });
  console.error(`Updated ${manifestPath}`);
}
