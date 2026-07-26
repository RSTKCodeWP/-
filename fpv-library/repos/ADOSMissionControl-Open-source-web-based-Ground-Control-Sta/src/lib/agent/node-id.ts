/**
 * @module node-id
 * @description The one canonical fleet-identity id format. A node selected on
 * any surface (the sidebar list, the grid, the post-pair handoff, the FC
 * attach) is keyed by `node:<deviceId>` — the same string the node registry
 * mints in `resolveNodeId`. This collapses the historical split between the
 * colon form (`local:<deviceId>`, used by `pairing-store.selectedPairedId`)
 * and the hyphen form (`local-<deviceId>` / `cloud-<deviceId>`, used by the
 * old fleet-store projector ids) onto a single space, so a node has ONE
 * selection id regardless of whether it was seen over the local or cloud
 * transport. After this, `pairing-store.selectedPairedId` and
 * `drone-manager.selectedDroneId` hold the identical `node:<deviceId>`.
 *
 * @license GPL-3.0-only
 */

import { resolveNodeId } from "@/stores/node-registry";

/** The prefix every agent-node id carries. */
const NODE_PREFIX = "node:";

/**
 * Canonical node id for an agent device id. Always `node:<trimmed deviceId>`.
 * Equivalent to the registry's `resolveNodeId(deviceId)` when a non-empty
 * device id is supplied; exposed here so selection / guard sites never form
 * the string by hand.
 */
export function nodeIdForDevice(deviceId: string): string {
  return `${NODE_PREFIX}${deviceId.trim()}`;
}

/**
 * Recover the agent device id from a `node:<deviceId>` id, or null when the
 * id is not an agent-node id (e.g. an `fc:<random>` direct-FC id, or an empty
 * payload). Callers that need the underlying device id (to look up LAN
 * credentials, drive a cloud unpair, etc.) go through this rather than slicing
 * a literal prefix.
 */
export function deviceIdFromNodeId(nodeId: string | null | undefined): string | null {
  if (!nodeId || !nodeId.startsWith(NODE_PREFIX)) return null;
  const deviceId = nodeId.slice(NODE_PREFIX.length).trim();
  return deviceId.length > 0 ? deviceId : null;
}

/**
 * Resolve a node id from an optional device id. A present device id yields the
 * canonical `node:<deviceId>`; an absent one yields a fresh `fc:<random>` for a
 * direct flight controller with no agent identity. This is the registry's
 * `resolveNodeId` re-exported under the agent-id module so the bridges import
 * one symbol for both the agent-node and direct-FC cases.
 */
export { resolveNodeId };
