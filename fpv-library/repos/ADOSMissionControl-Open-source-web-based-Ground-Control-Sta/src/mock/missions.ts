import type { Mission, Waypoint } from "@/lib/types";
import { randomId } from "@/lib/utils";
import { FLIGHT_PATHS } from "./flight-paths";

function pathToWaypoints(pathIndex: number): Waypoint[] {
  const path = FLIGHT_PATHS[pathIndex];
  if (!path) return [];
  return path.map((wp, i) => ({
    id: randomId(),
    lat: wp.lat,
    lon: wp.lon,
    alt: wp.alt,
    speed: wp.speed,
    command: i === 0 ? "TAKEOFF" as const : "WAYPOINT" as const,
  }));
}

export interface MockMission {
  droneId: string;
  mission: Mission;
}

export const MOCK_ACTIVE_MISSIONS: MockMission[] = [
  {
    droneId: "alpha-1",
    mission: {
      id: "msn-alpha",
      name: "Sector A Perimeter",
      droneId: "alpha-1",
      templateName: "perimeter_patrol",
      waypoints: pathToWaypoints(0),
      state: "running",
      progress: 42,
      currentWaypoint: 3,
      estimatedTime: 1800,
      estimatedDistance: 4200,
      startedAt: Date.now() - 12 * 60 * 1000,
    },
  },
  {
    droneId: "bravo-2",
    mission: {
      id: "msn-bravo",
      name: "Grid Survey Alpha",
      droneId: "bravo-2",
      templateName: "photogrammetry_grid",
      waypoints: pathToWaypoints(1),
      state: "running",
      progress: 28,
      currentWaypoint: 3,
      estimatedTime: 2400,
      estimatedDistance: 6800,
      startedAt: Date.now() - 8 * 60 * 1000,
    },
  },
];

export function getMockMission(droneId: string): Mission | null {
  const match = MOCK_ACTIVE_MISSIONS.find((m) => m.droneId === droneId);
  return match?.mission ?? null;
}
