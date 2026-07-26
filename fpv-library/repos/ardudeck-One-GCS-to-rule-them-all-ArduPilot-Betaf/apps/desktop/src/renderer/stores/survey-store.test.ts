import { describe, it, expect, beforeEach } from 'vitest';
import { useSurveyStore } from './survey-store';
import { useMissionStore } from './mission-store';
import { isSurveyGroup } from '../../shared/mission-group-types';

/** Reset both stores before each test */
function resetStore() {
  useMissionStore.setState({ groups: [], missionItems: [], isDirty: false });
  useSurveyStore.setState({
    drawMode: 'none',
    drawingVertices: [],
    polygon: null,
    config: {
      pattern: 'grid',
      altitude: 80,
      speed: 5,
      frontOverlap: 75,
      sideOverlap: 60,
      camera: {
        name: 'DJI Mavic 3E',
        sensorWidth: 17.3,
        sensorHeight: 13,
        imageWidth: 5280,
        imageHeight: 3956,
        focalLength: 12.3,
      },
      gridAngle: 0,
      overshoot: 20,
      altitudeReference: 'relative',
    },
    result: null,
    showFootprints: false,
    isActive: false,
  });
}

describe('survey-store', () => {
  beforeEach(() => {
    resetStore();
  });

  describe('setAltitudeReference', () => {
    it('sets altitude reference to terrain', () => {
      useSurveyStore.getState().setAltitudeReference('terrain');
      expect(useSurveyStore.getState().config.altitudeReference).toBe('terrain');
    });

    it('sets altitude reference to asl', () => {
      useSurveyStore.getState().setAltitudeReference('asl');
      expect(useSurveyStore.getState().config.altitudeReference).toBe('asl');
    });

    it('sets altitude reference to relative', () => {
      useSurveyStore.getState().setAltitudeReference('terrain');
      useSurveyStore.getState().setAltitudeReference('relative');
      expect(useSurveyStore.getState().config.altitudeReference).toBe('relative');
    });

    it('does not clear polygon or result when changing reference', () => {
      // Set up a polygon first
      const polygon = [
        { lat: -35.36, lng: 149.16 },
        { lat: -35.37, lng: 149.16 },
        { lat: -35.37, lng: 149.17 },
        { lat: -35.36, lng: 149.17 },
      ];
      useSurveyStore.setState({ polygon });

      useSurveyStore.getState().setAltitudeReference('terrain');

      expect(useSurveyStore.getState().polygon).toEqual(polygon);
    });
  });

  describe('removeVertex', () => {
    const squarePolygon = [
      { lat: -35.36, lng: 149.16 },
      { lat: -35.37, lng: 149.16 },
      { lat: -35.37, lng: 149.17 },
      { lat: -35.36, lng: 149.17 },
    ];

    it('removes a vertex from a polygon with more than 3 vertices', () => {
      useSurveyStore.setState({ polygon: [...squarePolygon] });
      useSurveyStore.getState().removeVertex(1);
      const polygon = useSurveyStore.getState().polygon;
      expect(polygon).toHaveLength(3);
      // Vertex at index 1 should be gone
      expect(polygon).not.toContainEqual(squarePolygon[1]);
    });

    it('does not remove vertex when polygon has exactly 3 vertices', () => {
      const triangle = squarePolygon.slice(0, 3);
      useSurveyStore.setState({ polygon: [...triangle] });
      useSurveyStore.getState().removeVertex(0);
      expect(useSurveyStore.getState().polygon).toHaveLength(3);
    });

    it('does nothing when polygon is null', () => {
      useSurveyStore.setState({ polygon: null });
      useSurveyStore.getState().removeVertex(0);
      expect(useSurveyStore.getState().polygon).toBeNull();
    });

    it('removes the first vertex correctly', () => {
      useSurveyStore.setState({ polygon: [...squarePolygon] });
      useSurveyStore.getState().removeVertex(0);
      const polygon = useSurveyStore.getState().polygon;
      expect(polygon).toHaveLength(3);
      expect(polygon![0]).toEqual(squarePolygon[1]);
    });

    it('removes the last vertex correctly', () => {
      useSurveyStore.setState({ polygon: [...squarePolygon] });
      useSurveyStore.getState().removeVertex(3);
      const polygon = useSurveyStore.getState().polygon;
      expect(polygon).toHaveLength(3);
      expect(polygon![2]).toEqual(squarePolygon[2]);
    });
  });

  describe('setSideOverlap', () => {
    it('accepts side overlap up to 99%', () => {
      useSurveyStore.getState().setSideOverlap(99);
      expect(useSurveyStore.getState().config.sideOverlap).toBe(99);
    });

    it('accepts side overlap at 95%', () => {
      useSurveyStore.getState().setSideOverlap(95);
      expect(useSurveyStore.getState().config.sideOverlap).toBe(95);
    });

    it('accepts values above the old 80% limit', () => {
      for (const val of [81, 85, 90, 95, 99]) {
        useSurveyStore.getState().setSideOverlap(val);
        expect(useSurveyStore.getState().config.sideOverlap).toBe(val);
      }
    });
  });

  describe('updateVertex', () => {
    it('updates a vertex position', () => {
      const polygon = [
        { lat: -35.36, lng: 149.16 },
        { lat: -35.37, lng: 149.16 },
        { lat: -35.37, lng: 149.17 },
      ];
      useSurveyStore.setState({ polygon: [...polygon] });

      useSurveyStore.getState().updateVertex(1, -35.365, 149.162);
      const updated = useSurveyStore.getState().polygon;
      expect(updated![1]).toEqual({ lat: -35.365, lng: 149.162 });
    });

    it('does nothing when polygon is null', () => {
      useSurveyStore.setState({ polygon: null });
      useSurveyStore.getState().updateVertex(0, 0, 0);
      expect(useSurveyStore.getState().polygon).toBeNull();
    });
  });

  describe('addSurveyAreasFromPolygons', () => {
    // A real square polygon large enough that the grid generator produces waypoints.
    // Side ~1 km so the 80 m altitude / ~30 m line spacing yields meaningful rows.
    const square1 = [
      { lat: -35.360, lng: 149.160 },
      { lat: -35.370, lng: 149.160 },
      { lat: -35.370, lng: 149.170 },
      { lat: -35.360, lng: 149.170 },
    ];
    const square2 = [
      { lat: -35.380, lng: 149.160 },
      { lat: -35.390, lng: 149.160 },
      { lat: -35.390, lng: 149.170 },
      { lat: -35.380, lng: 149.170 },
    ];

    it('returns empty array when given no areas', async () => {
      const ids = await useSurveyStore.getState().addSurveyAreasFromPolygons([]);
      expect(ids).toEqual([]);
    });

    it('skips areas with fewer than 3 points', async () => {
      const ids = await useSurveyStore.getState().addSurveyAreasFromPolygons([
        { polygon: [{ lat: -35.36, lng: 149.16 }, { lat: -35.37, lng: 149.16 }] },
      ]);
      expect(ids).toEqual([]);
      expect(useMissionStore.getState().groups).toHaveLength(0);
    });

    it('adds two areas in one atomic call and returns two ids', async () => {
      const ids = await useSurveyStore.getState().addSurveyAreasFromPolygons([
        { polygon: square1 },
        { polygon: square2 },
      ]);
      expect(ids).toHaveLength(2);
      expect(ids[0]).toBeTruthy();
      expect(ids[1]).toBeTruthy();
      expect(ids[0]).not.toBe(ids[1]);

      const { groups } = useMissionStore.getState();
      expect(groups.filter(isSurveyGroup)).toHaveLength(2);
    });

    it('opens the first group in the survey panel', async () => {
      const ids = await useSurveyStore.getState().addSurveyAreasFromPolygons([
        { polygon: square1 },
        { polygon: square2 },
      ]);
      const surveyState = useSurveyStore.getState();
      expect(surveyState.isActive).toBe(true);
      expect(surveyState.editingGroupId).toBe(ids[0]);
    });

    it('respects custom names', async () => {
      const ids = await useSurveyStore.getState().addSurveyAreasFromPolygons([
        { polygon: square1, name: 'Zone A' },
        { polygon: square2, name: 'Zone B' },
      ]);
      expect(ids).toHaveLength(2);
      const { groups } = useMissionStore.getState();
      const surveyGroups = groups.filter(isSurveyGroup);
      expect(surveyGroups.some((g) => g.name === 'Zone A')).toBe(true);
      expect(surveyGroups.some((g) => g.name === 'Zone B')).toBe(true);
    });

    it('all items belong to their respective groups', async () => {
      const ids = await useSurveyStore.getState().addSurveyAreasFromPolygons([
        { polygon: square1 },
        { polygon: square2 },
      ]);
      const { missionItems } = useMissionStore.getState();
      const group0Items = missionItems.filter((it) => it.groupId === ids[0]);
      const group1Items = missionItems.filter((it) => it.groupId === ids[1]);
      expect(group0Items.length).toBeGreaterThan(0);
      expect(group1Items.length).toBeGreaterThan(0);
    });
  });
});
