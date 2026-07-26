/*
 * Seeded value-noise terrain: jungle interior, ridgelines, eastern coastline,
 * canopy field with clearings and one east-west trail.
 *
 * Ported verbatim from fpv-sim index.html, minus the offscreen-canvas
 * rendering pass (which drew from its own independent RNG stream, seed+909,
 * so severing it cannot affect simulation determinism).
 *
 * All terrain randomness comes from streams derived from the seed
 * (seed+101/202/303/404), never from the main engagement stream — so the
 * world build consumes zero draws from the Simulation's rng.
 */

import { mulberry32 } from "./rng.js";
import { clamp, lerp, smooth01, dist, distToSeg } from "./math.js";
import type { Vec2 } from "./types.js";

export interface Clearing { x: number; y: number; r: number; }

export interface World {
  size: number;
  res: number;               // sample grid resolution
  elevG: Float32Array;
  canG: Float32Array;
  trail: Vec2[];
  clearings: Clearing[];
  seed: number;
}

export function makeNoise(seed: number): (x: number, y: number) => number {
  const r = mulberry32(seed);
  const G = 64, vals = new Float32Array(G * G);
  for (let i = 0; i < G * G; i++) vals[i] = r();
  return function (x: number, y: number) {
    x = ((x % G) + G) % G; y = ((y % G) + G) % G;
    const x0 = Math.floor(x), y0 = Math.floor(y);
    const x1 = (x0 + 1) % G, y1 = (y0 + 1) % G;
    const fx = smooth01(x - x0), fy = smooth01(y - y0);
    const v00 = vals[y0 * G + x0], v10 = vals[y0 * G + x1];
    const v01 = vals[y1 * G + x0], v11 = vals[y1 * G + x1];
    return lerp(lerp(v00, v10, fx), lerp(v01, v11, fx), fy);
  };
}

function sampleGrid(world: World, grid: Float32Array, x: number, y: number): number {
  const W = world.size, R = world.res;
  const gx = clamp(x / W * (R - 1), 0, R - 1.0001);
  const gy = clamp(y / W * (R - 1), 0, R - 1.0001);
  const x0 = Math.floor(gx), y0 = Math.floor(gy);
  const fx = gx - x0, fy = gy - y0;
  const i = y0 * R + x0;
  return lerp(
    lerp(grid[i], grid[i + 1], fx),
    lerp(grid[i + R], grid[i + R + 1], fx), fy);
}

export const elevAt = (world: World, x: number, y: number): number => sampleGrid(world, world.elevG, x, y);
export const canopyAt = (world: World, x: number, y: number): number => sampleGrid(world, world.canG, x, y);

export function buildWorld(seed: number, sizeM: number): World {
  const world: World = {
    size: sizeM,
    res: 200,
    elevG: new Float32Array(0),
    canG: new Float32Array(0),
    trail: [],
    clearings: [],
    seed,
  };
  const n1 = makeNoise(seed + 101);
  const n2 = makeNoise(seed + 202);
  const n3 = makeNoise(seed + 303);
  const wr = mulberry32(seed + 404);
  const W = world.size, R = world.res;
  world.elevG = new Float32Array(R * R);
  world.canG = new Float32Array(R * R);

  // Clearings: seeded LZ-sized gaps in the canopy.
  world.clearings = [];
  for (let i = 0; i < 6; i++) {
    world.clearings.push({
      x: 500 + wr() * 2600, y: 500 + wr() * 3000, r: 90 + wr() * 130,
    });
  }
  // Trail: winding east-west track through the interior.
  world.trail = [];
  let ty = 1500 + wr() * 900;
  for (let tx = 0; tx <= 3400; tx += 340) {
    ty += (wr() - 0.5) * 420;
    ty = clamp(ty, 800, 3100);
    world.trail.push({ x: tx, y: ty });
  }

  for (let gy = 0; gy < R; gy++) {
    for (let gx = 0; gx < R; gx++) {
      const x = gx / (R - 1) * W, y = gy / (R - 1) * W;
      const u = x / W, v = y / W;
      // Elevation: fBm shaped into low jungle hills and a spine ridge.
      const base = 0.52 * n1(u * 3.2, v * 3.2)
                 + 0.30 * n1(u * 6.4 + 7, v * 6.4 + 3)
                 + 0.18 * n1(u * 13 + 13, v * 13 + 9);
      let e = Math.pow(base, 1.35) * 265 - 18;
      // Eastern coastline with a shallow bay in the northeast.
      const coast = smooth01((x - 3180) / 640);
      const bay = smooth01((x - 2750) / 700) * smooth01((y - 2900) / 500);
      e -= coast * 330 + bay * 200;
      e = Math.max(e, -45);
      world.elevG[gy * R + gx] = e;

      // Canopy density 0..1.
      let c = (0.6 * n2(u * 5, v * 5) + 0.4 * n2(u * 11 + 5, v * 11 + 2)) * 1.55 - 0.28;
      c += 0.15 * n3(u * 23, v * 23) - 0.07;
      c = clamp(c, 0, 1);
      if (e < 3) c = 0;                       // beach / water
      if (e > 195) c *= clamp(1 - (e - 195) / 60, 0.25, 1); // thin on crests
      for (const cl of world.clearings) {
        const d = dist(x, y, cl.x, cl.y);
        if (d < cl.r * 1.5) c *= smooth01((d - cl.r * 0.55) / (cl.r * 0.9));
      }
      for (let i = 0; i < world.trail.length - 1; i++) {
        const a = world.trail[i], b = world.trail[i + 1];
        const d = distToSeg(x, y, a.x, a.y, b.x, b.y);
        if (d < 20) { c *= 0.12; break; }
        else if (d < 45) c *= 0.55;
      }
      world.canG[gy * R + gx] = c;
    }
  }
  return world;
}
