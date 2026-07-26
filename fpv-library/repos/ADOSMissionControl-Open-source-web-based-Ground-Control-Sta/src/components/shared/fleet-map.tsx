"use client";

import dynamic from "next/dynamic";
import { useDroneMetadataStore } from "@/stores/drone-metadata-store";
import type { FleetDrone } from "@/lib/types";

const MapWrapper = dynamic(
  () => import("./map-wrapper").then((m) => ({ default: m.MapWrapper })),
  { ssr: false }
);
const DroneMarker = dynamic(
  () => import("./drone-marker").then((m) => ({ default: m.DroneMarker })),
  { ssr: false }
);

interface FleetMapProps {
  drones: FleetDrone[];
  onDroneClick?: (id: string) => void;
  className?: string;
}

export function FleetMap({ drones, onDroneClick, className }: FleetMapProps) {
  const profiles = useDroneMetadataStore((s) => s.profiles);
  return (
    <MapWrapper className={className}>
      {drones.map((drone) =>
        drone.position ? (
          <DroneMarker
            key={drone.id}
            id={drone.id}
            name={profiles[drone.id]?.displayName ?? drone.name}
            lat={drone.position.lat}
            lon={drone.position.lon}
            heading={drone.position.heading}
            status={drone.status}
            battery={drone.battery?.remaining}
            onClick={onDroneClick}
          />
        ) : null
      )}
    </MapWrapper>
  );
}
