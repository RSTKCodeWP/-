/**
 * @module lib/api/signing-events
 * @description Append signing-event rows to the Convex audit log.
 *
 * Every user-triggered signing action in the GCS flows through this
 * module. When the user is not authenticated the emitter becomes a
 * silent no-op: anonymous enrollments still populate the local keystore
 * and the FC, they just don't produce cloud audit rows. This is by
 * design, since the audit table is scoped to `userId`.
 *
 * Log discipline: NEVER pass `keyHex` here. Pass only the 8-char
 * fingerprint through `keyIdOld` / `keyIdNew`.
 *
 * @license GPL-3.0-only
 */

import type { ConvexReactClient } from "convex/react";
import { cmdSigningEventsApi } from "@/lib/community-api-drones";
import { getOrCreateDeviceId } from "@/lib/protocol/link-id-allocator";

export type SigningEventType =
  | "enrollment"
  | "rotation"
  | "import"
  | "export"
  | "disable"
  | "cloud_sync_on"
  | "cloud_sync_off"
  | "clear_fc"
  | "key_mismatch_detected"
  | "user_purge_on_signout"
  | "fc_rejected_enrollment"
  | "require_on"
  | "require_off";

export interface EmitArgs {
  droneId: string;
  eventType: SigningEventType;
  keyIdOld?: string;
  keyIdNew?: string;
}

/**
 * Emit a signing event. Returns true when the row was written, false
 * when we intentionally skipped (e.g., user is signed out) or when the
 * write failed in a way that should not block the UI.
 *
 * Failures never throw: the audit log is defense-in-depth, not critical
 * path. A missing event must not prevent the operator from enrolling,
 * rotating, or disabling a key.
 */
export async function emitSigningEvent(
  client: ConvexReactClient | null,
  isAuthenticated: boolean,
  args: EmitArgs,
): Promise<boolean> {
  if (!client || !isAuthenticated) return false;
  try {
    await client.mutation(cmdSigningEventsApi.append, {
      droneId: args.droneId,
      eventType: args.eventType,
      keyIdOld: args.keyIdOld,
      keyIdNew: args.keyIdNew,
      deviceFingerprint: shortFingerprint(getOrCreateDeviceId()),
    });
    return true;
  } catch (err) {
    // Non-fatal. Write to console for operator visibility but do not
    // surface an error in the UI: the primary action already succeeded.
    console.warn("[signing] audit append failed", err);
    return false;
  }
}

/**
 * Short fingerprint of the stable per-browser device id. 12 hex chars is
 * enough to group same-device events in the audit log without leaking
 * the full random UUID. Stable across page reloads because the source
 * id is persisted to localStorage under `ados-device-id`.
 */
function shortFingerprint(tabId: string): string {
  // Simple polynomial hash → 12 hex chars. Not cryptographic; the goal
  // is stable-per-tab and short, not collision-resistant.
  let h1 = 0;
  let h2 = 0;
  for (let i = 0; i < tabId.length; i++) {
    const c = tabId.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 2654435761) | 0;
    h2 = Math.imul(h2 ^ c, 1597334677) | 0;
  }
  const lo = (h1 >>> 0).toString(16).padStart(8, "0");
  const hi = (h2 >>> 0).toString(16).padStart(8, "0").slice(0, 4);
  return `${lo}${hi}`;
}
