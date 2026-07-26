import type { ParamMetadata } from "@/lib/protocol/param-metadata";

/** MAV_PARAM_TYPE display names. */
export const PARAM_TYPE_LABELS: Record<number, string> = {
  1: "UINT8",
  2: "INT8",
  3: "UINT16",
  4: "INT16",
  5: "UINT32",
  6: "INT32",
  8: "UINT64",
  9: "INT64",
  10: "REAL32",
  11: "REAL64",
};

/** Read-only parameter name patterns. */
const READ_ONLY_PATTERNS = [/^STAT_/, /^INS_\w+_ID$/, /^GND_\w+_ID$/];

export function isReadOnly(name: string, _meta: ParamMetadata | undefined): boolean {
  return READ_ONLY_PATTERNS.some((p) => p.test(name));
}

/** Dangerous value validation rules for specific parameter patterns. */
interface DangerousRule {
  test: (name: string) => boolean;
  check: (value: number) => boolean;
  message: string;
}

const DANGEROUS_VALUE_RULES: DangerousRule[] = [
  { test: (n) => n === "BATT_CAPACITY", check: (v) => v < 0, message: "Battery capacity cannot be negative" },
  { test: (n) => n === "MOT_SPIN_ARM", check: (v) => v === 0, message: "Zero spin arm may prevent motor start" },
  { test: (n) => n.startsWith("FS_") && n.endsWith("_TIMEOUT"), check: (v) => v < 0, message: "Failsafe timeout cannot be negative" },
  { test: (n) => n === "FENCE_ALT_MAX", check: (v) => v < 0, message: "Fence max altitude cannot be negative" },
  { test: (n) => n === "FENCE_RADIUS", check: (v) => v < 0, message: "Fence radius cannot be negative" },
  { test: (n) => n === "BATT_LOW_VOLT", check: (v) => v < 0, message: "Low battery voltage cannot be negative" },
  { test: (n) => n === "BATT_CRT_VOLT", check: (v) => v < 0, message: "Critical battery voltage cannot be negative" },
];

export function getDangerousWarning(name: string, value: number): string | null {
  for (const rule of DANGEROUS_VALUE_RULES) {
    if (rule.test(name) && rule.check(value)) return rule.message;
  }
  return null;
}

/** Check if a value is outside the parameter's defined range. */
export function isValueOutOfRange(value: number, meta: ParamMetadata | undefined): boolean {
  if (!meta?.range) return false;
  return value < meta.range.min || value > meta.range.max;
}

/**
 * Match a parameter against a lowercased search term across its name,
 * human-friendly name, description, AND its enum/bitmask option labels — so a
 * query like "double notch" finds INS_HNTCH_OPTS. `lower` must already be
 * lowercased by the caller.
 */
export function paramMatchesFilter(
  name: string,
  meta: ParamMetadata | undefined,
  lower: string,
): boolean {
  if (name.toLowerCase().includes(lower)) return true;
  if (!meta) return false;
  if (meta.humanName?.toLowerCase().includes(lower)) return true;
  if (meta.description?.toLowerCase().includes(lower)) return true;
  if (meta.values) for (const label of meta.values.values()) if (label.toLowerCase().includes(lower)) return true;
  if (meta.bitmask) for (const label of meta.bitmask.values()) if (label.toLowerCase().includes(lower)) return true;
  return false;
}

/**
 * Build a per-param lowercased search haystack (name + humanName + description
 * + all enum/bitmask labels), so the grid filter is a single `.includes` per
 * keystroke instead of re-walking every param's option Maps.
 */
export function buildSearchHaystack(
  meta: Map<string, ParamMetadata> | undefined,
  names: string[],
): Map<string, string> {
  const out = new Map<string, string>();
  for (const name of names) {
    const m = meta?.get(name);
    const parts = [name];
    if (m) {
      if (m.humanName) parts.push(m.humanName);
      if (m.description) parts.push(m.description);
      if (m.values) for (const l of m.values.values()) parts.push(l);
      if (m.bitmask) for (const l of m.bitmask.values()) parts.push(l);
    }
    out.set(name, parts.join(" ").toLowerCase());
  }
  return out;
}
