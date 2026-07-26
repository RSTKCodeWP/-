/**
 * @module map/context-menu/actions/navigation
 * @description Navigation action handlers: fly-here, loiter, land. The orbit
 * action defers to a sub-panel and is wired in the orchestrator.
 * @license GPL-3.0-only
 */

import type { DroneProtocol } from "@/lib/protocol/types";
import type { MenuPosition } from "../types";

interface FlyHereArgs {
  menuPos: MenuPosition;
  rectLeft: number;
  rectTop: number;
  showConfirm: (lat: number, lon: number, screenX: number, screenY: number) => void;
}

export function handleFlyHere({ menuPos, rectLeft, rectTop, showConfirm }: FlyHereArgs): void {
  showConfirm(menuPos.lat, menuPos.lon, rectLeft + menuPos.x, rectTop + menuPos.y);
}

interface LoiterArgs {
  protocol: DroneProtocol | null;
  menuPos: MenuPosition;
  relativeAlt: number | undefined;
}

export function handleLoiterHere({ protocol, menuPos, relativeAlt }: LoiterArgs): void {
  if (!protocol) return;
  protocol.setFlightMode("LOITER");
  protocol.guidedGoto(menuPos.lat, menuPos.lon, relativeAlt ?? 10);
}

export function handleLandHere({ protocol, menuPos, relativeAlt }: LoiterArgs): void {
  if (!protocol) return;
  protocol.guidedGoto(menuPos.lat, menuPos.lon, relativeAlt ?? 10);
  setTimeout(() => protocol.land(), 500);
}
