/*
 * EMCON duty-cycle logic, ported verbatim from fpv-sim index.html.
 *
 * This is the heart of the demo's asymmetry: a team only exposes itself to
 * DF collection while an emitter is keyed. Each team's duty cycle is offset
 * by a per-seed random phase (ulPhase / viPhase) so the two sides' windows
 * don't align artificially.
 */

import type { Team } from "./types.js";

export function uplinkActive(team: Team, t: number): boolean {
  const d = team.drone;
  if (!d.launched || d.downed || d.state === "IMPACT" || team.gcs.destroyed) return false;
  const p = team.emcon;
  const per = p.uplinkOn + p.uplinkOff;
  return ((t + team.ulPhase) % per) < p.uplinkOn;
}

export function videoActive(team: Team, t: number): boolean {
  const d = team.drone;
  if (!d.launched || d.downed || d.linkLost || d.state === "IMPACT") return false;
  if (team.emcon.videoOff === 0) return true;                      // continuous
  if (d.state === "COMMIT" || d.state === "TERMINAL") return true; // needs eyes on
  const per = team.emcon.videoOn + team.emcon.videoOff;
  return ((t + team.viPhase) % per) < team.emcon.videoOn;
}
