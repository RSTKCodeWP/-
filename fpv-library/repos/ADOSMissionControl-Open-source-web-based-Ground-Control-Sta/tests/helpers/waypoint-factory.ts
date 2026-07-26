import type { Waypoint, WaypointCommand } from '@/lib/types/mission';

let _id = 0;

export function makeWaypoint(overrides?: Partial<Waypoint>): Waypoint {
  _id++;
  return {
    id: `wp-${_id}`,
    lat: 12.9716 + (_id * 0.001),
    lon: 77.5946 + (_id * 0.001),
    alt: 50,
    ...overrides,
  };
}

export function makeMission(count: number, overrides?: Partial<Waypoint>): Waypoint[] {
  return Array.from({ length: count }, (_, i) =>
    makeWaypoint({
      command: i === 0 ? 'TAKEOFF' : i === count - 1 ? 'LAND' : 'WAYPOINT',
      ...overrides,
    })
  );
}

export function resetWaypointIds(): void {
  _id = 0;
}
