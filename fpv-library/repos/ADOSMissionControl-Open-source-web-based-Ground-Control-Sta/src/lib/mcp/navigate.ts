/**
 * @module lib/mcp/navigate
 * @description Turns an MCP activity row's target surface into a GCS navigation:
 * select the affected node, open its node-detail tab, and route there. Shared by
 * the manual "jump to" affordance (a row click) and the auto-navigate follow
 * bridge so both resolve identity + surface the same way. Route changes ride a
 * `ados:navigate` CustomEvent handled once in CommandShell (non-component code
 * cannot call `useRouter`).
 * @license GPL-3.0-only
 */

import { useDroneManager } from "@/stores/drone-manager";
import { useFleetStore } from "@/stores/fleet-store";
import { useUiStore } from "@/stores/ui-store";
import { nodeIdForDevice } from "@/lib/agent/node-id";
import type { McpActivityRow } from "@/lib/mcp/activity";

/** The route event CommandShell listens for to push a Next route. */
export const MCP_NAVIGATE_EVENT = "ados:navigate";

/**
 * Resolve an activity row's `node` (a deviceId in fleet-mode, an id or `local`
 * in agent-mode) to a selectable fleet-row id — mirrors the Dashboard's
 * `handleOpenAgent` mapping. Returns null when no fleet row matches (the tool
 * ran against a node not present in this GCS's fleet).
 */
export function resolveFleetRowId(node: string): string | null {
  const fleet = useFleetStore.getState().drones;
  // A direct-FC id (fc:<random>) or an already-canonical node id is a row id.
  if (fleet.some((d) => d.id === node)) return node;
  const nid = nodeIdForDevice(node);
  if (fleet.some((d) => d.id === nid)) return nid;
  const match = fleet.find((d) => d.cloudDeviceId === node);
  return match ? match.id : null;
}

/** A short display name for a target node — the fleet drone's name when it
 *  resolves, else a trimmed node string (`local` for the agent-mode default). */
export function nodeDisplayName(node: string): string {
  if (!node || node === "local") return "local";
  const rowId = resolveFleetRowId(node);
  if (rowId) {
    const d = useFleetStore.getState().drones.find((x) => x.id === rowId);
    if (d?.name) return d.name;
  }
  return node.length > 12 ? `${node.slice(0, 10)}…` : node;
}

export function requestRoute(path: string): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(MCP_NAVIGATE_EVENT, { detail: path }));
}

/**
 * Navigate to the surface an activity row acted on. Returns the resolved
 * fleet-row id when a node was selected (so a caller can drive a spotlight),
 * `"routed"` for a whole-page route with no node, or null when nothing could be
 * resolved (feed-only row).
 */
export function navigateToRow(row: McpActivityRow): string | "routed" | null {
  const surface = row.surface;
  if (!surface) return null;

  if (surface.kind === "route") {
    requestRoute(surface.path);
    return "routed";
  }

  const rowId = resolveFleetRowId(row.node);
  if (!rowId) return null;
  useDroneManager.getState().selectDrone(rowId);
  useUiStore.getState().setPendingDetailTab(surface.id);
  requestRoute("/");
  return rowId;
}
