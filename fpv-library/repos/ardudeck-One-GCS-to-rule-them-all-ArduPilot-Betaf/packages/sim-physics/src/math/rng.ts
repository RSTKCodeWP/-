/**
 * Deterministic, seedable PRNG (mulberry32) plus a Gaussian helper. Used for
 * reproducible sensor noise and turbulence - never `Math.random`, so a sim run
 * is repeatable given the same seed.
 */

export interface Rng {
  /** Uniform in [0, 1). */
  next(): number;
  /** Standard normal (mean 0, stddev 1). */
  gaussian(): number;
}

export function makeRng(seed: number): Rng {
  let a = seed >>> 0;
  const next = (): number => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return {
    next,
    gaussian(): number {
      // Box-Muller. Guard u1 away from 0 to avoid log(0).
      const u1 = Math.max(1e-12, next());
      const u2 = next();
      return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    },
  };
}
