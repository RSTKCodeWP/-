/**
 * Telemetry routing helpers.
 *
 * In a fleet the main process emits one TELEMETRY_BATCH per vehicle. The flat
 * legacy telemetry store (which the map, HUD, etc. follow) must reflect exactly
 * ONE vehicle, otherwise every vehicle's position overwrites it in round-robin
 * and the map auto-follow flies to each in turn (an endless "looping over the
 * fleet" effect).
 *
 * This decides whether a given batch should update that shared store:
 *  - The legacy single-connection key (`__primary__`) always wins.
 *  - Otherwise the store locks onto the explicitly active vehicle if there is
 *    one, else the first vehicle we ever saw telemetry from. Crucially it never
 *    falls back to "accept everything" when no vehicle is active, which is what
 *    caused the looping.
 */

export const PRIMARY_VEHICLE_KEY = '__primary__';

export function shouldMirrorToSharedStore(
  vehicleKey: string,
  activeVehicleKey: string | null,
  firstSeenVehicleKey: string | null,
): boolean {
  if (vehicleKey === PRIMARY_VEHICLE_KEY) return true;
  const lockedKey = activeVehicleKey ?? firstSeenVehicleKey;
  // Before we've seen any keyed vehicle, accept (single-vehicle startup).
  if (lockedKey === null) return true;
  return vehicleKey === lockedKey;
}
