/**
 * Who the map's right-click commands are aimed at.
 *
 * Map commands route to the ACTIVE vehicle in the main process (activeFlightTarget).
 * The map still needs to know whether that active vehicle counts as "selected", because
 * the right-click popup only opens for a selected target.
 *
 * In single-vehicle mode selection is an explicit gesture: click the marker first. In
 * fleet mode the active vehicle IS the selection - it was chosen in the fleet strip or by
 * clicking its map marker, and those fleet markers are a separate layer that never sets
 * the map's local marker-selection flag.
 *
 * This must NOT be "there is no primary connection". The first drone of a swarm is the
 * primary link, so that test reported false for every real fleet: clicking a fleet marker
 * left the map with no selection, and right-click was silently dead until the operator
 * happened to also click the big primary marker.
 */
export function isFleetCommandTarget(
  activeVehicleKey: string | null,
  knownVehicleCount: number,
  primaryConnected: boolean,
): boolean {
  if (activeVehicleKey === null) return false;
  // More than one known vehicle => multi-vehicle mode regardless of the primary link.
  // A lone keyed vehicle with no primary link is also fleet-driven (orchestrator only).
  return knownVehicleCount > 1 || !primaryConnected;
}
