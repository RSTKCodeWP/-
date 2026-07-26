/*
 * Unit tests for sweep aggregation and the paired configuration comparison,
 * over hand-built engagement results with known statistics.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { aggregateSweep, comparePaired, distribution } from "../src/engine/index.js";
import type { EngagementResult, OutcomeReason, OutcomeResult } from "../src/engine/index.js";

function mkResult(
  seed: number,
  result: OutcomeResult,
  duration: number,
  ttf: { BLUFOR?: number; OPFOR?: number } = {},
  reason?: OutcomeReason,
): EngagementResult {
  const team = (side: "BLUFOR" | "OPFOR") => ({
    emcon_label: "TEST",
    launch_t_s: 20,
    first_lob_t_s: null,
    first_dl_intercept_t_s: null,
    fix_established_t_s: ttf[side] ?? null,
    commit_t_s: null,
    lobs_held: 0,
    nodes: [],
    fix: null,
    drone: { end_state: "DOWN", battery_pct: 0, x: 0, y: 0 },
    gcs: { destroyed: false, x: 0, y: 0 },
  });
  return {
    seed,
    outcome: {
      result,
      reason: reason ?? (result === "STALEMATE" ? "time_limit" : "gcs_destroyed"),
    },
    duration_s: duration,
    phase_timeline: [],
    teams: { BLUFOR: team("BLUFOR"), OPFOR: team("OPFOR") },
    events: [],
  };
}

test("distribution: interpolated percentiles over a known set", () => {
  const d = distribution([40, 10, 30, 20]); // unsorted on purpose
  assert.ok(d);
  assert.equal(d.n, 4);
  assert.equal(d.mean, 25);
  assert.equal(d.median, 25);
  assert.equal(d.p10, 13);  // idx 0.3 between 10 and 20
  assert.equal(d.p90, 37);  // idx 2.7 between 30 and 40
  assert.equal(d.min, 10);
  assert.equal(d.max, 40);
  assert.equal(distribution([]), null);
});

test("aggregateSweep: counts, rates, time-to-fix/kill populations", () => {
  const results = [
    mkResult(100, "BLUFOR", 300, { BLUFOR: 120 }),
    mkResult(101, "BLUFOR", 500, { BLUFOR: 200, OPFOR: 400 }),
    mkResult(102, "OPFOR", 250, { OPFOR: 100 }),
    mkResult(103, "STALEMATE", 3600, {}, "time_limit"),
    mkResult(104, "STALEMATE", 2000, {}, "both_drones_down"),
  ];
  const s = aggregateSweep(results);
  assert.equal(s.runs, 5);
  assert.equal(s.start_seed, 100);
  assert.equal(s.end_seed, 104);
  assert.deepEqual(s.outcomes, { BLUFOR: 2, OPFOR: 1, STALEMATE: 2 });
  assert.deepEqual(s.win_rates, { BLUFOR: 0.4, OPFOR: 0.2, STALEMATE: 0.4 });
  // Time-to-kill only over the three decisive runs.
  assert.ok(s.time_to_kill_s);
  assert.equal(s.time_to_kill_s.n, 3);
  assert.equal(s.time_to_kill_s.mean, 350);
  // Time-to-fix only over runs where the side actually fixed.
  assert.equal(s.time_to_fix_s.BLUFOR?.n, 2);
  assert.equal(s.time_to_fix_s.BLUFOR?.mean, 160);
  assert.equal(s.time_to_fix_s.OPFOR?.n, 2);
  assert.deepEqual(s.stalemate_reasons, { time_limit: 1, both_drones_down: 1 });
  assert.deepEqual(s.notable_seeds.fastest_kill, { seed: 102, winner: "OPFOR", t_s: 250 });
  assert.deepEqual(s.notable_seeds.slowest_kill, { seed: 101, winner: "BLUFOR", t_s: 500 });
  assert.equal(s.notable_seeds.example_stalemate, 103);
  assert.throws(() => aggregateSweep([]), /empty result set/);
});

test("comparePaired: flips, deltas, and input validation", () => {
  const a = [
    mkResult(1, "BLUFOR", 300, { BLUFOR: 100 }),
    mkResult(2, "BLUFOR", 400, { BLUFOR: 150 }),
    mkResult(3, "OPFOR", 350),
    mkResult(4, "STALEMATE", 3600),
  ];
  const b = [
    mkResult(1, "BLUFOR", 320, { BLUFOR: 140 }),
    mkResult(2, "OPFOR", 500, { BLUFOR: 260 }),   // flip
    mkResult(3, "OPFOR", 340),
    mkResult(4, "OPFOR", 900),                    // flip
  ];
  const p = comparePaired(a, b);
  assert.equal(p.same_outcome, 2);
  assert.equal(p.flips_total, 2);
  assert.deepEqual(p.flips_sample, [
    { seed: 2, a: "BLUFOR", b: "OPFOR" },
    { seed: 4, a: "STALEMATE", b: "OPFOR" },
  ]);
  // A: BLUFOR 0.5, OPFOR 0.25, stalemate 0.25 -> B: 0.25 / 0.75 / 0.
  assert.equal(p.blufor_win_rate_delta, -0.25);
  assert.equal(p.opfor_win_rate_delta, 0.5);
  assert.equal(p.stalemate_rate_delta, -0.25);
  // BLUFOR mean TTF: A (100+150)/2 = 125, B (140+260)/2 = 200 -> +75.
  assert.equal(p.mean_time_to_fix_delta_s.BLUFOR, 75);
  assert.equal(p.mean_time_to_fix_delta_s.OPFOR, null);

  assert.throws(() => comparePaired(a, b.slice(0, 3)), /differ in length/);
  const wrongSeeds = [...b.slice(1), mkResult(99, "BLUFOR", 100)];
  assert.throws(() => comparePaired(a, wrongSeeds), /seed mismatch/);
});
