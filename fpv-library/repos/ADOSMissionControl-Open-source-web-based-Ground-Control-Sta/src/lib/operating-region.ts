/**
 * @module lib/operating-region
 * @description Shared helpers for the radio operating-region control. A
 * fresh agent ships UNRESTRICTED: the radio comes up and transmits on the
 * configured channel without a verified regulatory domain, and the
 * operator is responsible for legal RF operation in their jurisdiction.
 * The operator opts into a region (an ISO 3166-1 alpha-2 country code) to
 * re-enable the strict regulatory gate and the region's legal power limit.
 *
 * The region picker, the onboarding step, and the per-node preference all
 * speak the same vocabulary defined here, so the agent config keys
 * (`network.regulatory.mode` + `network.regulatory.region`) round-trip
 * identically across surfaces.
 *
 * @license GPL-3.0-only
 */

/** The two regulatory postures the agent supports. */
export type RegulatoryMode = "unrestricted" | "region";

/** Sentinel `<Select>` value for the unrestricted (no-region) option. */
export const UNRESTRICTED_VALUE = "unrestricted";

/** Sentinel `<Select>` value that reveals a free-text ISO-code field. */
export const OTHER_REGION_VALUE = "__other__";

/**
 * A short list of common operating regions offered as one-click picks. The
 * full ISO 3166-1 alpha-2 space is reachable via the "Other" free-text
 * field, so this list is convenience, not a whitelist. Labels are plain
 * country names; the picker prepends the unrestricted option and appends
 * "Other" at render time.
 */
export const COMMON_REGIONS: { code: string; name: string }[] = [
  { code: "US", name: "United States" },
  { code: "IN", name: "India" },
  { code: "DE", name: "Germany" },
  { code: "GB", name: "United Kingdom" },
  { code: "AU", name: "Australia" },
  { code: "JP", name: "Japan" },
  { code: "CA", name: "Canada" },
];

/**
 * Normalize a free-text region entry to the agent's expected shape: an
 * uppercase two-letter A-Z code. Returns null when the input is not a
 * well-formed alpha-2 code, so the caller can reject it before writing
 * config. An empty / whitespace input also returns null.
 */
export function normalizeRegionCode(raw: string): string | null {
  const trimmed = raw.trim().toUpperCase();
  if (/^[A-Z]{2}$/.test(trimmed)) return trimmed;
  return null;
}

/** True when the code is one of the common one-click picks. */
export function isCommonRegion(code: string): boolean {
  return COMMON_REGIONS.some((r) => r.code === code);
}

/**
 * Resolve the human-readable name for a region code, falling back to the
 * uppercased code itself for any ISO code not in the common list.
 */
export function regionName(code: string): string {
  const match = COMMON_REGIONS.find((r) => r.code === code.toUpperCase());
  return match ? match.name : code.toUpperCase();
}
