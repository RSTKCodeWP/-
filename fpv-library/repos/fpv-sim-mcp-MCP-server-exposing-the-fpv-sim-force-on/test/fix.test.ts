/*
 * Unit tests for the weighted least-squares fix math and its quality gates,
 * using synthetic LOB sets with known geometry.
 *
 * Bearing convention (from the sim): radians, true north = 0, clockwise
 * positive — brg = atan2(dx, dy).
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  computeEstimate, updateFix, DEFAULT_CONFIG, mulberry32, makeGauss,
} from "../src/engine/index.js";
import type { Measurement, Team } from "../src/engine/index.js";
import type { SimCtx } from "../src/engine/context.js";

const FIX = DEFAULT_CONFIG.FIX;
const SIG = (4 * Math.PI) / 180; // 4 deg, the sim's clean-conditions 1-sigma

const brg = (sx: number, sy: number, tx: number, ty: number): number => Math.atan2(tx - sx, ty - sy);

function lobs(sx: number, sy: number, tx: number, ty: number, n: number, noise?: () => number): Measurement[] {
  const out: Measurement[] = [];
  for (let i = 0; i < n; i++) {
    out.push({ sx, sy, brg: brg(sx, sy, tx, ty) + (noise ? noise() * SIG : 0), sig: SIG, t: i });
  }
  return out;
}

const START = { x: 900, y: 900 }; // deliberately offset initial guess

test("exact 90-degree cut from two balanced sensors recovers the target", () => {
  const M = [...lobs(0, 0, 1000, 1000, 5), ...lobs(2000, 0, 1000, 1000, 5)];
  const sol = computeEstimate(M, START, FIX);
  assert.ok(sol, "well-crossed geometry must solve");
  assert.ok(Math.abs(sol.p.x - 1000) < 1e-6, `x within 1e-6, got ${sol.p.x}`);
  assert.ok(Math.abs(sol.p.y - 1000) < 1e-6, `y within 1e-6, got ${sol.p.y}`);
  // Zero residuals mean no chi-square inflation, but the formal covariance
  // still reflects the 4-deg measurement sigma: CEP = 0.59*(s1+s2), well
  // under 100 m for 10 well-crossed LOBs at ~1400 m range.
  assert.equal(sol.cep, Math.max(FIX.CEP_FLOOR_M, 0.59 * (sol.s1 + sol.s2)));
  assert.ok(sol.cep < 100, `clean 10-LOB cut should be tight, got ${sol.cep}`);
  assert.ok(Math.abs(sol.cutDeg - 90) < 1e-6, `cut angle ~90, got ${sol.cutDeg}`);
  assert.equal(sol.balance, 1, "5/5 split is perfectly balanced");
  // Cut angle beyond GOOD_CUT_DEG clamps the angle factor at 1: no penalty.
  assert.equal(sol.geomCep, sol.cep);
});

test("high-precision bearings drive the CEP down to the sensor-limited floor", () => {
  const tight = 0.5 * (Math.PI / 180); // 0.5-deg sigma
  const mk = (sx: number, sy: number, n: number): Measurement[] =>
    Array.from({ length: n }, (_, i) => ({ sx, sy, brg: brg(sx, sy, 1000, 1000), sig: tight, t: i }));
  const sol = computeEstimate([...mk(0, 0, 20), ...mk(2000, 0, 20)], START, FIX);
  assert.ok(sol);
  assert.equal(sol.cep, FIX.CEP_FLOOR_M, "CEP must not report below the floor");
});

test("parallel LOBs (single look angle) cannot produce a cut", () => {
  const M = [...lobs(0, 0, 0, 3000, 5), ...lobs(500, 0, 500, 3000, 5)];
  // Both sensors stare due north: normal matrix is singular.
  assert.equal(computeEstimate(M, START, FIX), null);
});

test("lopsided collection is penalized through balance", () => {
  const M = [...lobs(0, 0, 1000, 1000, 12), ...lobs(2000, 0, 1000, 1000, 3)];
  const sol = computeEstimate(M, START, FIX);
  assert.ok(sol);
  // Weaker collector holds 3 of 15 LOBs: balance = (3/15)/0.5 = 0.4.
  assert.ok(Math.abs(sol.balance - 0.4) < 1e-12, `balance 0.4, got ${sol.balance}`);
  // The geometry-penalized CEP must inflate accordingly (cep / balance here,
  // since the 90-degree cut leaves no angle penalty).
  assert.ok(Math.abs(sol.geomCep - sol.cep / 0.4) < 1e-9);
  assert.ok(sol.geomCep > sol.cep);
});

test("noisy bearings: residual inflation keeps the reported CEP honest", () => {
  const gauss = makeGauss(mulberry32(7)); // deterministic noise
  const M = [
    ...lobs(0, 0, 1000, 1000, 20, gauss),
    ...lobs(2000, 0, 1000, 1000, 20, gauss),
  ];
  const sol = computeEstimate(M, START, FIX);
  assert.ok(sol);
  const err = Math.hypot(sol.p.x - 1000, sol.p.y - 1000);
  // 40 well-crossed LOBs at 4-deg sigma from ~1400 m: the solution lands
  // near the target and the reported uncertainty covers the actual error.
  assert.ok(err < 200, `estimate error ${err}m should be small`);
  assert.ok(Math.max(sol.cep, sol.geomCep) >= err / 3, "reported CEP must not be wildly optimistic");
});

/* ------------------------- updateFix gating ------------------------- */

