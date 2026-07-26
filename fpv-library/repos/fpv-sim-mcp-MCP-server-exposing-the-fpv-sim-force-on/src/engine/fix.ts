/*
 * Weighted least-squares intersection of accumulated LOBs, ported verbatim
 * from fpv-sim index.html.
 *
 * Measurement model: perpendicular offset from each bearing line,
 * noise sigma_perp = sig * range. Covariance = inverse normal matrix.
 *
 * The pure solve (computeEstimate) is separated from the stateful gating
 * wrapper (updateFix) so the math can be unit-tested against synthetic LOB
 * sets with known intersections. The computation order inside each is
 * unchanged from the original.
 */

import { clamp, d2r, r2d, dist, normAng, gridRef } from "./math.js";
import type { FixConfig } from "./config.js";
import type { Measurement, Team, Vec2 } from "./types.js";
import type { SimCtx } from "./context.js";

export interface FixSolution {
  p: Vec2;
  s1: number;        // error-ellipse semi-axis sigmas (major, minor)
  s2: number;
  ang: number;       // major-axis orientation, math frame
  cep: number;       // formal CEP (floored at CEP_FLOOR_M)
  geomCep: number;   // CEP inflated by crossing-angle / balance geometry
  cutDeg: number;    // crossing angle between the two strongest collectors
  balance: number;   // LOB share of the weaker collector, 1.0 = 50/50 split
}

/*
 * Two-iteration iteratively-reweighted solve: the weights depend on range to
 * the answer, so solve, re-range, solve again. Returns null while the LOB
 * geometry is still near-parallel (singular normal matrix).
 */
export function computeEstimate(M: Measurement[], start: Vec2, FIX: FixConfig): FixSolution | null {
  let p0 = start;
  for (let iter = 0; iter < 2; iter++) {
    let A11 = 0, A12 = 0, A22 = 0, b1 = 0, b2 = 0;
    for (const m of M) {
      const r = Math.max(300, dist(m.sx, m.sy, p0.x, p0.y));
      const w = 1 / Math.pow(m.sig * r, 2);
      const nx = Math.cos(m.brg), ny = -Math.sin(m.brg); // perpendicular to LOB
      const c = nx * m.sx + ny * m.sy;
      A11 += w * nx * nx; A12 += w * nx * ny; A22 += w * ny * ny;
      b1 += w * nx * c; b2 += w * ny * c;
    }
    const det = A11 * A22 - A12 * A12;
    if (Math.abs(det) < 1e-12) return null; // near-parallel geometry, no cut yet
    const px = (A22 * b1 - A12 * b2) / det;
    const py = (A11 * b2 - A12 * b1) / det;
    p0 = { x: px, y: py };
    if (iter === 1) {
      // Residual-based covariance inflation keeps the ellipse honest when
      // the small-sample geometry makes the formal covariance optimistic.
      let chi2 = 0;
      for (const m of M) {
        const r = Math.max(300, dist(m.sx, m.sy, p0.x, p0.y));
        const w = 1 / Math.pow(m.sig * r, 2);
        const nx = Math.cos(m.brg), ny = -Math.sin(m.brg);
        const res = nx * p0.x + ny * p0.y - (nx * m.sx + ny * m.sy);
        chi2 += w * res * res;
      }
      const scale = Math.max(1, chi2 / Math.max(1, M.length - 2));
      // Covariance = scale * A^-1; eigen-decompose for the error ellipse.
      const C11 = scale * A22 / det, C12 = scale * -A12 / det, C22 = scale * A11 / det;
      const tr = C11 + C22, dd = C11 * C22 - C12 * C12;
      const disc = Math.sqrt(Math.max(0, tr * tr / 4 - dd));
      const l1 = tr / 2 + disc, l2 = Math.max(1, tr / 2 - disc);
      const s1 = Math.sqrt(l1), s2 = Math.sqrt(l2);
      const ang = Math.atan2(l1 - C11, C12 || 1e-9); // eigvec of l1, math-frame
      const cep = Math.max(FIX.CEP_FLOOR_M, 0.59 * (s1 + s2));
      // Geometric quality from genuine multi-sensor crossing. Group LOBs by
      // sensor; take the two strongest collectors, compute the crossing angle
      // between their mean bearings, and weight by how balanced the evidence
      // is. A fix leaning on one sensor (few crossing LOBs from the other)
      // has weak along-range constraint and must report a large CEP.
      const byS: Record<string, { n: number; sx: number; sy: number }> = {};
      for (const m of M) {
        const key = Math.round(m.sx) + "_" + Math.round(m.sy);
        (byS[key] = byS[key] || { n: 0, sx: m.sx, sy: m.sy }).n++;
      }
      const grp = Object.values(byS).sort((a, b) => b.n - a.n);
      const s0 = grp[0], sB = grp[1] || grp[0];
      const b0 = Math.atan2(p0.x - s0.sx, p0.y - s0.sy);
      const bB = Math.atan2(p0.x - sB.sx, p0.y - sB.sy);
      const cross = Math.abs(normAng(b0 - bB));
      const angFactor = clamp(Math.sin(cross) / Math.sin(d2r(FIX.GOOD_CUT_DEG)), 0.05, 1);
      // Balance: share of LOBs held by the weaker of the two collectors,
      // normalized so a 50/50 split scores 1.0 and a lopsided split scores low.
      const balance = clamp((sB.n / (s0.n + sB.n)) / 0.5, 0.12, 1);
      const geomCep = cep / (angFactor * balance);
      return { p: p0, s1, s2, ang, cep, geomCep, cutDeg: r2d(cross), balance };
    }
  }
  /* unreachable: iter === 1 always returns or bails on a singular matrix */
  return null;
}

