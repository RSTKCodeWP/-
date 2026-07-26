/**
 * objects-geo — pure GeoJSON builders for the object-based Area Editor renderer.
 *
 * Produces the FeatureCollections the map layers consume:
 *  - object fills/outlines (per-object color, selected emphasis, corridor swath)
 *  - the selected object's transform handles (bbox + scale corners/edges + rotate)
 *  - per-vertex handles (when the selected object is being vertex-edited)
 *  - the in-progress draft rubber-band
 *
 * No React, no map library. Handle features carry the local-frame data the
 * interaction layer needs to apply a transform, so the math lives in one place.
 */

import type { LatLng } from '../components/survey/survey-types';
import { corridorSwath } from '../components/survey/geo-edit';
import {
  objectWorldRing,
  objectWorldHoles,
  objectWorldBranches,
  objectLocalBBox,
  localToWorld,
  type EditorObject,
  type LocalPt,
} from './area-object';

/** Distinct, saturated per-object colors (cycled by list index). */
export const AREA_COLORS = [
  '#22d3ee', '#f59e0b', '#a78bfa', '#34d399',
  '#f472b6', '#60a5fa', '#fb7185', '#facc15',
];
export function colorForIndex(i: number): string {
  return AREA_COLORS[((i % AREA_COLORS.length) + AREA_COLORS.length) % AREA_COLORS.length]!;
}

function closeRing(coords: [number, number][]): [number, number][] {
  const first = coords[0];
  return first ? [...coords, [first[0], first[1]]] : coords;
}

function toCoord(p: LatLng): [number, number] {
  return [p.lng, p.lat];
}

// ---------------------------------------------------------------------------
// Object fills / outlines
// ---------------------------------------------------------------------------

export function buildObjectsData(objects: EditorObject[], selectedId: string | null): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];

  objects.forEach((obj, i) => {
    if (!obj.visible) return;
    // Geofences render green (inclusion) / red (exclusion), overriding the palette.
    const color =
      obj.fenceType === 'inclusion' ? '#22c55e'
        : obj.fenceType === 'exclusion' ? '#ef4444'
          : (obj.color ?? colorForIndex(i));
    const selected = obj.id === selectedId;
    const ring = objectWorldRing(obj);

    if (obj.type === 'corridor') {
      const width = obj.corridorWidthM ?? 60;
      // The main centerline plus any branches, each rendered as a swath + line.
      const centerlines = [ring, ...objectWorldBranches(obj)];
      for (const cl of centerlines) {
        if (cl.length < 2) continue;
        const swath = corridorSwath(cl, width);
        if (swath.length >= 3) {
          features.push({
            type: 'Feature',
            geometry: { type: 'Polygon', coordinates: [closeRing(swath.map(toCoord))] },
            properties: { id: obj.id, color, selected, corridor: true },
          });
        }
        features.push({
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: cl.map(toCoord) },
          properties: { id: obj.id, color, selected, corridor: true },
        });
      }
      return;
    }

    if (ring.length >= 3) {
      const rings: [number, number][][] = [closeRing(ring.map(toCoord))];
      for (const hole of objectWorldHoles(obj)) {
        if (hole.length >= 3) rings.push(closeRing(hole.map(toCoord)));
      }
      features.push({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: rings },
        properties: {
          id: obj.id,
          color,
          selected,
          ...(obj.fenceType ? { fenceType: obj.fenceType } : {}),
          // Workspace-role areas render as a dashed outline with barely-there fill.
          ...(obj.role === 'workspace' ? { workspace: true } : {}),
        },
      });
    }
  });

  return { type: 'FeatureCollection', features };
}

// ---------------------------------------------------------------------------
// Transform handles (selected object, select tool)
// ---------------------------------------------------------------------------

interface ScaleHandle {
  role: 'scale';
  /** Grabbed handle position in local coords. */
  hx: number; hy: number;
  /** Anchor (kept fixed) in local coords. */
  ax: number; ay: number;
  /** Which local axes this handle scales. */
  axis: 'xy' | 'x' | 'y';
}

/**
 * Selection box + 8 scale handles + 1 rotate handle for the selected object.
 * Corner handles scale both axes about the opposite corner; edge handles scale
 * one axis about the opposite edge midpoint. The rotate handle sits beyond the
 * top edge. All positions are mapped through the object's rotation/placement so
 * the box visually tracks a rotated shape.
 */
