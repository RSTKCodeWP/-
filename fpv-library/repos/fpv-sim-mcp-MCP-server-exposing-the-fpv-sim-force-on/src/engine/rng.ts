/*
 * Deterministic RNG, ported verbatim from fpv-sim index.html.
 *
 * The entire engagement — emplacement jitter, EMCON phase offsets, detection
 * rolls, bearing noise — draws from ONE mulberry32 stream. The order of
 * draws is therefore part of the simulation's contract: any reordering of
 * rng() call sites changes every subsequent outcome. Do not "clean up" call
 * order in the consumers of this module.
 */

export type Rng = () => number;

export function mulberry32(a: number): Rng {
  return function () {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

/*
 * Box–Muller gaussian. The zero-rejection loops consume a VARIABLE number of
 * draws from the underlying stream; this is part of the deterministic
 * contract and must not be replaced with a fixed-draw implementation.
 */
export function makeGauss(rng: Rng): Rng {
  return function () {
    let u = 0, v = 0;
    while (u === 0) u = rng();
    while (v === 0) v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  };
}
