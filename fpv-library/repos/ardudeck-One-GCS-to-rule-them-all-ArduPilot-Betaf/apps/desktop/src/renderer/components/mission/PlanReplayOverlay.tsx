/**
 * Animated replay of a survey group's planning pipeline on the mission map.
 *
 * Driven by replay-store (start/stop trigger) + plan-replay.ts (pure timeline).
 * Renders the TOPAS-style decomposition cells appearing one by one, the visit
 * order as numbered badges + centroid route lines, the per-cell coverage
 * tracks, then traces the group's actual mission waypoints before everything
 * fades out. All layers are non-interactive - this is presentation only, the
 * normal overlays underneath keep handling clicks.
 */
import { useEffect, useMemo, useState } from 'react';
import { Marker, Polygon, Polyline } from 'react-leaflet';
import L from 'leaflet';
import { useMissionStore } from '../../stores/mission-store';
import { useReplayStore } from '../../stores/replay-store';
import { isSurveyGroup } from '../../../shared/mission-group-types';
import {
  commandHasLocation,
  hasValidCoordinates,
  isNavigationCommand,
} from '../../../shared/mission-types';
import { cellColor, computeReplayFrame, parseReplayData } from './plan-replay';

// Tick at 100ms - stage steps are 200-300ms so this is smooth enough without
// paying rAF-rate React re-renders for a full-map overlay.
const TICK_MS = 100;

function badgeIcon(n: number): L.DivIcon {
  return L.divIcon({
    className: '',
    html: `<div class="flex items-center justify-center w-5 h-5 rounded-full bg-zinc-900/90 border border-white/70 text-[10px] font-semibold text-white">${n}</div>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });
}

export function PlanReplayOverlay() {
  const groupId = useReplayStore((s) => s.groupId);
  const startSeq = useReplayStore((s) => s.startSeq);
  const stopReplay = useReplayStore((s) => s.stopReplay);
  const groups = useMissionStore((s) => s.groups);
  const missionItems = useMissionStore((s) => s.missionItems);

  const group = groupId ? groups.find((g) => g.id === groupId) : undefined;
  const data = useMemo(
    () => (group && isSurveyGroup(group) ? parseReplayData(group.generatorResult) : null),
    [group],
  );

  // The final "path" stage traces the group's real mission waypoints.
  const path = useMemo(() => {
    if (!groupId) return [];
    return missionItems
      .filter(
        (it) =>
          it.groupId === groupId &&
          isNavigationCommand(it.command) &&
          commandHasLocation(it.command) &&
          hasValidCoordinates(it.latitude, it.longitude),
      )
      .map((it) => [it.latitude, it.longitude] as [number, number]);
  }, [missionItems, groupId]);

  const [elapsed, setElapsed] = useState(0);

  // Key on a boolean, not `data` identity: an unrelated mission edit can
  // recreate the group object (and thus re-parse), which must not restart
  // the clock mid-replay.
  const hasData = data !== null;
  useEffect(() => {
    if (!groupId || !hasData) return;
    setElapsed(0);
    const started = performance.now();
    const id = window.setInterval(() => setElapsed(performance.now() - started), TICK_MS);
    return () => window.clearInterval(id);
  }, [groupId, startSeq, hasData]);

  const frame = data ? computeReplayFrame(elapsed, data) : null;

  // Stop when the timeline completes, or when the group vanished / its
  // generatorResult stopped validating mid-replay (group deleted, regenerated
  // with bad data, ...). Also stop on unmount so a map teardown doesn't leave
  // a phantom "replaying" state behind.
  const shouldStop = groupId !== null && (data === null || frame?.finished === true);
  useEffect(() => {
    if (shouldStop) stopReplay();
  }, [shouldStop, stopReplay]);
  useEffect(() => () => useReplayStore.getState().stopReplay(), []);

  if (!data || !frame || frame.finished) return null;

  const fade = frame.fadeOpacity;
  // Same flat-array shape as PersistentSurveyOverlay (react-leaflet 4.x can
  // miss layer registration for layers nested in Fragments).
  const layers: React.ReactNode[] = [];

  // Stage 1: decomposition cells, in cells-array order.
  for (let i = 0; i < frame.visibleCells; i++) {
    const cell = data.cells[i];
    if (!cell) break;
    const color = cellColor(cell.index);
    layers.push(
      <Polygon
        key={`replay-cell-${i}`}
        positions={cell.polygon.map((p) => [p.lat, p.lng] as [number, number])}
        interactive={false}
        pathOptions={{
          color,
          weight: 2,
          opacity: 0.9 * fade,
          fillColor: color,
          fillOpacity: 0.28 * fade,
        }}
      />,
    );
  }

  // Stage 2: route lines between consecutive visited centroids, then badges
  // on top.
  for (let k = 0; k < frame.visibleConnections; k++) {
    const from = data.cells[data.order[k]!];
    const to = data.cells[data.order[k + 1]!];
    if (!from || !to) break;
    layers.push(
      <Polyline
        key={`replay-conn-${k}`}
        positions={[
          [from.centroid.lat, from.centroid.lng],
          [to.centroid.lat, to.centroid.lng],
        ]}
        interactive={false}
        pathOptions={{ color: '#ffffff', weight: 2, opacity: 0.9 * fade, dashArray: '6, 4' }}
      />,
    );
  }
  for (let k = 0; k < frame.visibleBadges; k++) {
    const cell = data.cells[data.order[k]!];
    if (!cell) break;
    layers.push(
      <Marker
        key={`replay-badge-${k}`}
        position={[cell.centroid.lat, cell.centroid.lng]}
        icon={badgeIcon(k + 1)}
        interactive={false}
        opacity={fade}
        zIndexOffset={2000}
      />,
    );
  }

  // Stage 3: coverage tracks, batched per visited cell, tinted like the cell.
  for (let k = 0; k < frame.visibleTrackCells; k++) {
    const cell = data.cells[data.order[k]!];
    if (!cell) break;
    cell.tracks.forEach((seg, si) => {
      layers.push(
        <Polyline
          key={`replay-track-${k}-${si}`}
          positions={[
            [seg[0].lat, seg[0].lng],
            [seg[1].lat, seg[1].lng],
          ]}
          interactive={false}
          pathOptions={{ color: cellColor(cell.index), weight: 1.5, opacity: 0.85 * fade }}
        />,
      );
    });
  }

  // Stage 4: trace the actual mission path as a growing waypoint prefix.
  if (frame.pathFraction > 0 && path.length >= 2) {
    const count = Math.max(2, Math.ceil(frame.pathFraction * path.length));
    layers.push(
      <Polyline
        key="replay-path"
        positions={path.slice(0, count)}
        interactive={false}
        pathOptions={{ color: '#22d3ee', weight: 3, opacity: fade }}
      />,
    );
  }

  if (layers.length === 0) return null;
  return <>{layers}</>;
}