export function buildTransformHandles(obj: EditorObject): GeoJSON.FeatureCollection {
  const bb = objectLocalBBox(obj);
  const { minX, minY, maxX, maxY } = bb;
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const rotOffset = Math.max((maxY - minY) * 0.25, 12);

  const corners: ScaleHandle[] = [
    { role: 'scale', hx: minX, hy: minY, ax: maxX, ay: maxY, axis: 'xy' },
    { role: 'scale', hx: maxX, hy: minY, ax: minX, ay: maxY, axis: 'xy' },
    { role: 'scale', hx: maxX, hy: maxY, ax: minX, ay: minY, axis: 'xy' },
    { role: 'scale', hx: minX, hy: maxY, ax: maxX, ay: minY, axis: 'xy' },
  ];
  const edges: ScaleHandle[] = [
    { role: 'scale', hx: cx, hy: minY, ax: cx, ay: maxY, axis: 'y' },
    { role: 'scale', hx: maxX, hy: cy, ax: minX, ay: cy, axis: 'x' },
    { role: 'scale', hx: cx, hy: maxY, ax: cx, ay: minY, axis: 'y' },
    { role: 'scale', hx: minX, hy: cy, ax: maxX, ay: cy, axis: 'x' },
  ];

  const features: GeoJSON.Feature[] = [];

  // Selection box outline.
  const boxLocal: LocalPt[] = [
    { x: minX, y: minY }, { x: maxX, y: minY }, { x: maxX, y: maxY }, { x: minX, y: maxY }, { x: minX, y: minY },
  ];
  features.push({
    type: 'Feature',
    geometry: { type: 'LineString', coordinates: boxLocal.map((p) => toCoord(localToWorld(obj, p))) },
    properties: { role: 'bbox' },
  });

  for (const h of [...corners, ...edges]) {
    const w = localToWorld(obj, { x: h.hx, y: h.hy });
    features.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: toCoord(w) },
      properties: { role: 'scale', hx: h.hx, hy: h.hy, ax: h.ax, ay: h.ay, axis: h.axis },
    });
  }

  // Rotate handle, beyond the top edge, plus a stalk to the box.
  const rotLocal: LocalPt = { x: cx, y: maxY + rotOffset };
  const topMid: LocalPt = { x: cx, y: maxY };
  features.push({
    type: 'Feature',
    geometry: { type: 'LineString', coordinates: [toCoord(localToWorld(obj, topMid)), toCoord(localToWorld(obj, rotLocal))] },
    properties: { role: 'rotate-stalk' },
  });
  features.push({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: toCoord(localToWorld(obj, rotLocal)) },
    properties: { role: 'rotate' },
  });

  return { type: 'FeatureCollection', features };
}

// ---------------------------------------------------------------------------
// Vertex handles (selected vertex-editable object, edit tool)
// ---------------------------------------------------------------------------

export function buildVertexHandles(obj: EditorObject, selectedVertex: number | null): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  // Main centerline / ring vertices (branch -1, hole -1).
  objectWorldRing(obj).forEach((p, i) => {
    features.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: toCoord(p) },
      properties: { role: 'vertex', vertex: i, branch: -1, hole: -1, selected: i === selectedVertex },
    });
  });
  // Hole vertices, tagged with their hole index so edits route to the right ring.
  objectWorldHoles(obj).forEach((hole, hi) => {
    hole.forEach((p, i) => {
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: toCoord(p) },
        properties: { role: 'vertex', vertex: i, branch: -1, hole: hi, selected: false },
      });
    });
  });
  // Corridor branch vertices, tagged with their branch index so edits route to
  // the right centerline.
  objectWorldBranches(obj).forEach((br, bi) => {
    br.forEach((p, i) => {
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: toCoord(p) },
        properties: { role: 'vertex', vertex: i, branch: bi, hole: -1, selected: false },
      });
    });
  });
  return { type: 'FeatureCollection', features };
}

// ---------------------------------------------------------------------------
// Draft rubber-band (in-progress polygon/corridor)
// ---------------------------------------------------------------------------

export function buildDraftData(points: LatLng[], cursor?: LatLng | null): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  const line = cursor && points.length >= 1 ? [...points, cursor] : points;
  if (line.length >= 2) {
    features.push({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: line.map(toCoord) },
      properties: {},
    });
  }
  for (const p of points) {
    features.push({ type: 'Feature', geometry: { type: 'Point', coordinates: toCoord(p) }, properties: {} });
  }
  return { type: 'FeatureCollection', features };
}
