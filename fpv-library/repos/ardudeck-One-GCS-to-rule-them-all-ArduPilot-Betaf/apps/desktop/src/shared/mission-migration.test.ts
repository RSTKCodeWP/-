import { describe, it, expect } from 'vitest';
import { migrateStoredMission, migrateSavePayload } from './mission-migration';
import { MAV_CMD, MAV_FRAME } from './mission-types';
import type { MissionItem } from './mission-types';
import { MISSION_FILE_VERSION } from './mission-library-types';
import { createManualGroup } from './mission-group-types';

function wp(seq: number, partial: Partial<MissionItem> = {}): MissionItem {
  return {
    seq,
    frame: MAV_FRAME.GLOBAL_RELATIVE_ALT,
    command: MAV_CMD.NAV_WAYPOINT,
    current: false,
    autocontinue: true,
    param1: 0,
    param2: 0,
    param3: 0,
    param4: 0,
    latitude: 1,
    longitude: 2,
    altitude: 100,
    ...partial,
  };
}

describe('migrateStoredMission', () => {
  it('returns null for garbage', () => {
    expect(migrateStoredMission(null)).toBeNull();
    expect(migrateStoredMission(undefined)).toBeNull();
    expect(migrateStoredMission(42)).toBeNull();
    expect(migrateStoredMission({ items: 'not-an-array' })).toBeNull();
    expect(migrateStoredMission({})).toBeNull();
  });

  it('wraps v1 (no groups) in a single Manual group', () => {
    const raw = {
      id: 'm1',
      name: 'Test',
      description: '',
      vehicleProfileId: null,
      tags: [],
      waypointCount: 2,
      totalDistanceMeters: 0,
      boundingBox: null,
      flightCount: 0,
      lastFlightStatus: null,
      createdAt: '2026-05-01T00:00:00Z',
      updatedAt: '2026-05-01T00:00:00Z',
      items: [wp(0), wp(1)],
      homePosition: null,
    };
    const out = migrateStoredMission(raw)!;
    expect(out).not.toBeNull();
    expect(out.version).toBe(MISSION_FILE_VERSION);
    expect(out.groups).toHaveLength(1);
    expect(out.groups[0]!.kind).toBe('manual');
    expect(out.groups[0]!.name).toBe('Manual');
    expect(out.items).toHaveLength(2);
    for (const it of out.items) {
      expect(it.groupId).toBe(out.groups[0]!.id);
    }
  });

  it('preserves a v2 file with groups intact', () => {
    const manual = createManualGroup({ name: 'Existing' });
    const raw = {
      id: 'm2',
      name: 'Test',
      description: '',
      vehicleProfileId: null,
      tags: [],
      waypointCount: 1,
      totalDistanceMeters: 0,
      boundingBox: null,
      flightCount: 0,
      lastFlightStatus: null,
      createdAt: '2026-05-01T00:00:00Z',
      updatedAt: '2026-05-01T00:00:00Z',
      version: MISSION_FILE_VERSION,
      groups: [manual],
      items: [wp(0, { groupId: manual.id })],
      homePosition: null,
    };
    const out = migrateStoredMission(raw)!;
    expect(out.groups).toHaveLength(1);
    expect(out.groups[0]!.id).toBe(manual.id);
    expect(out.groups[0]!.name).toBe('Existing');
    expect(out.items[0]!.groupId).toBe(manual.id);
  });

  it('backfills missing groupId on a v2 file (hand-edited resilience)', () => {
    const manual = createManualGroup({ name: 'A' });
    const raw = {
      id: 'm3',
      name: 'Test',
      description: '',
      vehicleProfileId: null,
      tags: [],
      waypointCount: 2,
      totalDistanceMeters: 0,
      boundingBox: null,
      flightCount: 0,
      lastFlightStatus: null,
      createdAt: '2026-05-01T00:00:00Z',
      updatedAt: '2026-05-01T00:00:00Z',
      version: MISSION_FILE_VERSION,
      groups: [manual],
      // Second item missing groupId.
      items: [wp(0, { groupId: manual.id }), wp(1)],
      homePosition: null,
    };
    const out = migrateStoredMission(raw)!;
    expect(out.items[0]!.groupId).toBe(manual.id);
    expect(out.items[1]!.groupId).toBe(manual.id);
  });

  it('is idempotent', () => {
    const raw = {
      id: 'm4',
      name: 'Test',
      description: '',
      vehicleProfileId: null,
      tags: [],
      waypointCount: 1,
      totalDistanceMeters: 0,
      boundingBox: null,
      flightCount: 0,
      lastFlightStatus: null,
      createdAt: '2026-05-01T00:00:00Z',
      updatedAt: '2026-05-01T00:00:00Z',
      items: [wp(0)],
      homePosition: null,
    };
    const once = migrateStoredMission(raw)!;
    const twice = migrateStoredMission(once)!;
    expect(twice.groups).toHaveLength(1);
    expect(twice.groups[0]!.id).toBe(once.groups[0]!.id);
    expect(twice.items[0]!.groupId).toBe(once.groups[0]!.id);
  });

  it('handles an empty item list', () => {
    const raw = {
      id: 'm5',
      name: 'Empty',
      description: '',
      vehicleProfileId: null,
      tags: [],
      waypointCount: 0,
      totalDistanceMeters: 0,
      boundingBox: null,
      flightCount: 0,
      lastFlightStatus: null,
      createdAt: '2026-05-01T00:00:00Z',
      updatedAt: '2026-05-01T00:00:00Z',
      items: [],
      homePosition: null,
    };
    const out = migrateStoredMission(raw)!;
    expect(out.groups).toHaveLength(1);
    expect(out.items).toHaveLength(0);
  });
});

describe('migrateSavePayload', () => {
  it('wraps a legacy payload with no groups in a single Manual group', () => {
    const out = migrateSavePayload({
      name: 'X',
      description: '',
      vehicleProfileId: null,
      tags: [],
      items: [wp(0), wp(1)],
      homePosition: null,
    });
    expect(out.groups).toHaveLength(1);
    expect(out.groups[0]!.kind).toBe('manual');
    expect(out.items[0]!.groupId).toBe(out.groups[0]!.id);
    expect(out.items[1]!.groupId).toBe(out.groups[0]!.id);
  });

  it('passes through a payload that already has groups', () => {
    const manual = createManualGroup({ name: 'Saved' });
    const out = migrateSavePayload({
      name: 'X',
      description: '',
      vehicleProfileId: null,
      tags: [],
      groups: [manual],
      items: [wp(0, { groupId: manual.id })],
      homePosition: null,
    });
    expect(out.groups).toHaveLength(1);
    expect(out.groups[0]!.id).toBe(manual.id);
    expect(out.items[0]!.groupId).toBe(manual.id);
  });

  it('backfills missing groupId on supplied items using first available group', () => {
    const manual = createManualGroup({ name: 'A' });
    const out = migrateSavePayload({
      name: 'X',
      description: '',
      vehicleProfileId: null,
      tags: [],
      groups: [manual],
      items: [wp(0)], // missing groupId
      homePosition: null,
    });
    expect(out.items[0]!.groupId).toBe(manual.id);
  });
});
