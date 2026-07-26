/*
 * Drone finite-state machine, ported verbatim from fpv-sim index.html.
 *
 *   STANDBY → TRANSIT → HOLD → COMMIT → TERMINAL → IMPACT
 *                 ↓ (own GCS destroyed)      ↓ (fix error / battery)
 *             LINK LOST → DOWN         expanding search / DOWN
 *
 * The only changes from the browser version are the removal of the visual
 * breadcrumb trail and explosion markers; neither touches the RNG or any
 * state the simulation reads back.
 */

import { clamp, d2r, dist, brgTo, normAng, gridRef, fmtT } from "./math.js";
import type { Drone, Team } from "./types.js";
import type { SimCtx } from "./context.js";

function steerToward(d: Drone, tx: number, ty: number, dt: number, turnDps: number): void {
  const want = brgTo(d.x, d.y, tx, ty);
  const diff = normAng(want - d.hdg);
  const maxTurn = d2r(turnDps) * dt;
  d.hdg = normAng(d.hdg + clamp(diff, -maxTurn, maxTurn));
}

function moveDrone(sim: SimCtx, d: Drone, dt: number): void {
  d.x += Math.sin(d.hdg) * d.spd * dt;
  d.y += Math.cos(d.hdg) * d.spd * dt;
  d.x = clamp(d.x, 30, sim.world.size - 30);
  d.y = clamp(d.y, 30, sim.world.size - 30);
}

