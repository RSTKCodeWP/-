/**
 * @module map/context-menu/actions/orbit
 * @description Orbit action handler. Invoked from the orbit configuration
 * sub-panel when the operator confirms radius and direction.
 * @license GPL-3.0-only
 */

import type { DroneProtocol } from "@/lib/protocol/types";
import type { MenuPosition } from "../types";

interface OrbitArgs {
  protocol: DroneProtocol | null;
  menuPos: MenuPosition;
  radius: number;
  clockwise: boolean;
  relativeAlt: number | undefined;
}

export function handleOrbitConfirmed({
  protocol,
  menuPos,
  radius,
  clockwise,
  relativeAlt,
}: OrbitArgs): void {
  if (!protocol?.orbit) return;
  const signedRadius = clockwise ? radius : -radius;
  protocol.orbit(signedRadius, 2, 2, menuPos.lat, menuPos.lon, relativeAlt ?? 20);
}
