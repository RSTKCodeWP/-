"use client";

import { useState, useCallback } from "react";
import { useParamSafetyStore } from "@/stores/param-safety-store";
import { useDroneManager } from "@/stores/drone-manager";

export function useDisconnectGuard() {
  const [guardOpen, setGuardOpen] = useState(false);
  const [pendingDroneId, setPendingDroneId] = useState<string | null>(null);

  const requestDisconnect = useCallback((droneId: string) => {
    const pendingCount = useParamSafetyStore.getState().getPendingCount();
    if (pendingCount > 0) {
      setPendingDroneId(droneId);
      setGuardOpen(true);
    } else {
      // No pending writes, disconnect immediately
      const drone = useDroneManager.getState().drones.get(droneId);
      if (drone) {
        drone.protocol.disconnect().catch(() => {});
      }
      useDroneManager.getState().disconnectDrone(droneId);
    }
  }, []);

  const commitAndDisconnect = useCallback(() => {
    if (!pendingDroneId) return;
    const drone = useDroneManager.getState().drones.get(pendingDroneId);
    if (drone) {
      // Fire-and-forget flash commit
      drone.protocol.commitParamsToFlash().catch(() => {});
      drone.protocol.disconnect().catch(() => {});
    }
    useParamSafetyStore.getState().commitFlash(true);
    useDroneManager.getState().disconnectDrone(pendingDroneId);
    setPendingDroneId(null);
    setGuardOpen(false);
  }, [pendingDroneId]);

  const discardAndDisconnect = useCallback(() => {
    if (!pendingDroneId) return;
    const drone = useDroneManager.getState().drones.get(pendingDroneId);
    if (drone) {
      drone.protocol.disconnect().catch(() => {});
    }
    useParamSafetyStore.getState().clear();
    useDroneManager.getState().disconnectDrone(pendingDroneId);
    setPendingDroneId(null);
    setGuardOpen(false);
  }, [pendingDroneId]);

  const cancelDisconnect = useCallback(() => {
    setPendingDroneId(null);
    setGuardOpen(false);
  }, []);

  return {
    guardOpen,
    commitAndDisconnect,
    discardAndDisconnect,
    cancelDisconnect,
    requestDisconnect,
  };
}
