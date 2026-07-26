"use client";

/**
 * @module FleetProjectionBridge
 * @description The single feed from the canonical node registry into the legacy
 * fleet store. Replaces the two ad-hoc projectors (LocalDroneBridge +
 * CloudDroneBridge): the bridges now WRITE the registry (presence + FC), and
 * this component projects the registry back into `fleet-store.drones` so every
 * consumer keeps reading `useFleetStore.drones` unchanged. One physical node
 * collapses to one row regardless of transport, FC-less nodes never render
 * fabricated telemetry, and a cloud tick can never overwrite live flight data.
 *
 * Lowest-risk cutover: this keeps `fleet-store` as the read surface. A
 * follow-up removes `fleet-store.drones` and points consumers at
 * `useFleetDronesFromRegistry()` directly, retiring this bridge.
 * @license GPL-3.0-only
 */

import { useEffect } from "react";
import { useFleetStore } from "@/stores/fleet-store";
import { useFleetDronesFromRegistry } from "@/stores/node-registry/use-fleet-drones";

export function FleetProjectionBridge() {
  const drones = useFleetDronesFromRegistry();

  useEffect(() => {
    // `setDrones` replaces the whole drones array (alerts are untouched). The
    // projection is memoized, so this effect only fires when the registry,
    // a cloud status row, or the 1Hz liveness clock actually changes.
    useFleetStore.getState().setDrones(drones);
  }, [drones]);

  return null;
}
