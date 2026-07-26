/**
 * Virtual parameter registry for MSP protocol.
 *
 * Maps MSP binary config data to named "virtual parameters" so the existing
 * `usePanelParams` hook works unchanged for Betaflight/iNav panels.
 *
 * Each virtual param knows:
 * - Which MSP command to read/write
 * - How to extract its value from the read response payload
 * - How to patch its value into a write payload (for sending back)
 *
 * Pure data + pure functions. No side effects.
 *
 * This module is a facade over the virtual-params/ folder: individual
 * entries are defined per subsystem (tuning, system, peripherals) and
 * concatenated into one Map here.
 *
 * @module protocol/msp/virtual-params
 */

import type { VirtualParamDef } from "./virtual-params/types";
import { entries as tuningEntries } from "./virtual-params/entries-tuning";
import { entries as systemEntries } from "./virtual-params/entries-system";
import { entries as peripheralsEntries } from "./virtual-params/entries-peripherals";

// Re-export types + factory helpers so existing imports resolve unchanged.
export type { VirtualParamDef } from "./virtual-params/types";

// ── Build the Map ────────────────────────────────────────────

const combinedEntries: Array<[string, VirtualParamDef]> = [
  ...tuningEntries,
  ...systemEntries,
  ...peripheralsEntries,
];

export const VIRTUAL_PARAMS: ReadonlyMap<string, VirtualParamDef> = new Map(combinedEntries);

// ── Query helpers ────────────────────────────────────────────

/**
 * Group virtual params by their MSP read command so a panel can batch-load
 * all params using the minimal set of reads.
 */
export function getParamsByReadCmd(): Map<number, string[]> {
  const groups = new Map<number, string[]>();
  for (const [name, def] of VIRTUAL_PARAMS) {
    const list = groups.get(def.readCmd) ?? [];
    list.push(name);
    groups.set(def.readCmd, list);
  }
  return groups;
}

/**
 * Unique set of read commands that cover the given param names.
 */
export function getReadCmdsForParams(paramNames: string[]): number[] {
  const cmds = new Set<number>();
  for (const name of paramNames) {
    const def = VIRTUAL_PARAMS.get(name);
    if (def) cmds.add(def.readCmd);
  }
  return Array.from(cmds).sort((a, b) => a - b);
}
