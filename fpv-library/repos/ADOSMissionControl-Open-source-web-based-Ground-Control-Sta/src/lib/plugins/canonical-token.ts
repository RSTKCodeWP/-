/**
 * Canonical-JSON helpers for the multi-issuer capability-token wire
 * format. Mirrors the agent's `_canonical_claims_blob` exactly so
 * tokens minted by either side verify on the other.
 *
 * Wire format (matches `capability-token-claims.ts` parser):
 *
 *     urlsafe_b64(canonical_json_blob) + "." + urlsafe_b64(hmac_sha256_sig)
 *
 * Canonical JSON: sorted top-level keys, no whitespace, no trailing
 * newline. The claims shape carries primitive fields and one flat
 * `grantedCapabilities` string array, so nested-object sorting is not
 * required. If the claims grow a nested object in a future revision,
 * extend this helper to sort recursively (and bump the wire version on
 * the envelope before either side rolls out).
 *
 * The verifier in `capability-token-claims.ts` reconstructs the claims
 * from the blob's raw bytes, never by re-serialising. Signing therefore
 * runs over the EXACT bytes that the verifier reads, which sidesteps a
 * full class of "my JSON looks the same but its bytes differ" bugs.
 *
 * @license GPL-3.0-only
 */

import type { TokenClaims } from "./capability-token-claims";

/** Serialise claims into the canonical UTF-8 byte string the agent and
 * the GCS sign and verify against.
 *
 * Top-level keys are emitted in deterministic alphabetical order to
 * match Python's `json.dumps(..., sort_keys=True, separators=(",", ":"))`.
 */
export function canonicalClaimsBytes(claims: TokenClaims): Uint8Array {
  const sortedKeys: ReadonlyArray<keyof TokenClaims> = [
    "agentId",
    "expiresAt",
    "grantedCapabilities",
    "iss",
    "operatorId",
    "pluginId",
  ];
  const obj: Record<string, unknown> = {};
  for (const k of sortedKeys) obj[k] = claims[k];
  return new TextEncoder().encode(JSON.stringify(obj));
}

/** URL-safe base64 without `=` padding. Compatible with the verifier's
 * tolerant decoder that accepts both URL-safe and standard alphabets. */
export function urlsafeB64NoPad(bytes: Uint8Array): string {
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Sign `claims` with the given HMAC-SHA256 key and emit the canonical
 * `<urlsafe-b64-blob>.<urlsafe-b64-sig>` wire token. */
export async function signCanonicalToken(
  claims: TokenClaims,
  key: CryptoKey,
): Promise<string> {
  const blob = canonicalClaimsBytes(claims);
  const sig = new Uint8Array(
    await crypto.subtle.sign("HMAC", key, blob as BufferSource),
  );
  return `${urlsafeB64NoPad(blob)}.${urlsafeB64NoPad(sig)}`;
}
