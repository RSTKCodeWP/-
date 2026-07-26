"use client";

import { useFleetStore } from "@/stores/fleet-store";
import { useDroneManager } from "@/stores/drone-manager";
import { FleetMap } from "@/components/shared/fleet-map";

export function DashboardMap() {
  const drones = useFleetStore((s) => s.drones);
  const selectDrone = useDroneManager((s) => s.selectDrone);

  return (
    <FleetMap
      drones={drones}
      onDroneClick={selectDrone}
      className="w-full h-full min-h-[300px]"
    />
  );
}
