/**
 * Persistent overlay for completed survey groups.
 *
 * Renders visible SurveyGroup polygons from mission-store on the map. Click a
 * polygon to select its group (drives selection coupling with the waypoint
 * table); double-click to load it back into the survey draft for editing. The
 * selected group's polygon is drawn with a thicker stroke and brighter fill.
 *
 * The in-progress drawing overlay lives in SurveyMapOverlay; this one shows
 * after a survey has been inserted. The group currently being edited and any
 * hidden (unchecked) groups are skipped.
 *
 * Spec: docs/superpowers/specs/2026-05-28-mission-groups-design.md
 */
import { useMemo } from 'react';
import { Polygon, Polyline } from 'react-leaflet';
import { useMissionStore } from '../../stores/mission-store';
import { useSurveyStore } from '../../stores/survey-store';
import { isSurveyGroup, type SurveyGroup } from '../../../shared/mission-group-types';
import { extractGeneratorOverlays } from './generator-overlays';

export function PersistentSurveyOverlay() {
  const groups = useMissionStore((s) => s.groups);
  const selectedGroupId = useMissionStore((s) => s.selectedGroupId);
  const setSelectedGroupId = useMissionStore((s) => s.setSelectedGroupId);
  // The group currently being edited is drawn by SurveyMapOverlay (the live
  // draft); skip it here so its polygon + WPs aren't rendered twice.
  const editingGroupId = useSurveyStore((s) => s.editingGroupId);
  const loadFromGroup = useSurveyStore((s) => s.loadFromGroup);

  const surveyGroups = useMemo<SurveyGroup[]>(
    () => groups.filter(isSurveyGroup).filter((g) => g.visible && g.id !== editingGroupId),
    [groups, editingGroupId],
  );

  // Returning an array of layers (rather than wrapping in Fragments) avoids a
  // react-leaflet 4.x quirk where a Layer component inside a Fragment can
  // miss its layer registration cycle on initial mount in some cases. The
  // map renders this in a list so this is the same final tree, just flatter.
  const layers: React.ReactNode[] = [];

  for (const g of surveyGroups) {
    const isCorridor = g.generatorId === 'builtin.corridor';
    // Corridors are an open centerline (2+ points); area patterns need a ring.
    if (g.polygon.length < (isCorridor ? 2 : 3)) continue;
    const isSelected = g.id === selectedGroupId;
    const positions = g.polygon.map((p) => [p.lat, p.lng] as [number, number]);

    // Corridor: draw the centerline as a dashed open polyline (white casing +
    // group color), no fill — it's a path, not an area.
    if (isCorridor) {
      layers.push(
        <Polyline
          key={`corr-case-${g.id}`}
          positions={positions}
          pane={isSelected ? 'markerPane' : undefined}
          interactive={false}
          pathOptions={{ color: '#ffffff', weight: isSelected ? 7 : 5, opacity: 0.85 }}
        />,
      );
      layers.push(
        <Polyline
          key={`corr-${g.id}`}
          positions={positions}
          pane={isSelected ? 'markerPane' : undefined}
          pathOptions={{ color: g.color, weight: isSelected ? 4 : 3, dashArray: '10, 6' }}
          eventHandlers={{
            click: (e) => {
              e.originalEvent.stopPropagation();
              setSelectedGroupId(g.id);
              loadFromGroup({ id: g.id, polygon: g.polygon, config: g.config });
            },
          }}
        />,
      );
      // Branch centerlines forked off the corridor — same dashed casing as the main one.
      const branches = (g.config as { corridorBranches?: Array<Array<{ lat: number; lng: number }>> }).corridorBranches ?? [];
      branches.forEach((br, bi) => {
        if (br.length < 2) return;
        const brPos = br.map((p) => [p.lat, p.lng] as [number, number]);
        layers.push(
          <Polyline
            key={`corr-br-case-${g.id}-${bi}`}
            positions={brPos}
            pane={isSelected ? 'markerPane' : undefined}
            interactive={false}
            pathOptions={{ color: '#ffffff', weight: isSelected ? 7 : 5, opacity: 0.85 }}
          />,
        );
        layers.push(
          <Polyline
            key={`corr-br-${g.id}-${bi}`}
            positions={brPos}
            pane={isSelected ? 'markerPane' : undefined}
            pathOptions={{ color: g.color, weight: isSelected ? 4 : 3, dashArray: '10, 6' }}
            eventHandlers={{
              click: (e) => {
                e.originalEvent.stopPropagation();
                setSelectedGroupId(g.id);
                loadFromGroup({ id: g.id, polygon: g.polygon, config: g.config });
              },
            }}
          />,
        );
      });
      continue;
    }

    const holePositions =
      g.holes?.map((ring) =>
        ring.map((p) => [p.lat, p.lng] as [number, number]),
      ) ?? [];
    const polygonPositions =
      holePositions.length > 0 ? [positions, ...holePositions] : positions;

    // White casing under the colored outline so the boundary stands out
    // against the blue survey grid (the flight lines are sky-blue, and a
    // group's own colour can sit close to it).
    layers.push(
      <Polygon
        key={`poly-case-${g.id}`}
        positions={polygonPositions}
        pane={isSelected ? 'markerPane' : undefined}
        interactive={false}
        pathOptions={{
          color: '#ffffff',
          weight: isSelected ? 7 : 5,
          opacity: 0.85,
          fill: false,
        }}
      />,
    );
    layers.push(
      <Polygon
        key={`poly-${g.id}`}
        positions={polygonPositions}
        // Selected survey draws on top of the waypoint markers so the boundary
        // is actually visible (and grabbable) when WPs cover it.
        pane={isSelected ? 'markerPane' : undefined}
        pathOptions={{
          color: g.color,
          weight: isSelected ? 4 : 3,
          fillColor: g.color,
          fillOpacity: isSelected ? 0.22 : 0.1,
        }}
        eventHandlers={{
          // Single click loads the survey into the panel for editing (and
          // selects it). The labeled "Edit" button in the waypoint list does
          // the same - either way there's an obvious, discoverable path; no
          // hidden double-click required. stopPropagation so this click isn't
          // also seen as an "empty map" click that would exit edit mode.
          click: (e) => {
            e.originalEvent.stopPropagation();
            setSelectedGroupId(g.id);
            loadFromGroup({ id: g.id, polygon: g.polygon, config: g.config });
          },
        }}
      />,
    );

    // Workspace polygon (allowed flight area) rendered as a dashed outline
    // outside the ROI. Only present for generators that declare
    // `supportsWorkspace`. Built-ins do not; TOPAS module would.
    if (g.workspace && g.workspace.length >= 3) {
      const workspaceClosed: [number, number][] = [
        ...g.workspace.map((p) => [p.lat, p.lng] as [number, number]),
        [g.workspace[0]!.lat, g.workspace[0]!.lng],
      ];
      layers.push(
        <Polyline
          key={`ws-${g.id}`}
          positions={workspaceClosed}
          pathOptions={{
            color: g.color,
            weight: 1.5,
            opacity: 0.6,
            dashArray: '10, 6',
          }}
        />,
      );
    }

    // Generator-contributed decorations (e.g. TOPAS decomposition cells).
    // Non-interactive so they never steal clicks from the group polygon.
    extractGeneratorOverlays(g.generatorResult).forEach((ov, oi) => {
      const points = ov.points.map((p) => [p.lat, p.lng] as [number, number]);
      const pathOptions = {
        color: ov.color ?? g.color,
        weight: 1,
        opacity: 0.55,
        ...(ov.dashed ? { dashArray: '4, 4' } : {}),
      };
      layers.push(
        ov.type === 'polygon' ? (
          <Polygon
            key={`gen-ov-${g.id}-${oi}`}
            positions={points}
            interactive={false}
            pathOptions={{ ...pathOptions, fillColor: ov.color ?? g.color, fillOpacity: 0.14 }}
          />
        ) : (
          <Polyline
            key={`gen-ov-${g.id}-${oi}`}
            positions={points}
            interactive={false}
            pathOptions={pathOptions}
          />
        ),
      );
    });
  }

  if (layers.length === 0) return null;
  return <>{layers}</>;
}
