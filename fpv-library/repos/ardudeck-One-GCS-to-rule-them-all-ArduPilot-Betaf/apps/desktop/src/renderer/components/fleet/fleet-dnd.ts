/**
 * Shared drag-and-drop plumbing for building fleets by dragging vehicles between
 * fleet groups (used by the FleetStrip rail and the Sim World fleet picker).
 * Dropping a vehicle on a fleet adds it there; dropping on the free/unassigned zone
 * peels it out. The engine sync lives in useFormationControl (addToFleet / removeFromFleet).
 */

import type { DragEvent } from 'react';

const MIME = 'application/x-ardudeck-vehicle-key';

/** The sentinel drop-zone id for "not in any fleet". */
export const FREE_ZONE = '__free__';

export function startVehicleDrag(e: DragEvent, vehicleKey: string): void {
  e.dataTransfer.setData(MIME, vehicleKey);
  e.dataTransfer.setData('text/plain', vehicleKey);
  e.dataTransfer.effectAllowed = 'move';
}

/** Read the dragged vehicle key. Only reliable inside onDrop, not onDragOver. */
export function readVehicleDrag(e: DragEvent): string | null {
  return e.dataTransfer.getData(MIME) || null;
}

/** Allow a drop on this zone (must be called in onDragOver to enable onDrop). */
export function allowVehicleDrop(e: DragEvent): void {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
}
