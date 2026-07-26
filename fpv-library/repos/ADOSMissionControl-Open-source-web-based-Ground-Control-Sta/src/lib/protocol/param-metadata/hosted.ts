/**
 * Hosted parameter-registry overlay.
 *
 * Fetches a version-matched metadata snapshot from our first-party Convex
 * registry and returns it as an overlay merged over the bundled floor. This is
 * the runtime freshness + version-matching tier; it replaces any direct
 * upstream-firmware fetch (upstream is build-time-only). Best-effort: any
 * failure, or no configured Convex backend (OSS self-host / demo), returns an
 * empty Map so the provider degrades to the bundled floor.
 *
 * @module protocol/param-metadata/hosted
 * @license GPL-3.0-only
 */

import { ConvexHttpClient } from "convex/browser";
import { anyApi } from "convex/server";
import { ungzip } from "pako";
import type { FirmwareType } from "../types";
import type { ParamMetadata, ParamSnapshot } from "./types";
import { deserializeMetaMap } from "./types";

let client: ConvexHttpClient | null = null;
let triedClient = false;

function getClient(): ConvexHttpClient | null {
  if (triedClient) return client;
  triedClient = true;
  const url = process.env.NEXT_PUBLIC_CONVEX_URL;
  if (url) client = new ConvexHttpClient(url);
  return client;
}

function b64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/** Fetch the hosted version-matched snapshot for a firmware. Always resolves. */
export async function fetchHostedOverlay(
  firmware: FirmwareType,
  version?: string | null,
): Promise<Map<string, ParamMetadata>> {
  try {
    const c = getClient();
    if (!c) return new Map();
    const row = await c.query(anyApi.paramRegistry.getSnapshot, {
      firmware,
      version: version ?? undefined,
    });
    if (!row || typeof row.gzB64 !== "string") return new Map();
    const snap = JSON.parse(ungzip(b64ToBytes(row.gzB64), { to: "string" })) as ParamSnapshot;
    return deserializeMetaMap(snap.params ?? []);
  } catch {
    return new Map();
  }
}
