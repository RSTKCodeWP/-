import { describe, it, expect, beforeEach } from 'vitest';
import { useMissionStore } from './mission-store';
import type { MissionItem, MavFrame } from '../../shared/mission-types';
import { MAV_CMD, MAV_FRAME } from '../../shared/mission-types';
import {
  planTerrainSafeAltitudes,
  type PlannerWaypoint,
  type TerrainLookup,
} from '../components/mission/terrain-altitude-planner';

/**
 * Flight-safety regression guard for issue #106.
 *
 * The catastrophic failure mode is a mismatch between a waypoint's altitude
 * VALUE and its FRAME: e.g. an absolute ~1150m value left tagged
 * GLOBAL_RELATIVE_ALT, which the FC would fly as 1150m ABOVE HOME. These tests
 * drive the real planner -> applyTerrainPlan path and assert every emitted
 * waypoint carries an altitude that matches its frame, and that the terrain
 * auto-adjust and survey terrain-follow (ASL) mechanisms never corrupt each
 * other's altitudes.
 */

function item(seq: number, lat: number, frame: MavFrame, altitude: number): MissionItem {
  return {
    seq,
    frame,
    command: MAV_CMD.NAV_WAYPOINT,
    current: false,
    autocontinue: true,
    param1: 0,
    param2: 0,
    param3: 0,
    param4: 0,
    latitude: lat,
    longitude: 0,
    altitude,
  };
}

// Ground elevation by latitude (ASL m): home flats at 1000, a 1080 hill, a 1100 plateau.
const groundByLat: Record<string, number> = { '0': 1000, '0.01': 1080, '0.02': 1100 };
const terrain: TerrainLookup = {
  elevationAt: (lat) => groundByLat[String(Math.round(lat * 100) / 100)] ?? 1000,
};

const HOME_ELEV = 1000;

describe('applyTerrainPlan - altitude/frame consistency (issue #106 safety)', () => {
  beforeEach(() => {
    useMissionStore.getState().reset();
  });

  it('keeps each raised waypoint in its own frame and never emits an ASL value in a relative frame', () => {
    const items = [
      item(0, 0, MAV_FRAME.GLOBAL_RELATIVE_ALT, 50), // 50m over 1000 ground = clears
      item(1, 0.01, MAV_FRAME.GLOBAL_RELATIVE_ALT, 10), // 10m over a 1080 hill = must raise
      item(2, 0.02, MAV_FRAME.GLOBAL, 1150), // ASL terrain-follow style, 50m AGL = clears
    ];
    useMissionStore.setState({ missionItems: items });

    const planner: PlannerWaypoint[] = [
      { seq: 0, latitude: 0, longitude: 0, altitude: 50, frame: 'relative' },
      { seq: 1, latitude: 0.01, longitude: 0, altitude: 10, frame: 'relative' },
      { seq: 2, latitude: 0.02, longitude: 0, altitude: 1150, frame: 'asl' },
    ];
    const plan = planTerrainSafeAltitudes(planner, terrain, {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: false,
      homeElevationMeters: HOME_ELEV,
    });

    useMissionStore.getState().applyTerrainPlan(plan);
    const out = useMissionStore.getState().missionItems;

    // Relative waypoint that already clears: untouched.
    expect(out[0]!.frame).toBe(MAV_FRAME.GLOBAL_RELATIVE_ALT);
    expect(out[0]!.altitude).toBe(50);

    // Relative waypoint over the hill: raised to 30m AGL => 1110 ASL => 110 relative
    // to a 1000m home. The killer assertion: it stays a RELATIVE-magnitude value,
    // NOT the ~1110 ASL value the old code wrote into a relative frame.
    expect(out[1]!.frame).toBe(MAV_FRAME.GLOBAL_RELATIVE_ALT);
    expect(out[1]!.altitude).toBe(110);
    expect(out[1]!.altitude).toBeLessThan(500); // never an absolute altitude in a relative frame

    // ASL terrain-follow waypoint already clearing terrain: value and frame intact
    // (the two mechanisms do not interfere).
    expect(out[2]!.frame).toBe(MAV_FRAME.GLOBAL);
    expect(out[2]!.altitude).toBe(1150);
  });

  it('emits inserted waypoints in the segment frame with a matching altitude value', () => {
    // Two relative-100m waypoints straddling a 1080m hill at 1000m ground; the
    // straight path clips the hill, so an intermediate waypoint is inserted.
    const ridge: TerrainLookup = {
      elevationAt: (lat) => (Math.abs(lat - 0.005) < 0.003 ? 1080 : 1000),
    };
    const items = [
      item(0, 0, MAV_FRAME.GLOBAL_RELATIVE_ALT, 40),
      item(1, 0.01, MAV_FRAME.GLOBAL_RELATIVE_ALT, 40),
    ];
    useMissionStore.setState({ missionItems: items });

    const planner: PlannerWaypoint[] = [
      { seq: 0, latitude: 0, longitude: 0, altitude: 40, frame: 'relative' },
      { seq: 1, latitude: 0.01, longitude: 0, altitude: 40, frame: 'relative' },
    ];
    const plan = planTerrainSafeAltitudes(planner, ridge, {
      safeBuffer: 30,
      raiseEndpoints: true,
      insertIntermediates: true,
      homeElevationMeters: HOME_ELEV,
    });
    expect(plan.inserts.length).toBeGreaterThan(0);

    useMissionStore.getState().applyTerrainPlan(plan);
    const out = useMissionStore.getState().missionItems;

    // Every emitted waypoint that is relative-framed must carry a relative-magnitude
    // altitude - no absolute values smuggled into a relative frame.
    for (const wp of out) {
      if (wp.frame === MAV_FRAME.GLOBAL_RELATIVE_ALT) {
        expect(wp.altitude).toBeLessThan(500);
      }
    }
    // The inserted waypoint (more than the original 2) is relative and clears the
    // 1080 hill by the buffer: 1110 ASL => 110 relative to 1000m home.
    expect(out.length).toBeGreaterThan(2);
    const inserted = out.find((wp) => wp.altitude > 40 && wp.frame === MAV_FRAME.GLOBAL_RELATIVE_ALT);
    expect(inserted).toBeDefined();
    expect(inserted!.altitude).toBeGreaterThanOrEqual(100);
    expect(inserted!.altitude).toBeLessThan(200);
  });
});
