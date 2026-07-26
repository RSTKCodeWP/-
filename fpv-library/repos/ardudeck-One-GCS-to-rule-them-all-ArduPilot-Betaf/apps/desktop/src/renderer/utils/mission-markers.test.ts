import { describe, it, expect } from 'vitest';
import { MAV_CMD, type MissionItem } from '../../shared/mission-types';
import { splitMissionMarkers, isKeyCommand, SEMANTIC_MARKER_THRESHOLD } from './mission-markers';

// Minimal MissionItem factory - only the fields the classifier reads matter.
function wp(seq: number, command: number = MAV_CMD.NAV_WAYPOINT): MissionItem {
  return { seq, command, latitude: 1 + seq * 1e-4, longitude: 2 + seq * 1e-4 } as MissionItem;
}

describe('isKeyCommand', () => {
  it('treats launch/landing/loiter/ROI as key', () => {
    expect(isKeyCommand(MAV_CMD.NAV_TAKEOFF)).toBe(true);
    expect(isKeyCommand(MAV_CMD.NAV_LAND)).toBe(true);
    expect(isKeyCommand(MAV_CMD.NAV_RETURN_TO_LAUNCH)).toBe(true);
    expect(isKeyCommand(MAV_CMD.NAV_LOITER_TIME)).toBe(true);
    expect(isKeyCommand(MAV_CMD.DO_SET_ROI_LOCATION)).toBe(true);
  });

  it('treats plain nav waypoints as NOT key (they are the bulk)', () => {
    expect(isKeyCommand(MAV_CMD.NAV_WAYPOINT)).toBe(false);
    expect(isKeyCommand(MAV_CMD.NAV_SPLINE_WAYPOINT)).toBe(false);
  });
});

describe('splitMissionMarkers', () => {
  it('keeps every waypoint as a pin for small missions', () => {
    const items = Array.from({ length: 10 }, (_, i) => wp(i));
    const split = splitMissionMarkers(items, null);
    expect(split.semantic).toBe(false);
    expect(split.pins).toHaveLength(10);
    expect(split.bulk).toHaveLength(0);
    expect(split.pins.every((p) => p.role === 'key')).toBe(true);
  });

  it('collapses a large all-plain mission to just start + end', () => {
    const n = SEMANTIC_MARKER_THRESHOLD + 500;
    const items = Array.from({ length: n }, (_, i) => wp(i));
    const split = splitMissionMarkers(items, null);
    expect(split.semantic).toBe(true);
    expect(split.pins.map((p) => p.role).sort()).toEqual(['end', 'start']);
    expect(split.bulk).toHaveLength(n - 2);
  });

  it('promotes key commands and the live target inside a large mission', () => {
    const items = Array.from({ length: SEMANTIC_MARKER_THRESHOLD + 100 }, (_, i) => wp(i));
    items[0] = wp(0, MAV_CMD.NAV_TAKEOFF);
    items[50] = wp(50, MAV_CMD.NAV_LOITER_TIME);
    const last = items.length - 1;
    items[last] = wp(last, MAV_CMD.NAV_LAND);
    const currentSeq = 70;

    const split = splitMissionMarkers(items, currentSeq);
    const bySeq = new Map(split.pins.map((p) => [p.wp.seq, p.role]));

    // Takeoff/loiter/land are key commands - their own glyph, not START/END.
    expect(bySeq.get(0)).toBe('key');
    expect(bySeq.get(50)).toBe('key');
    expect(bySeq.get(last)).toBe('key');
    // The live target wins over a plain waypoint.
    expect(bySeq.get(70)).toBe('current');
    // No plain endpoints remain to label as start/end here.
    expect([...bySeq.values()]).not.toContain('start');
  });

  it('current target takes precedence over a key command on the same item', () => {
    const items = Array.from({ length: SEMANTIC_MARKER_THRESHOLD + 1 }, (_, i) => wp(i));
    items[10] = wp(10, MAV_CMD.NAV_LOITER_TIME);
    const split = splitMissionMarkers(items, 10);
    expect(split.pins.find((p) => p.wp.seq === 10)?.role).toBe('current');
  });
});
