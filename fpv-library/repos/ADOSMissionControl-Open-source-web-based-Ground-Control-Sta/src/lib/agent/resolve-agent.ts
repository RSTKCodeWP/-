"use client";

/**
 * Resolve the LAN-paired agent (base URL + pairing key) for a drone, read
 * imperatively from `local-nodes-store` at call time. This is the Rule-39
 * local-first agent lookup the plugin bridge uses to reach a specific drone's
 * agent directly (a config write, a vision designate) with no Convex round-trip.
 *
 * Returns null when the drone is not LAN-paired (e.g. a cloud-only drone before
 * the deferred cloud-relay mirror lands); callers surface that honestly rather
 * than acting on the wrong agent.
 *
 * @module agent/resolve-agent
 * @license GPL-3.0-only
 */

import { useLocalNodesStore } from "@/stores/local-nodes-store";

/** A resolved LAN agent target. */
export interface ResolvedLocalAgent {
  /** Base URL of the agent (no trailing slash handling needed; clients trim). */
  agentUrl: string;
  /** Pairing key for that agent. */
  apiKey: string;
}

/** Resolve the LAN agent for `droneId`, or null when it is not LAN-paired. */
export function resolveLocalAgentForDrone(
  droneId: string,
): ResolvedLocalAgent | null {
  const node = useLocalNodesStore
    .getState()
    .nodes.find((n) => n.deviceId === droneId);
  if (!node?.hostname || !node?.apiKey) return null;
  return { agentUrl: node.hostname, apiKey: node.apiKey };
}
