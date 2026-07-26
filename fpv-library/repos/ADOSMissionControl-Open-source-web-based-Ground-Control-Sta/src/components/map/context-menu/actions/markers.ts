/**
 * @module map/context-menu/actions/markers
 * @description Marker action handlers: rally points, POI markers, set-heading.
 * The add-poi action goes through a label-input sub-panel; this module exposes
 * the confirm handler the panel calls.
 * @license GPL-3.0-only
 */

import type { DroneProtocol } from "@/lib/protocol/types";
import type { RallyPoint } from "@/stores/rally-store";
import { bearing } from "@/lib/telemetry-utils";
import type { MenuPosition } from "../types";

interface AddRallyArgs {
  menuPos: MenuPosition;
  relativeAlt: number | undefined;
  addRally: (point: RallyPoint) => void;
  uploadRally: () => Promise<void> | void;
}

export function handleAddRally({ menuPos, relativeAlt, addRally, uploadRally }: AddRallyArgs): void {
  addRally({
    id: `rally-${Date.now()}`,
    lat: menuPos.lat,
    lon: menuPos.lon,
    alt: relativeAlt ?? 30,
  });
  void uploadRally();
}

interface AddPoiArgs {
  menuPos: MenuPosition;
  label: string;
  addPoi: (lat: number, lon: number, label: string) => void;
}

export function handleAddPoiConfirmed({ menuPos, label, addPoi }: AddPoiArgs): void {
  addPoi(menuPos.lat, menuPos.lon, label);
}

interface SetHeadingArgs {
  protocol: DroneProtocol | null;
  menuPos: MenuPosition;
  fromLat: number;
  fromLon: number;
}

export function handleSetHeading({ protocol, menuPos, fromLat, fromLon }: SetHeadingArgs): void {
  if (!protocol) return;
  const brng = bearing(fromLat, fromLon, menuPos.lat, menuPos.lon);
  protocol.setYaw(brng, 30, 1, false);
}