export function updateFix(sim: SimCtx, T: Team): void {
  const FIX = sim.config.FIX;
  const M = T.meas;
  if (M.length < FIX.MIN_LOBS_SOLVE) return;
  // Require genuine multi-sensor geometry. A cut dominated by one collector
  // (many looks from one node, a single crossing LOB from another) is close
  // to a single-sensor solution: the along-range position slides freely.
  // Count LOBs per sensor and require the SECOND-strongest to carry weight.
  const perSensor: Record<string, number> = {};
  for (const m of M) {
    const key = Math.round(m.sx) + "_" + Math.round(m.sy);
    perSensor[key] = (perSensor[key] || 0) + 1;
  }
  const counts = Object.values(perSensor).sort((a, b) => b - a);
  if (counts.length < 2 || counts[1] < FIX.MIN_LOBS_2ND) return;

  const start = T.est.p || { x: T.searchBox.x + T.searchBox.w / 2, y: T.searchBox.y + T.searchBox.h / 2 };
  const sol = computeEstimate(M, start, FIX);
  if (!sol) return;

  T.estHist.push({ x: sol.p.x, y: sol.p.y, t: sim.t });
  while (T.estHist.length > 6) T.estHist.shift();
  // Jitter penalty: if the last few solutions are still wandering, the
  // effective CEP cannot be small yet regardless of the formal covariance.
  let jitter = 0;
  if (T.estHist.length >= 4) {
    const n = T.estHist.length, mx = T.estHist.reduce((s, e) => s + e.x, 0) / n,
          my = T.estHist.reduce((s, e) => s + e.y, 0) / n;
    jitter = Math.sqrt(T.estHist.reduce((s, e) => s + (e.x - mx) ** 2 + (e.y - my) ** 2, 0) / n);
  } else {
    jitter = 9999;
  }
  const effCep = Math.max(sol.cep, sol.geomCep, jitter);
  T.est = {
    p: sol.p, s1: sol.s1, s2: sol.s2, ang: sol.ang, cep: effCep, formalCep: sol.cep,
    geomCep: sol.geomCep, jitter, cutDeg: sol.cutDeg, balance: sol.balance, solved: true,
  };

  if (!T.flags.crossFix && T.est.solved) {
    T.flags.crossFix = true;
    T.flagTimes.crossFix = sim.t;
    sim.addEvent(T.side, "CROSS-FIX FORMING ON HOSTILE C2 EMITTER // " + M.length + " LOBS HELD");
  }
  if (!T.flags.fixed && M.length >= FIX.MIN_LOBS_FIX && T.est.cep < FIX.FIX_CEP_M) {
    T.flags.fixed = true;
    T.flagTimes.fixed = sim.t;
    sim.addEvent(T.side, "FIX ESTABLISHED HOSTILE GCS " + gridRef(T.est.p!.x, T.est.p!.y) +
      " // CEP " + Math.round(T.est.cep) + "M // " + M.length + " LOBS");
  }
}