export function stepDrone(sim: SimCtx, T: Team, dt: number): void {
  const d = T.drone, E = sim.teams[T.enemy], D = sim.config.DRONE;

  if (!d.launched) {
    if (sim.t >= T.launchT && !T.gcs.destroyed) {
      d.launched = true; d.state = "TRANSIT"; d.agl = 2;
      d.hdg = brgTo(d.x, d.y, d.wps[0].x, d.wps[0].y);
      sim.addEvent(T.side, "sUAS-1 LAUNCH " + gridRef(d.x, d.y) + " // KINETIC PAYLOAD // HOLDING FWD OF FLOT PENDING FIX");
    }
    return;
  }
  if (d.downed || d.state === "IMPACT") return;

  // Battery. Drain scales with flight regime: holding at loiter speed is
  // far cheaper than transit, dash, or terminal.
  const drainMult = (d.state === "HOLD") ? D.LOITER_DRAIN : 1.0;
  d.airT += dt * drainMult;
  d.batt = clamp(100 * (1 - d.airT / D.ENDURANCE_S), 0, 100);
  if (d.batt < 30 && !T.flags.lowBatt) {
    T.flags.lowBatt = true;
    T.flagTimes.lowBatt = sim.t;
    sim.addEvent(T.side, "sUAS-1 BATTERY 30 PCT // ENDURANCE LIMITED");
  }
  if (d.batt <= 0) {
    d.downed = true; d.state = "DOWN";
    sim.addEvent(T.side, "sUAS-1 DOWN // BATTERY EXHAUSTED " + gridRef(d.x, d.y));
    return;
  }

  // Own GCS destroyed: C2 severed.
  if (T.gcs.destroyed && !d.linkLost) {
    d.linkLost = true; d.linkLostT = sim.t; d.state = "LINK LOST";
    sim.addEvent(T.side, "sUAS-1 C2 LINK LOST // NO OPERATOR IN THE LOOP");
  }
  if (d.linkLost) {
    d.spd = Math.max(0, d.spd - 2 * dt);
    d.agl = Math.max(0, d.agl - 4 * dt);
    if (sim.t - d.linkLostT > 8 && d.state !== "DOWN") {
      d.downed = true; d.state = "DOWN";
      sim.addEvent(T.side, "sUAS-1 DOWN " + gridRef(d.x, d.y));
    }
    moveDrone(sim, d, dt);
    return;
  }

  // Attack commit: own fix quality inside threshold.
  if (!T.flags.committed && T.est.solved && T.flags.fixed &&
      T.meas.length >= sim.config.FIX.MIN_LOBS_COMMIT &&
      T.est.cep < sim.config.FIX.COMMIT_CEP_M &&
      (d.state === "TRANSIT" || d.state === "HOLD")) {
    T.flags.committed = true; T.flagTimes.committed = sim.t; d.state = "COMMIT";
    sim.addEvent(T.side, "ATTACK COMMIT // sUAS-1 EGRESS HOLD // TASKED HOSTILE GCS " +
      gridRef(T.est.p!.x, T.est.p!.y) + " // CEP " + Math.round(T.est.cep) + "M");
  }
  // Final-push commit: low battery forces the decision. Accept a looser fix
  // (terminal visual acquisition will refine the last few hundred meters)
  // rather than expend the drone holding on station.
  else if (!T.flags.committed && T.est.solved && T.est.cep < sim.config.FIX.PUSH_CEP_M &&
      d.batt <= D.PUSH_BATT_PCT &&
      (d.state === "TRANSIT" || d.state === "HOLD")) {
    T.flags.committed = true; T.flagTimes.committed = sim.t; d.state = "COMMIT";
    sim.addEvent(T.side, "FINAL PUSH // BINGO FUEL // sUAS-1 COMMITTING ON BEST FIX " +
      gridRef(T.est.p!.x, T.est.p!.y) + " // CEP " + Math.round(T.est.cep) + "M");
  }

  let targetX = 0, targetY = 0, wantSpd = D.CRUISE_MPS, wantAgl = D.ALT_TRANSIT_AGL;

  if (d.state === "TRANSIT") {
    const hp = T.holdPt;
    targetX = hp.x; targetY = hp.y;
    if (dist(d.x, d.y, hp.x, hp.y) < D.WPT_RADIUS_M && !T.flags.onStation) {
      T.flags.onStation = true; T.flagTimes.onStation = sim.t; d.state = "HOLD";
      sim.addEvent(T.side, "sUAS-1 ESTABLISHED HOLD " + gridRef(hp.x, hp.y) +
        " // AWAITING FIX ON HOSTILE GCS");
    }
  } else if (d.state === "HOLD") {
    // Endurance-optimal orbit around the holding point while ground cUAS
    // builds the fix. Slow and low-ish to conserve battery.
    d.orbitA += dt * (D.LOITER_MPS / D.HOLD_RADIUS_M);
    targetX = T.holdPt.x + Math.sin(d.orbitA) * D.HOLD_RADIUS_M;
    targetY = T.holdPt.y + Math.cos(d.orbitA) * D.HOLD_RADIUS_M;
    wantSpd = D.LOITER_MPS; wantAgl = D.ALT_LOITER_AGL;
  } else if (d.state === "COMMIT") {
    targetX = T.est.p!.x; targetY = T.est.p!.y;
    wantSpd = D.DASH_MPS;
    if (dist(d.x, d.y, targetX, targetY) < 380) {
      d.state = "TERMINAL";
      sim.addEvent(T.side, "sUAS-1 TERMINAL PHASE // DESCENDING BELOW CANOPY FOR VISUAL ID");
    }
  } else if (d.state === "TERMINAL") {
    wantSpd = D.TERMINAL_MPS; wantAgl = D.ALT_TERMINAL_AGL;
    const gr = dist(d.x, d.y, E.gcs.x, E.gcs.y);
    if (!T.flags.acquired && gr < D.ACQ_RANGE_M) {
      T.flags.acquired = true;
      T.flagTimes.acquired = sim.t;
      sim.addEvent(T.side, "sUAS-1 VISUAL ACQ HOSTILE GCS // COMMENCING ATTACK RUN");
    }
    if (T.flags.acquired) {
      targetX = E.gcs.x; targetY = E.gcs.y;
      if (gr < D.IMPACT_RANGE_M) {
        d.state = "IMPACT"; d.spd = 0;
        E.gcs.destroyed = true;
        sim.winner = T.side; sim.endT = sim.t;
        sim.addEvent(T.side, "IMPACT // HOSTILE GCS DESTROYED " + gridRef(E.gcs.x, E.gcs.y));
        sim.addEvent("SYS", "ENDEX // " + T.side + " VICTORY " + fmtT(sim.t));
        return;
      }
    } else {
      // Drive to the fix center first. Only once the drone has reached the
      // estimated point without acquiring (a fix error larger than sensor
      // range) does the operator fly an expanding-square visual search
      // outward. A modest error is recovered quickly; a gross error (a
      // geometrically weak fix that slipped the commit gate) burns battery.
      const d2fix = dist(d.x, d.y, T.est.p!.x, T.est.p!.y);
      if (d2fix > D.WPT_RADIUS_M && !d.fixReached) {
        targetX = T.est.p!.x; targetY = T.est.p!.y;   // still inbound to the fix
      } else {
        d.fixReached = true;
        d.searchR = (d.searchR || 0) + dt * D.TERMINAL_SEARCH_GROW;
        d.orbitA += dt * (D.TERMINAL_MPS / Math.max(40, d.searchR));
        targetX = T.est.p!.x + Math.sin(d.orbitA) * d.searchR;
        targetY = T.est.p!.y + Math.cos(d.orbitA) * d.searchR;
      }
      wantSpd = D.TERMINAL_MPS; wantAgl = D.ALT_TERMINAL_AGL;
    }
  }

  steerToward(d, targetX, targetY, dt, D.TURN_DPS);
  d.spd = d.spd + clamp(wantSpd - d.spd, -6 * dt, 6 * dt);
  d.agl = d.agl + clamp(wantAgl - d.agl, -D.CLIMB_MPS * dt, D.CLIMB_MPS * dt);
  moveDrone(sim, d, dt);
}
