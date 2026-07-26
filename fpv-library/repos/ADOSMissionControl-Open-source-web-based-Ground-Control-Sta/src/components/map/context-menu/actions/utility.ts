/**
 * @module map/context-menu/actions/utility
 * @description Utility action handlers: copy coordinates, copy distance and
 * bearing from the connected drone.
 * @license GPL-3.0-only
 */

import type { MenuPosition } from "../types";

export function handleCopyCoords(menuPos: MenuPosition): void {
  navigator.clipboard.writeText(`${menuPos.lat.toFixed(7)}, ${menuPos.lon.toFixed(7)}`);
}

interface MeasureArgs {
  distLabel: string;
  bearingDeg: number;
}

export function handleMeasureFromDrone({ distLabel, bearingDeg }: MeasureArgs): void {
  navigator.clipboard.writeText(`${distLabel} at ${Math.round(bearingDeg)}°`);
}
