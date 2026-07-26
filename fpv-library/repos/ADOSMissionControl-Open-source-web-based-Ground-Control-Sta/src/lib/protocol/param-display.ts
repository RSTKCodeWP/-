/**
 * Human-readable parameter value formatting (enums, bitmasks).
 *
 * @module protocol/param-display
 * @license GPL-3.0-only
 */

import type { ParamMetadata } from "./param-metadata";

/** Decoded view of a bitmask value: labels for set documented bits + the
 *  bit indices that are set but not described by the metadata. */
export interface DecodedBitmask {
  set: string[];
  unknownBits: number[];
}

/**
 * Decode a numeric bitmask value against its bit→label metadata.
 * Bits set in the value but absent from the metadata are returned in
 * `unknownBits` so the UI can surface (and never silently drop) them.
 */
export function decodeBitmaskFlags(
  value: number,
  bitmask: Map<number, string>,
): DecodedBitmask {
  const intVal = Math.trunc(value) >>> 0;
  const set: string[] = [];
  for (const [bit, label] of [...bitmask.entries()].sort((a, b) => a[0] - b[0])) {
    if (bit >= 0 && bit < 32 && (intVal & (1 << bit)) !== 0) set.push(label);
  }
  const unknownBits: number[] = [];
  for (let i = 0; i < 32; i++) {
    if ((intVal & (1 << i)) !== 0 && !bitmask.has(i)) unknownBits.push(i);
  }
  return { set, unknownBits };
}

/**
 * Compact summary of a bitmask value for a grid cell.
 * `0` → "0"; few flags → "Label A, Label B (5)"; many → "A, B +3 (255)".
 * Unknown set bits are counted toward the overflow as "bitN".
 */
export function summarizeBitmask(
  value: number,
  bitmask: Map<number, string>,
  maxLabels = 2,
): string {
  const intVal = Math.trunc(value) >>> 0;
  if (intVal === 0) return "0";
  const { set, unknownBits } = decodeBitmaskFlags(value, bitmask);
  const labels = [...set, ...unknownBits.map((b) => `bit${b}`)];
  if (labels.length === 0) return String(intVal);
  if (labels.length <= maxLabels) return `${labels.join(", ")} (${intVal})`;
  const shown = labels.slice(0, maxLabels).join(", ");
  return `${shown} +${labels.length - maxLabels} (${intVal})`;
}

/**
 * Format a numeric param value for read-only display.
 * Bitmask params become a decoded summary; enum params become "5 — Loiter";
 * others return the numeric string.
 */
export function formatParamDisplayValue(
  value: number,
  meta?: ParamMetadata | null,
): string {
  if (meta?.bitmask && meta.bitmask.size > 0) {
    return summarizeBitmask(value, meta.bitmask);
  }
  if (meta?.values && meta.values.size > 0) {
    // Exact key match; MAVLink params are often integers stored as floats.
    const intKey = Math.trunc(value);
    const label =
      meta.values.get(value) ??
      meta.values.get(intKey) ??
      (Number.isInteger(value) ? undefined : meta.values.get(Math.round(value)));
    if (label !== undefined) {
      const shown = Number.isInteger(value) ? value : intKey;
      return `${shown} — ${label}`;
    }
  }
  return String(value);
}
