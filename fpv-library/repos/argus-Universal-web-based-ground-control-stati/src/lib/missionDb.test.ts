import { describe, it, expect, beforeEach } from 'vitest';
import { saveMission, loadMission, listMissions, deleteMission, updateMissionName } from './missionDb';
import 'fake-indexeddb/auto';

const sampleData = () => ({
  waypoints: [{ lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp' as const, loiter_param: 0 }],
  fence: [
    { lat: 30, lon: 120 },
    { lat: 30.1, lon: 120.1 },
    { lat: 30.05, lon: 120.05 },
  ],
  rally: [{ lat: 30, lon: 120, alt: 100 }],
  defaultAlt: 50,
});

describe('missionDb', () => {
  beforeEach(async () => {
    const list = await listMissions();
    for (const m of list) await deleteMission(m.id);
  });

  it('saveMission returns an id', async () => {
    const id = await saveMission('Test Mission', sampleData());
    expect(id).toBeTruthy();
    expect(typeof id).toBe('string');
  });

  it('loadMission retrieves saved data', async () => {
    const id = await saveMission('My Mission', sampleData());
    const loaded = await loadMission(id);
    expect(loaded).not.toBeNull();
    expect(loaded!.name).toBe('My Mission');
    expect(loaded!.waypoints).toHaveLength(1);
    expect(loaded!.waypoints[0].lat).toBe(30);
    expect(loaded!.fence).toHaveLength(3);
    expect(loaded!.rally).toHaveLength(1);
    expect(loaded!.defaultAlt).toBe(50);
    expect(loaded!.createdAt).toBeGreaterThan(0);
  });

  it('loadMission returns null for unknown id', async () => {
    const result = await loadMission('nonexistent');
    expect(result).toBeNull();
  });

  it('listMissions returns all saved missions', async () => {
    await saveMission('First', sampleData());
    await saveMission('Second', sampleData());
    const list = await listMissions();
    expect(list).toHaveLength(2);
    const names = list.map((m) => m.name);
    expect(names).toContain('First');
    expect(names).toContain('Second');
  });

  it('deleteMission removes a mission', async () => {
    const id = await saveMission('ToDelete', sampleData());
    await deleteMission(id);
    const loaded = await loadMission(id);
    expect(loaded).toBeNull();
  });

  it('updateMissionName changes the name', async () => {
    const id = await saveMission('OldName', sampleData());
    await updateMissionName(id, 'NewName');
    const loaded = await loadMission(id);
    expect(loaded!.name).toBe('NewName');
  });

  it('updateMissionName is noop for unknown id', async () => {
    await updateMissionName('unknown', 'whatever');
    const list = await listMissions();
    expect(list).toHaveLength(0);
  });

  it('saveMission preserves waypoint fields', async () => {
    const data = sampleData();
    data.waypoints[0].drop = true;
    data.waypoints[0].speed = 8;
    const id = await saveMission('Detailed', data);
    const loaded = await loadMission(id);
    expect(loaded!.waypoints[0].drop).toBe(true);
    expect(loaded!.waypoints[0].speed).toBe(8);
  });
});
