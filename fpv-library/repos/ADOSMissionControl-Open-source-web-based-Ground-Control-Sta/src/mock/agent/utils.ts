/**
 * @module mock/agent/utils
 * @description Shared helpers + the per-process boot timestamp used by
 * every domain mock. Centralised so swapping the jitter strategy or
 * the boot epoch only touches one file.
 * @license GPL-3.0-only
 */

export const startTime = Date.now();

export const jitter = (base: number, range: number): number =>
  base + (Math.random() - 0.5) * 2 * range;

export function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
