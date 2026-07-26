/*
 * RF propagation, ported verbatim from fpv-sim index.html.
 *
 * Path attenuation factor between two points with antenna/flight heights
 * (AGL). Terrain blocking is heavy but not absolute (diffraction); canopy
 * along the path is a soft loss. Returns 0 (clean LOS) .. ~6 (severely
 * masked).
 */

import { lerp } from "./math.js";
import { elevAt, canopyAt, type World } from "./terrain.js";

export function pathAtten(
  world: World,
  canopyHgtM: number,
  ax: number, ay: number, aAgl: number,
  bx: number, by: number, bAgl: number,
): number {
  const aZ = Math.max(elevAt(world, ax, ay), 0) + aAgl;
  const bZ = Math.max(elevAt(world, bx, by), 0) + bAgl;
  const K = 14;
  let block = 0, veg = 0;
  for (let i = 1; i < K; i++) {
    const t = i / K;
    const x = lerp(ax, bx, t), y = lerp(ay, by, t);
    const g = elevAt(world, x, y);
    const losZ = lerp(aZ, bZ, t);
    if (g > losZ + 2) block += 1;
    else if (losZ < g + canopyHgtM) veg += canopyAt(world, x, y);
  }
  return Math.min(6, (block / K) * 4.2 + veg * 0.14);
}