function mkTeam(meas: Measurement[]): Team {
  return {
    side: "BLUFOR", enemy: "OPFOR",
    emcon: DEFAULT_CONFIG.TEAMS.BLUFOR, emconLabel: "INTERMITTENT",
    launchT: 20, ulPhase: 0, viPhase: 0,
    gcs: { id: "BLUFOR-GCS", x: 0, y: 0, destroyed: false, transmitting: false },
    nodes: [],
    drone: null as unknown as Team["drone"], // not touched by updateFix
    meas,
    est: { p: null, cep: Infinity, s1: 0, s2: 0, ang: 0, solved: false },
    estHist: [],
    flags: { firstLOB: false, crossFix: false, fixed: false, committed: false,
             acquired: false, dlFirst: false, lowBatt: false, onStation: false },
    flagTimes: {},
    droneTrack: null,
    searchBox: { x: 500, y: 500, w: 1000, h: 1000 }, nai: "NAI 2", holdPt: { x: 0, y: 0 },
  };
}

function mkCtx(events: { side: string; text: string }[]): SimCtx {
  return {
    config: DEFAULT_CONFIG, t: 42,
    addEvent: (side: string, text: string) => events.push({ side, text }),
  } as unknown as SimCtx; // world/teams/rng are not touched by updateFix
}

test("no solve below MIN_LOBS_SOLVE", () => {
  const T = mkTeam([...lobs(0, 0, 1000, 1000, 3), ...lobs(2000, 0, 1000, 1000, 2)]);
  updateFix(mkCtx([]), T);
  assert.equal(T.est.solved, false);
});

test("no solve when the second collector is below MIN_LOBS_2ND", () => {
  // 9 LOBs total but only 2 from the second sensor: near-single-sensor
  // geometry, the along-range position would slide freely.
  const T = mkTeam([...lobs(0, 0, 1000, 1000, 7), ...lobs(2000, 0, 1000, 1000, 2)]);
  updateFix(mkCtx([]), T);
  assert.equal(T.est.solved, false);
});

test("balanced multi-sensor evidence solves, and the jitter gate delays FIX", () => {
  const events: { side: string; text: string }[] = [];
  const ctx = mkCtx(events);
  const T = mkTeam([...lobs(0, 0, 1000, 1000, 6), ...lobs(2000, 0, 1000, 1000, 4)]);

  updateFix(ctx, T);
  assert.equal(T.est.solved, true);
  assert.ok(events.some((e) => e.text.startsWith("CROSS-FIX FORMING")), "cross-fix announced on first solve");
  // Fewer than 4 solutions in the history: jitter is 9999, so the effective
  // CEP cannot pass the FIX gate yet no matter how good the geometry is.
  assert.equal(T.flags.fixed, false);
  assert.equal(T.est.cep, 9999);

  updateFix(ctx, T);
  updateFix(ctx, T);
  assert.equal(T.flags.fixed, false, "still inside the jitter window");
  updateFix(ctx, T); // 4th identical solution: jitter -> 0
  assert.equal(T.flags.fixed, true, "stable estimate with 10 LOBs and small CEP declares FIX");
  assert.ok(events.some((e) => e.text.startsWith("FIX ESTABLISHED")));
  assert.ok(T.est.cep < DEFAULT_CONFIG.FIX.FIX_CEP_M);
});
