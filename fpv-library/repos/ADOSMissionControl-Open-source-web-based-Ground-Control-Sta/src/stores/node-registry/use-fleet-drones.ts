"use client";

/**
 * @module NodeRegistry/use-fleet-drones
 * @description React hooks that derive the live `FleetDrone[]` projection from
 * the canonical node registry. The registry holds raw identity / connection /
 * FC state; these hooks subscribe to it plus the command-fleet display statuses
 * and the shared 1Hz clock so OFFLINE transitions flip live without a new write.
 *
 * @license GPL-3.0-only
 */

import { useMemo } from "react";

import type { FleetDrone } from "@/lib/types/drone";
import { useCommandFleetStore } from "@/stores/command-fleet-store";
import { useClockTick } from "@/lib/agent/freshness";
import { useNodeRegistryStore } from "./node-registry-store";
import { selectFleetDrones } from "./select-fleet-drones";

/**
 * The live fleet projection. Recomputes when the registry mutates
 * (`lastUpdate`), when a cloud status row changes, or on the 1Hz clock tick
 * (so a node crossing the offline threshold transitions without a new write).
 */
export function useFleetDronesFromRegistry(): FleetDrone[] {
  const nodes = useNodeRegistryStore((s) => s.nodes);
  const lastUpdate = useNodeRegistryStore((s) => s.lastUpdate);
  const cloudStatuses = useCommandFleetStore((s) => s.cloudStatuses);
  const tick = useClockTick();

  return useMemo(
    () => selectFleetDrones({ nodes, cloudStatuses, now: Date.now() }),
    // `tick` and `lastUpdate` are scalar change signals; including them keeps
    // the projection live without depending on object identity of `nodes`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [nodes, lastUpdate, cloudStatuses, tick],
  );
}
