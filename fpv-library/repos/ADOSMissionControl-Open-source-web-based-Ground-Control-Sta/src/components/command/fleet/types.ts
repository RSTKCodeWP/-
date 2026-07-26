/**
 * @module fleet/types
 * @description Shared types and helpers for fleet sidebar sub-components.
 * @license GPL-3.0-only
 */

import type { PairedDrone } from "@/stores/pairing-store";
import {
  STALE_THRESHOLD_MS,
  OFFLINE_THRESHOLD_MS,
} from "@/lib/agent/freshness";

export type DroneLiveness = "live" | "stale" | "offline";

export type RenameDroneMutation =
  | ((args: { droneId: never; name: string }) => Promise<unknown>)
  | null;

export type UnpairDroneMutation =
  | ((args: { droneId: never }) => Promise<unknown>)
  | null;

export function droneLiveness(
  drone: PairedDrone & { isDirectFc?: boolean },
): DroneLiveness {
  // A direct-connect FC (USB/serial/TCP/BT/WS) is live-by-presence: it only
  // exists in the fleet list while its transport is open (it is removed on
  // disconnect), so it never ages to stale/offline against a heartbeat clock.
  if (drone.isDirectFc) return "live";
  if (!drone.lastSeen) return "offline";
  const elapsed = Date.now() - drone.lastSeen;
  if (elapsed < STALE_THRESHOLD_MS) return "live";
  if (elapsed < OFFLINE_THRESHOLD_MS) return "stale";
  return "offline";
}

export function dotClass(liveness: DroneLiveness): string {
  switch (liveness) {
    case "live":
      return "bg-status-success";
    case "stale":
      return "bg-status-warning animate-pulse";
    case "offline":
      return "bg-text-tertiary/30";
  }
}

export function tierLabel(tier?: number): string | null {
  if (!tier) return null;
  return `T${tier}`;
}
