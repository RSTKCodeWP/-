/**
 * @module plan-share
 * @description Client-only shareable plan links. A mission (waypoints + name +
 * geofence/rally) is serialized to the SAME `.altmission` JSON shape used for file
 * export, deflate-compressed with pako, and base64url-encoded into a URL fragment
 * (`#plan=...`). Everything happens in the browser — no server, no upload, nothing
 * leaves the machine except the link the operator chooses to copy. Decoding is
 * defensive: a malformed or oversized fragment yields `null`, never a partial or
 * fabricated plan.
 * @license GPL-3.0-only
 */

import { deflate, inflate } from "pako";
import type { MissionFile, MissionMetadata, MissionExtras } from "@/lib/mission-io";
import type { Waypoint } from "@/lib/types";

/** The URL fragment key: `#plan=<encoded>`. */
export const SHARE_HASH_KEY = "plan";

/**
 * Practical ceiling on the encoded length. Browsers and servers vary, but ~8000
 * characters keeps the whole URL comfortably under common limits. Beyond this the
 * caller should fall back to file export rather than a link.
 */
export const SHARE_MAX_ENCODED_LEN = 8000;

// ── base64url (URL-safe, no padding) ─────────────────────────

function bytesToBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlToBytes(s: string): Uint8Array {
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/");
  const pad = b64.length % 4 === 0 ? "" : "=".repeat(4 - (b64.length % 4));
  const binary = atob(b64 + pad);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

// ── Encode ───────────────────────────────────────────────────

/** Build the `.altmission`-shaped file object for a plan. */
export function buildMissionFile(
  waypoints: Waypoint[],
  metadata: MissionMetadata,
  extras?: MissionExtras,
): MissionFile {
  return {
    version: 1,
    metadata,
    waypoints,
    ...(extras?.geofence ? { geofence: extras.geofence } : {}),
    ...(extras?.rally && extras.rally.length > 0 ? { rally: extras.rally } : {}),
  };
}

/** Deflate + base64url-encode a mission file into a shareable fragment value. */
export function encodePlan(file: MissionFile): string {
  const json = JSON.stringify(file);
  const compressed = deflate(json);
  return bytesToBase64Url(compressed);
}

/** Result of trying to build a share link. */
export interface ShareLinkResult {
  /** The encoded fragment value, or null when the plan is too large to share as a link. */
  encoded: string | null;
  /** Encoded length (for the too-large message). */
  length: number;
  /** True when `encoded` exceeds {@link SHARE_MAX_ENCODED_LEN}. */
  tooLarge: boolean;
}

/**
 * Encode a plan and report whether it fits within the link-size ceiling. When
 * `tooLarge`, `encoded` is null and the caller should offer file export instead.
 */
export function makeShareLink(file: MissionFile): ShareLinkResult {
  const encoded = encodePlan(file);
  if (encoded.length > SHARE_MAX_ENCODED_LEN) {
    return { encoded: null, length: encoded.length, tooLarge: true };
  }
  return { encoded, length: encoded.length, tooLarge: false };
}

/** Build a full share URL for the current page + an encoded fragment. */
export function buildShareUrl(origin: string, pathname: string, encoded: string): string {
  return `${origin}${pathname}#${SHARE_HASH_KEY}=${encoded}`;
}

// ── Decode ───────────────────────────────────────────────────

/**
 * Decode a fragment value back into a mission file. Returns `null` for any bad
 * input (not base64url, not deflate, not JSON, or not a valid mission shape) so a
 * tampered or truncated link can never load a partial plan.
 */
export function decodePlan(encoded: string): MissionFile | null {
  if (!encoded || encoded.length > SHARE_MAX_ENCODED_LEN * 4) return null;
  try {
    const bytes = base64UrlToBytes(encoded);
    const json = inflate(bytes, { to: "string" });
    const data = JSON.parse(json) as MissionFile;
    if (
      data.version !== 1 ||
      !Array.isArray(data.waypoints) ||
      !data.metadata ||
      typeof data.metadata.name !== "string"
    ) {
      return null;
    }
    return data;
  } catch {
    return null;
  }
}

/**
 * Read a `#plan=<encoded>` value from a URL hash string (e.g. `window.location.hash`),
 * returning the decoded mission file or null. The hash may include the leading `#`.
 */
export function readPlanFromHash(hash: string): MissionFile | null {
  const raw = hash.startsWith("#") ? hash.slice(1) : hash;
  const params = new URLSearchParams(raw);
  const encoded = params.get(SHARE_HASH_KEY);
  return encoded ? decodePlan(encoded) : null;
}
