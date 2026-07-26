/*
 * DF collection, ported verbatim from fpv-sim index.html.
 *
 * Every scan interval, each side's nodes roll detection against every active
 * enemy emitter in range:
 *  - C2 uplink intercepts produce LOBs that terminate at the enemy GCS and
 *    feed the geolocation fix.
 *  - FPV video downlink intercepts produce a (noisy) track on the enemy air
 *    vehicle — situational awareness only, they do not feed the GCS fix.
 *
 * RNG discipline: the scan order (BLUFOR's collection first, then OPFOR's;
 * uplink before downlink; node 1 before node 2) fixes the order of rng()
 * and gauss() draws and must not change.
 */

import { clamp, d2r, r2d, dist, brgTo } from "./math.js";
import { pathAtten } from "./rf.js";
import { uplinkActive, videoActive } from "./emissions.js";
import { updateFix } from "./fix.js";
import type { SimCtx } from "./context.js";

export function doScans(sim: SimCtx): void {
  const CUAS = sim.config.CUAS;
  for (const side of ["BLUFOR", "OPFOR"] as const) {
    const T = sim.teams[side];
    const E = sim.teams[T.enemy];
    if (T.gcs.destroyed) continue;
    // C2 uplink intercepts: LOBs terminate at the enemy GCS.
    if (uplinkActive(E, sim.t)) {
      for (const nd of T.nodes) {
        const r = dist(nd.x, nd.y, E.gcs.x, E.gcs.y);
        if (r > CUAS.MAX_RANGE_M) continue;
        const att = pathAtten(sim.world, CUAS.CANOPY_HGT_M, nd.x, nd.y, 4, E.gcs.x, E.gcs.y, 2.5);
        const p = CUAS.P_DETECT_UL * clamp(1.15 - r / CUAS.MAX_RANGE_M, 0, 1) * Math.exp(-att);
        if (sim.rng() < p) {
          const sig = d2r(CUAS.BRG_SIGMA_DEG) * (1 + 0.5 * att);
          const brg = brgTo(nd.x, nd.y, E.gcs.x, E.gcs.y) + sim.gauss() * sig;
          T.meas.push({ sx: nd.x, sy: nd.y, brg, sig, t: sim.t });
          if (T.meas.length > CUAS.MAX_MEAS) T.meas.shift();
          nd.det++; nd.lastBrg = brg; nd.lastT = sim.t;
          if (!T.flags.firstLOB) {
            T.flags.firstLOB = true;
            T.flagTimes.firstLOB = sim.t;
            sim.addEvent(side, nd.id.replace(side + "-", "") + " INITIAL LOB " +
              String(Math.round((r2d(brg) + 360) % 360)).padStart(3, "0") +
              "T // C2 UPLINK 915 MHZ // HOSTILE GCS EMITTING");
          }
        }
      }
      updateFix(sim, T);
    }
    // FPV video downlink intercepts: track on the enemy air vehicle.
    if (videoActive(E, sim.t)) {
      const d = E.drone;
      for (const nd of T.nodes) {
        const r = dist(nd.x, nd.y, d.x, d.y);
        if (r > CUAS.MAX_RANGE_M) continue;
        const att = pathAtten(sim.world, CUAS.CANOPY_HGT_M, nd.x, nd.y, 4, d.x, d.y, Math.max(d.agl, 5));
        const p = CUAS.P_DETECT_DL * clamp(1.2 - r / CUAS.MAX_RANGE_M, 0, 1) * Math.exp(-att);
        if (sim.rng() < p) {
          nd.dl++;
          T.droneTrack = { x: d.x + sim.gauss() * 55, y: d.y + sim.gauss() * 55, t: sim.t };
          if (!T.flags.dlFirst) {
            T.flags.dlFirst = true;
            T.flagTimes.dlFirst = sim.t;
            sim.addEvent(side, "FPV VIDEO DOWNLINK DETECTED 5.8 GHZ // HOSTILE sUAS AIRBORNE");
          }
        }
      }
    }
  }
}
