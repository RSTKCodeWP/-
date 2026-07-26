/*
 * Server-side aggregation over batches of engagement results.
 *
 * This lives next to the engine (not in the MCP layer) because it is pure
 * arithmetic over EngagementResult values and is unit-tested independently.
 * The design reason aggregation exists at all: a 200-seed sweep returned raw
 * would be hundreds of kilobytes of event logs; the statistics an agent
 * actually reasons over fit in a kilobyte and are deterministic to compute.
 */

import type { EngagementResult } from "./simulation.js";
import type { OutcomeReason, Side } from "./types.js";

export interface DistributionStats {
  mean: number;
  median: number;
  p10: number;
  p90: number;
  min: number;
  max: number;
  n: number;
}

export interface SweepSummary {
  runs: number;
  start_seed: number;
  end_seed: number;
  outcomes: { BLUFOR: number; OPFOR: number; STALEMATE: number };
  win_rates: { BLUFOR: number; OPFOR: number; STALEMATE: number };
  /* Time for each side to declare FIX ESTABLISHED, over runs where it did. */
  time_to_fix_s: Record<Side, DistributionStats | null>;
  /* Time from T0 to GCS kill, over decisive runs only. */
  time_to_kill_s: DistributionStats | null;
  duration_s: DistributionStats;
  stalemate_reasons: Partial<Record<OutcomeReason, number>>;
  notable_seeds: {
    fastest_kill: { seed: number; winner: Side; t_s: number } | null;
    slowest_kill: { seed: number; winner: Side; t_s: number } | null;
    example_stalemate: number | null;
  };
}

const round1 = (v: number): number => Math.round(v * 10) / 10;

export function distribution(values: number[]): DistributionStats | null {
  if (values.length === 0) return null;
  const s = [...values].sort((a, b) => a - b);
  const pick = (p: number): number => {
    const idx = (s.length - 1) * p;
    const lo = Math.floor(idx), hi = Math.ceil(idx);
    return s[lo] + (s[hi] - s[lo]) * (idx - lo);
  };
  const mean = s.reduce((a, b) => a + b, 0) / s.length;
  return {
    mean: round1(mean),
    median: round1(pick(0.5)),
    p10: round1(pick(0.1)),
    p90: round1(pick(0.9)),
    min: round1(s[0]),
    max: round1(s[s.length - 1]),
    n: s.length,
  };
}

export function aggregateSweep(results: EngagementResult[]): SweepSummary {
  if (results.length === 0) throw new Error("aggregateSweep: empty result set");
  const outcomes = { BLUFOR: 0, OPFOR: 0, STALEMATE: 0 };
  const stalemateReasons: Partial<Record<OutcomeReason, number>> = {};
  const ttf: Record<Side, number[]> = { BLUFOR: [], OPFOR: [] };
  const ttk: number[] = [];
  const durations: number[] = [];
  let fastest: { seed: number; winner: Side; t_s: number } | null = null;
  let slowest: { seed: number; winner: Side; t_s: number } | null = null;
  let exampleStalemate: number | null = null;

  for (const r of results) {
    outcomes[r.outcome.result]++;
    durations.push(r.duration_s);
    if (r.outcome.result === "STALEMATE") {
      stalemateReasons[r.outcome.reason] = (stalemateReasons[r.outcome.reason] ?? 0) + 1;
      if (exampleStalemate === null) exampleStalemate = r.seed;
    } else {
      const winner = r.outcome.result;
      ttk.push(r.duration_s);
      if (!fastest || r.duration_s < fastest.t_s) fastest = { seed: r.seed, winner, t_s: r.duration_s };
      if (!slowest || r.duration_s > slowest.t_s) slowest = { seed: r.seed, winner, t_s: r.duration_s };
    }
    for (const side of ["BLUFOR", "OPFOR"] as const) {
      const t = r.teams[side].fix_established_t_s;
      if (t !== null) ttf[side].push(t);
    }
  }

  const n = results.length;
  const rate = (c: number): number => Math.round((c / n) * 1000) / 1000;
  return {
    runs: n,
    start_seed: results[0].seed,
    end_seed: results[results.length - 1].seed,
    outcomes,
    win_rates: { BLUFOR: rate(outcomes.BLUFOR), OPFOR: rate(outcomes.OPFOR), STALEMATE: rate(outcomes.STALEMATE) },
    time_to_fix_s: { BLUFOR: distribution(ttf.BLUFOR), OPFOR: distribution(ttf.OPFOR) },
    time_to_kill_s: distribution(ttk),
    duration_s: distribution(durations)!,
    stalemate_reasons: stalemateReasons,
    notable_seeds: { fastest_kill: fastest, slowest_kill: slowest, example_stalemate: exampleStalemate },
  };
}

export interface PairedFlip { seed: number; a: string; b: string; }

export interface PairedComparison {
  same_outcome: number;
  flips_total: number;
  flips_sample: PairedFlip[];
  blufor_win_rate_delta: number;  // variant B minus variant A
  opfor_win_rate_delta: number;
  stalemate_rate_delta: number;
  mean_time_to_fix_delta_s: Record<Side, number | null>; // B minus A, per fixing side
}

/* Paired (same-seed) comparison of two variants. Both inputs must cover the
   identical seed list in the same order. */
export function comparePaired(a: EngagementResult[], b: EngagementResult[]): PairedComparison {
  if (a.length !== b.length) throw new Error("comparePaired: result sets differ in length");
  let same = 0;
  const flips: PairedFlip[] = [];
  for (let i = 0; i < a.length; i++) {
    if (a[i].seed !== b[i].seed) throw new Error("comparePaired: seed mismatch at index " + i);
    if (a[i].outcome.result === b[i].outcome.result) same++;
    else flips.push({ seed: a[i].seed, a: a[i].outcome.result, b: b[i].outcome.result });
  }
  const sa = aggregateSweep(a), sb = aggregateSweep(b);
  const d3 = (v: number): number => Math.round(v * 1000) / 1000;
  const ttfDelta = (side: Side): number | null => {
    const ta = sa.time_to_fix_s[side], tb = sb.time_to_fix_s[side];
    if (!ta || !tb) return null;
    return Math.round((tb.mean - ta.mean) * 10) / 10;
  };
  return {
    same_outcome: same,
    flips_total: flips.length,
    flips_sample: flips.slice(0, 25),
    blufor_win_rate_delta: d3(sb.win_rates.BLUFOR - sa.win_rates.BLUFOR),
    opfor_win_rate_delta: d3(sb.win_rates.OPFOR - sa.win_rates.OPFOR),
    stalemate_rate_delta: d3(sb.win_rates.STALEMATE - sa.win_rates.STALEMATE),
    mean_time_to_fix_delta_s: { BLUFOR: ttfDelta("BLUFOR"), OPFOR: ttfDelta("OPFOR") },
  };
}
