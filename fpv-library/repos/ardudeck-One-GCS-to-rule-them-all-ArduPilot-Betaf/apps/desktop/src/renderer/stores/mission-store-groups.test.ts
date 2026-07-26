import { describe, it, expect, beforeEach } from 'vitest';
import { useMissionStore } from './mission-store';
import { createSurveyGroup } from '../../shared/mission-group-types';
import type { MissionItem } from '../../shared/mission-types';
import { MAV_CMD, MAV_FRAME, computeGroupWaypointNumbers } from '../../shared/mission-types';

function wp(seq: number): MissionItem {
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
    latitude: 51.5,
    longitude: -0.1,
    altitude: 50,
  };
}

describe('mission-store groups', () => {
  beforeEach(() => {
    useMissionStore.getState().reset();
  });

  it('addSurveyGroup preserves polygon on the stored group', () => {
    const polygon = [
      { lat: 51.5, lng: -0.1 },
      { lat: 51.51, lng: -0.1 },
      { lat: 51.51, lng: -0.09 },
      { lat: 51.5, lng: -0.09 },
    ];
    const survey = createSurveyGroup({
      name: 'Test',
      generatorId: 'builtin.grid',
      generatorVersion: '1.0.0',
      polygon,
      config: { altitude: 50 },
    });
    useMissionStore.getState().addSurveyGroup(survey, [wp(0), wp(1), wp(2)]);

    const stored = useMissionStore.getState().groups.find((g) => g.id === survey.id);
    expect(stored).toBeTruthy();
    expect(stored!.kind).toBe('survey');
    if (stored!.kind !== 'survey') throw new Error();
    expect(stored!.polygon).toHaveLength(4);
    expect(stored!.polygon[0]!.lat).toBe(51.5);
    expect(stored!.polygon[0]!.lng).toBe(-0.1);
  });

  it('addSurveyGroup stamps every item with the new group id', () => {
    const polygon = [
      { lat: 0, lng: 0 },
      { lat: 1, lng: 0 },
      { lat: 1, lng: 1 },
    ];
    const survey = createSurveyGroup({
      name: 'X',
      generatorId: 'builtin.grid',
      generatorVersion: '1.0.0',
      polygon,
      config: {},
    });
    useMissionStore.getState().addSurveyGroup(survey, [wp(0), wp(1)]);

    const items = useMissionStore.getState().missionItems;
    expect(items).toHaveLength(2);
    for (const it of items) {
      expect(it.groupId).toBe(survey.id);
    }
  });

  function makeSurvey(name: string) {
    return createSurveyGroup({
      name,
      generatorId: 'builtin.grid',
      generatorVersion: '1.0.0',
      polygon: [
        { lat: 0, lng: 0 },
        { lat: 1, lng: 0 },
        { lat: 1, lng: 1 },
      ],
      config: {},
    });
  }

  it('new groups default to visible', () => {
    const survey = makeSurvey('V');
    useMissionStore.getState().addSurveyGroup(survey, [wp(0)]);
    expect(useMissionStore.getState().groups.find((g) => g.id === survey.id)!.visible).toBe(true);
  });

  it('setGroupVisible toggles only the map-visibility flag', () => {
    const survey = makeSurvey('V');
    useMissionStore.getState().addSurveyGroup(survey, [wp(0)]);
    useMissionStore.getState().setGroupVisible(survey.id, false);
    expect(useMissionStore.getState().groups.find((g) => g.id === survey.id)!.visible).toBe(false);
  });

  it('getUploadItems flattens ALL groups regardless of visibility', () => {
    const a = makeSurvey('A');
    const b = makeSurvey('B');
    useMissionStore.getState().addSurveyGroup(a, [wp(0), wp(1)]);
    useMissionStore.getState().addSurveyGroup(b, [wp(0)]);
    // Hide B on the map — it must still be part of an upload.
    useMissionStore.getState().setGroupVisible(b.id, false);
    const items = useMissionStore.getState().getUploadItems();
    expect(items).toHaveLength(3);
    expect(items.map((it) => it.seq)).toEqual([0, 1, 2]); // contiguous renumber
  });

  it('numbers waypoints 1-based within each group', () => {
    const a = makeSurvey('A');
    const b = makeSurvey('B');
    useMissionStore.getState().addSurveyGroup(a, [wp(0), wp(1)]);
    useMissionStore.getState().addSurveyGroup(b, [wp(0), wp(1), wp(2)]);
    const items = useMissionStore.getState().missionItems;
    const nums = computeGroupWaypointNumbers(items);
    const aItems = items.filter((it) => it.groupId === a.id);
    const bItems = items.filter((it) => it.groupId === b.id);
    expect(aItems.map((it) => nums.get(it.seq))).toEqual([1, 2]);
    // Group B restarts at 1 rather than continuing the global count.
    expect(bItems.map((it) => nums.get(it.seq))).toEqual([1, 2, 3]);
  });

  it('getUploadItemsForGroup returns just that group, renumbered from 0', () => {
    const a = makeSurvey('A');
    const b = makeSurvey('B');
    useMissionStore.getState().addSurveyGroup(a, [wp(0), wp(1)]);
    useMissionStore.getState().addSurveyGroup(b, [wp(0), wp(1), wp(2)]);
    const items = useMissionStore.getState().getUploadItemsForGroup(b.id);
    expect(items).toHaveLength(3);
    expect(items.map((it) => it.seq)).toEqual([0, 1, 2]);
    expect(items.every((it) => it.groupId === b.id)).toBe(true);
  });

  it('undo removes the last added group; redo restores it', () => {
    const survey = makeSurvey('U');
    useMissionStore.getState().addSurveyGroup(survey, [wp(0), wp(1)]);
    expect(useMissionStore.getState().groups).toHaveLength(1);
    expect(useMissionStore.getState()._canUndo).toBe(true);

    useMissionStore.getState().undo();
    expect(useMissionStore.getState().groups).toHaveLength(0);
    expect(useMissionStore.getState().missionItems).toHaveLength(0);
    expect(useMissionStore.getState()._canRedo).toBe(true);

    useMissionStore.getState().redo();
    expect(useMissionStore.getState().groups).toHaveLength(1);
    expect(useMissionStore.getState().missionItems).toHaveLength(2);
  });

  it('self-heals waypoints with no groupId into a recovered group', () => {
    // Directly land orphaned items (no groupId, no groups) - the bug where the
    // table showed headerless "Fly here" rows numbered by global seq.
    useMissionStore.setState({ missionItems: [wp(0), wp(1), wp(2)], groups: [] });
    const s = useMissionStore.getState();
    expect(s.groups).toHaveLength(1);
    const gid = s.groups[0]!.id;
    expect(s.missionItems.every((it) => it.groupId === gid)).toBe(true);
    // Per-group numbering now resolves instead of falling back to global seq.
    const nums = computeGroupWaypointNumbers(s.missionItems);
    expect(nums.get(0)).toBe(1);
    expect(nums.get(2)).toBe(3);
  });

  it('self-heals items whose groupId points to a missing group', () => {
    useMissionStore.setState({ missionItems: [{ ...wp(0), groupId: 'ghost' }], groups: [] });
    const s = useMissionStore.getState();
    const gid = s.missionItems[0]!.groupId;
    expect(s.groups.some((g) => g.id === gid)).toBe(true);
  });

  it('addSurveyGroup keeps existing groups + items intact', () => {
    // Place a couple of manual WPs first by simulating a click.
    useMissionStore.getState().addWaypoint(51.5, -0.1, 50);
    useMissionStore.getState().addWaypoint(51.51, -0.1, 50);
    const itemsBefore = useMissionStore.getState().missionItems.length;
    const groupsBefore = useMissionStore.getState().groups.length;

    const survey = createSurveyGroup({
      name: 'X',
      generatorId: 'builtin.grid',
      generatorVersion: '1.0.0',
      polygon: [
        { lat: 0, lng: 0 },
        { lat: 1, lng: 0 },
        { lat: 1, lng: 1 },
      ],
      config: {},
    });
    useMissionStore.getState().addSurveyGroup(survey, [wp(0), wp(1), wp(2)]);

    const state = useMissionStore.getState();
    expect(state.groups).toHaveLength(groupsBefore + 1);
    expect(state.missionItems).toHaveLength(itemsBefore + 3);
    expect(state.groups.find((g) => g.id === survey.id)).toBeTruthy();
  });
});
