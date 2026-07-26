"use client";

/**
 * @module Px4EventsBridge
 * @description Subscribes to the selected PX4 drone's structured events (MAVLink
 * EVENT msg 410), fetches the FC-served events metadata once, and pushes decoded
 * events into `px4-events-store` so the Logs → Events feed can render them.
 * Runs once (mounted in CommandShell); re-scopes to the selected drone and
 * clears on drone switch. No-op for non-PX4 firmwares (they never emit events).
 * @license GPL-3.0-only
 */

import { useEffect } from "react";
import { useDroneManager } from "@/stores/drone-manager";
import { usePx4EventsStore } from "@/stores/px4-events-store";
import { isDemoMode } from "@/lib/utils";

export function Px4EventsBridge() {
  const selectedId = useDroneManager((s) => s.selectedDroneId);
  const firmwareType = useDroneManager((s) => {
    const d = s.selectedDroneId ? s.drones.get(s.selectedDroneId) : null;
    return d?.vehicleInfo.firmwareType ?? null;
  });

  useEffect(() => {
    usePx4EventsStore.getState().clear();
    const drone = useDroneManager.getState().getSelectedDrone();
    if (!drone || firmwareType !== "px4") return;
    const protocol = drone.protocol;

    let cancelled = false;
    if (isDemoMode()) {
      // Demo mode has no FC-served metadata — seed a small bundled map so the
      // synthetic mock events render with decoded text.
      import("@/mock/px4-demo-events").then((m) => {
        if (!cancelled) usePx4EventsStore.getState().setMetadata(m.DEMO_PX4_EVENT_METADATA);
      });
    } else {
      void usePx4EventsStore.getState().loadMetadata(protocol);
    }

    const unsub = protocol.onEvent((ev) =>
      usePx4EventsStore.getState().pushRaw({
        id: ev.id,
        logLevels: ev.logLevels,
        arguments: ev.arguments,
        eventTimeBootMs: ev.eventTimeBootMs,
      }),
    );
    return () => {
      cancelled = true;
      unsub();
    };
  }, [selectedId, firmwareType]);

  return null;
}
