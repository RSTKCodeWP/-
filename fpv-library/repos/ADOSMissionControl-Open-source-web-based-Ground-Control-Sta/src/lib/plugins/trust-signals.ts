/**
 * @module plugins/trust-signals
 * @description The ONE derivation of a plugin's trust signals from its
 * manifest facts. Every surface that shows trust badges — the install
 * pop-up header, the plugin cards, the MCP tab — resolves the same signal
 * set here so a plugin never reads as "verified" on one surface and
 * "unsigned" on another.
 *
 * A first-party signer id (`altnautica-YYYY-X`) is the strongest claim: it
 * implies the archive is signed AND published by a verified first-party
 * publisher. Any other signer id means only that the archive is signed. An
 * open (auditable) license adds the open-source signal, and a declared
 * closed vendor binary adds the vendor-binary signal.
 *
 * @license GPL-3.0-only
 */

import type { TrustSignal } from "@/components/plugins/TrustBadge";

/** A first-party Ed25519 signer key id, e.g. `altnautica-2026-A`. */
const FIRST_PARTY_SIGNER = /^altnautica-\d{4}-[A-Z]$/;

/**
 * Open-source SPDX license id fragments. A license string containing any of
 * these (case-insensitive) is treated as publicly auditable. Kept as
 * substrings so `GPL-3.0-or-later`, `GPL-3.0-only`, `Apache-2.0`, etc. all
 * resolve without an exhaustive SPDX table.
 */
const OPEN_LICENSE_HINTS: readonly string[] = [
  "gpl",
  "lgpl",
  "agpl",
  "mit",
  "apache",
  "bsd",
  "mpl",
  "cc0",
  "cc-by",
  "isc",
  "unlicense",
  "zlib",
];

/**
 * The manifest facts the trust derivation reads. A structural subset of
 * `InstallManifestSummary` so any caller can pass the summary (or a lean
 * card row) without a cast.
 */
export interface TrustSignalInput {
  /** Ed25519 signer key id from the signed archive, when present. */
  signerId?: string;
  /** SPDX license string declared in the manifest. */
  license?: string;
  /** Declared closed-source vendor-binary attribution rows, if any. */
  vendorAttribution?: ReadonlyArray<{ name?: string }>;
}

/**
 * Resolve the full logical trust-signal set for a plugin. Callers that want
 * a de-duplicated display set (first-party subsumes verified-publisher) use
 * {@link displayTrustSignals}.
 */
export function deriveTrustSignals(input: TrustSignalInput): TrustSignal[] {
  const signals: TrustSignal[] = [];
  const signer = input.signerId?.trim();
  if (signer) {
    signals.push("signed");
    if (isFirstPartySignerId(signer)) {
      signals.push("verified-publisher");
      signals.push("first-party");
    }
  }
  if (isOpenLicense(input.license)) signals.push("open-source");
  if (input.vendorAttribution && input.vendorAttribution.length > 0) {
    signals.push("vendor-binary");
  }
  return signals;
}

/**
 * The trust-signal set to render as badges. Identical to
 * {@link deriveTrustSignals} except `verified-publisher` is dropped when
 * `first-party` is present — first-party is the stronger claim, so showing
 * both is redundant noise on a header row.
 */
export function displayTrustSignals(input: TrustSignalInput): TrustSignal[] {
  const all = deriveTrustSignals(input);
  if (all.includes("first-party")) {
    return all.filter((s) => s !== "verified-publisher");
  }
  return all;
}

/**
 * True for a signer key id in the first-party allowlist form
 * `altnautica-YYYY-X`. The single predicate every surface shares so the
 * `altnautica-\d{4}-[A-Z]` shape is written down exactly once.
 */
export function isFirstPartySignerId(signerId?: string | null): boolean {
  return !!signerId && FIRST_PARTY_SIGNER.test(signerId.trim());
}

/** True when a plugin is first-party (a verified-publisher signer). */
export function isFirstParty(input: TrustSignalInput): boolean {
  return isFirstPartySignerId(input.signerId);
}

function isOpenLicense(license?: string): boolean {
  if (!license) return false;
  const l = license.toLowerCase();
  return OPEN_LICENSE_HINTS.some((hint) => l.includes(hint));
}
