/**
 * Pure geometry edit operations for the Area Editor polygon surface.
 * Renderer-agnostic: no React, no DOM, no map library imports.
 *
 * A "ring" is LatLng[] representing polygon vertices in order, NOT closed
 * (the edge from last vertex back to first is implicit).
 */

import type { LatLng } from './survey-types';
import { distanceLatLng, latLngToLocal, localToLatLng } from './geo-math';

// ---------------------------------------------------------------------------
// snapPoint
// ---------------------------------------------------------------------------

/**
 * Returns the target nearest to `p` (by haversine distance) if that distance
 * is <= `toleranceM`, otherwise null. Empty targets -> null.
 */
export function snapPoint(p: LatLng, targets: LatLng[], toleranceM: number): LatLng | null {
  if (targets.length === 0) return null;

  let bestDist = Infinity;
  let bestTarget: LatLng | null = null;

  for (const t of targets) {
    const d = distanceLatLng(p, t);
    if (d < bestDist) {
      bestDist = d;
      bestTarget = t;
    }
  }

  return bestDist <= toleranceM ? bestTarget : null;
}

// ---------------------------------------------------------------------------
// Internal: point-to-segment distance in 2D local space
// ---------------------------------------------------------------------------

function pointToSegmentDist2D(
  px: number,
  py: number,
  ax: number,
  ay: number,
  bx: number,
  by: number,
): number {
  const dx = bx - ax;
  const dy = by - ay;
  const lenSq = dx * dx + dy * dy;

  if (lenSq === 0) {
    // Degenerate segment (a === b): distance to the point
    const ex = px - ax;
    const ey = py - ay;
    return Math.sqrt(ex * ex + ey * ey);
  }

  // Project p onto the line a->b, clamped to [0, 1]
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lenSq));
  const cx = ax + t * dx;
  const cy = ay + t * dy;
  const ex = px - cx;
  const ey = py - cy;
  return Math.sqrt(ex * ex + ey * ey);
}

// ---------------------------------------------------------------------------
// nearestEdgeIndex
// ---------------------------------------------------------------------------

/**
 * Returns the index `i` such that the edge from ring[i] to ring[(i+1) % n]
 * is closest to `p`. Distance is measured in the local projected plane
 * (meters) using `p` as the projection origin.
 *
 * Returns -1 if ring has fewer than 2 vertices.
 */
export function nearestEdgeIndex(ring: LatLng[], p: LatLng): number {
  const n = ring.length;
  if (n < 2) return -1;

  // Project everything into local meter space with `p` as origin
  const localP = { x: 0, y: 0 }; // p projected onto itself is always (0,0)

  let bestIdx = 0;
  let bestDist = Infinity;

  for (let i = 0; i < n; i++) {
    const a = ring[i];
    const b = ring[(i + 1) % n];

    // Guard: noUncheckedIndexedAccess means these may be undefined in theory
    // but the length check above guarantees valid indices for 0..n-1
    if (a === undefined || b === undefined) continue;

    const la = latLngToLocal(p, a);
    const lb = latLngToLocal(p, b);

    const d = pointToSegmentDist2D(localP.x, localP.y, la.x, la.y, lb.x, lb.y);
    if (d < bestDist) {
      bestDist = d;
      bestIdx = i;
    }
  }

  return bestIdx;
}

// ---------------------------------------------------------------------------
// insertVertexOnEdge
// ---------------------------------------------------------------------------

/**
 * Inserts `p` immediately after the start vertex of the nearest edge
 * (between ring[i] and ring[i+1]). Returns a NEW array and the index
 * at which `p` was inserted.
 *
 * If ring has fewer than 2 vertices, appends `p` at the end.
 */
export function insertVertexOnEdge(
  ring: LatLng[],
  p: LatLng,
): { ring: LatLng[]; index: number } {
  if (ring.length < 2) {
    return { ring: [...ring, p], index: ring.length };
  }

  const i = nearestEdgeIndex(ring, p);
  // Insert after index i (between ring[i] and ring[i+1])
  const insertAt = i + 1;
  const newRing = [...ring.slice(0, insertAt), p, ...ring.slice(insertAt)];
  return { ring: newRing, index: insertAt };
}

// ---------------------------------------------------------------------------
// nudgeVertex
// ---------------------------------------------------------------------------

/**
 * Returns a NEW ring with ring[index] moved by (+dLat, +dLng).
 * If index is out of range, returns a copy unchanged.
 */
export function nudgeVertex(
  ring: LatLng[],
  index: number,
  dLat: number,
  dLng: number,
): LatLng[] {
  if (index < 0 || index >= ring.length) {
    return [...ring];
  }

  return ring.map((v, i) => {
    if (i === index) {
      return { lat: v.lat + dLat, lng: v.lng + dLng };
    }
    return { ...v };
  });
}

// ---------------------------------------------------------------------------
// removeVertexSafe
// ---------------------------------------------------------------------------

/**
 * Returns a NEW ring with the vertex at `index` removed, UNLESS removing
 * would drop the count below `minVertices`, in which case returns a copy
 * unchanged. Out-of-range index -> copy unchanged.
 */
export function removeVertexSafe(
  ring: LatLng[],
  index: number,
  minVertices = 3,
): LatLng[] {
  if (index < 0 || index >= ring.length) {
    return [...ring];
  }

  if (ring.length - 1 < minVertices) {
    return [...ring];
  }

  return [...ring.slice(0, index), ...ring.slice(index + 1)];
}

// ---------------------------------------------------------------------------
// pointInRing
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// splitPolygon
// ---------------------------------------------------------------------------

/**
 * Splits a polygon ring into two rings along the chord between vertex aIndex
 * and vertex bIndex (walking forward in ring order, wrapping at the end).
 *
 * Ring 1: vertices from aIndex to bIndex inclusive (walking forward/wrapping).
 * Ring 2: vertices from bIndex to aIndex inclusive (walking forward/wrapping).
 * Both rings share the two chord endpoints.
 *
 * Returns null if:
 *   - ring.length < 4
 *   - either index is out of range
 *   - indices are equal
 *   - indices are adjacent (either directly or wrap-around), which would
 *     produce a degenerate ring with fewer than 3 vertices
 *
 * Non-mutating.
 *
 * Example: [A, B, C, D] split at 0 and 2 -> [[A, B, C], [C, D, A]]
 *
 * Note: polygon boolean union (mergePolygons) is intentionally deferred -
 * it requires a full Sutherland-Hodgman / Greiner-Hormann clipping algorithm.
 */
export function splitPolygon(
  ring: LatLng[],
  aIndex: number,
  bIndex: number,
): [LatLng[], LatLng[]] | null {
  const n = ring.length;

  if (n < 4) return null;
  if (aIndex < 0 || aIndex >= n || bIndex < 0 || bIndex >= n) return null;
  if (aIndex === bIndex) return null;

  // Check adjacency (wrapping): the chord skips zero intermediate vertices in
  // at least one direction if the indices are neighbours mod n.
  const forward = (bIndex - aIndex + n) % n;
  const backward = (aIndex - bIndex + n) % n;
  if (forward === 1 || backward === 1) return null;

  // Build ring1: walk from aIndex to bIndex inclusive (forward, wrapping).
  const ring1: LatLng[] = [];
  for (let steps = 0; steps <= forward; steps++) {
    const v = ring[(aIndex + steps) % n];
    if (v === undefined) return null;
    ring1.push({ ...v });
  }

  // Build ring2: walk from bIndex to aIndex inclusive (forward, wrapping).
  const ring2: LatLng[] = [];
  for (let steps = 0; steps <= backward; steps++) {
    const v = ring[(bIndex + steps) % n];
    if (v === undefined) return null;
    ring2.push({ ...v });
  }

  if (ring1.length < 3 || ring2.length < 3) return null;

  return [ring1, ring2];
}

// ---------------------------------------------------------------------------
// ringSignedAreaLocal
// ---------------------------------------------------------------------------

/**
 * Computes the signed area of a ring projected into a local meters plane,
 * using the ring's first vertex as the projection origin and the shoelace
 * formula.
 *
 * Convention (standard math/GIS coords with y = north):
 *   Positive  -> counter-clockwise (CCW) winding
 *   Negative  -> clockwise (CW) winding
 *
 * Returns 0 for rings with fewer than 3 vertices.
 */
export function ringSignedAreaLocal(ring: LatLng[]): number {
  const n = ring.length;
  if (n < 3) return 0;

  const origin = ring[0]!;
  const local = ring.map(v => latLngToLocal(origin, v));

  let area = 0;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const a = local[i]!;
    const b = local[j]!;
    area += a.x * b.y - b.x * a.y;
  }
  return area / 2;
}

// ---------------------------------------------------------------------------
// ensureWinding
// ---------------------------------------------------------------------------

/**
 * Returns the ring reversed if its current winding does not match the
 * requested direction (`clockwise`), otherwise returns a copy with the same
 * order. Non-mutating - always returns a new array.
 *
 * Winding is determined by ringSignedAreaLocal:
 *   positive signed area  -> CCW  (clockwise = false)
 *   negative signed area  -> CW   (clockwise = true)
 *
 * Useful so outer rings and holes can be given consistent orientation before
 * writing GeoJSON or running scan-line algorithms.
 */
export function ensureWinding(ring: LatLng[], clockwise: boolean): LatLng[] {
  const area = ringSignedAreaLocal(ring);
  // area > 0 -> CCW, area <= 0 -> CW (or degenerate)
  const isCW = area < 0;

  if (isCW === clockwise) {
    // Already the right winding - return a shallow copy
    return ring.map(v => ({ ...v }));
  }

  // Flip winding
  return [...ring].reverse().map(v => ({ ...v }));
}

// ---------------------------------------------------------------------------
// pointInRing
// ---------------------------------------------------------------------------

/**
 * Ray-casting point-in-polygon test in lat/lng space (lat = y, lng = x).
 * Points exactly on the boundary may return either true or false; the
 * implementation does not guarantee a specific result for boundary cases.
 *
 * Returns false for rings with fewer than 3 vertices.
 */
export function pointInRing(p: LatLng, ring: LatLng[]): boolean {
  const n = ring.length;
  if (n < 3) return false;

  const px = p.lng;
  const py = p.lat;
  let inside = false;

  for (let i = 0, j = n - 1; i < n; j = i++) {
    const vi = ring[i];
    const vj = ring[j];

    // noUncheckedIndexedAccess guard - indices are valid within 0..n-1
    if (vi === undefined || vj === undefined) continue;

    const xi = vi.lng;
    const yi = vi.lat;
    const xj = vj.lng;
    const yj = vj.lat;

    // Standard ray-cast: does the horizontal ray from p cross this edge?
    const crosses =
      yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi;

    if (crosses) inside = !inside;
  }

  return inside;
}

// ---------------------------------------------------------------------------
// corridorSwath
// ---------------------------------------------------------------------------

/**
 * Build a closed polygon approximating the ground a corridor survey covers: the
 * `centerline` buffered by `widthM/2` on each side. Used purely as a live editor
 * PREVIEW of coverage width — the real per-strip flight lines are produced later
 * by the corridor generator using the mission's camera/overlap config.
 *
 * Returns vertices (not closed; caller closes for rendering). Uses a per-vertex
 * averaged-normal (miter) offset in a local tangent plane; corner offsets are
 * approximate, which is fine for a preview. Empty for < 2 points or width <= 0.
 */
export function corridorSwath(centerline: LatLng[], widthM: number): LatLng[] {
  if (centerline.length < 2 || widthM <= 0) return [];
  const origin = centerline[0]!;
  const pts = centerline.map((p) => latLngToLocal(origin, p));
  const half = widthM / 2;

  const left: { x: number; y: number }[] = [];
  const right: { x: number; y: number }[] = [];

  for (let i = 0; i < pts.length; i++) {
    const cur = pts[i]!;
    const prev = pts[i - 1];
    const next = pts[i + 1];

    let dx = 0;
    let dy = 0;
    if (prev) {
      const ix = cur.x - prev.x;
      const iy = cur.y - prev.y;
      const l = Math.hypot(ix, iy) || 1;
      dx += ix / l;
      dy += iy / l;
    }
    if (next) {
      const ox = next.x - cur.x;
      const oy = next.y - cur.y;
      const l = Math.hypot(ox, oy) || 1;
      dx += ox / l;
      dy += oy / l;
    }
    const dl = Math.hypot(dx, dy) || 1;
    dx /= dl;
    dy /= dl;

    // Left-hand normal of the tangent direction (dx, dy).
    const nx = -dy;
    const ny = dx;
    left.push({ x: cur.x + nx * half, y: cur.y + ny * half });
    right.push({ x: cur.x - nx * half, y: cur.y - ny * half });
  }

  const ring = [...left, ...right.reverse()];
  return ring.map((q) => localToLatLng(origin, q.x, q.y));
}

// ---------------------------------------------------------------------------
// Shape primitives (rectangle / circle)
// ---------------------------------------------------------------------------

/**
 * Axis-aligned (lat/lng) rectangle ring from two opposite corners `a` and `c`.
 * Returns 4 vertices, open (the closing edge is implicit). Degenerate corners
 * (same lat or same lng) still return 4 points; callers can reject zero-area.
 */
export function rectangleRing(a: LatLng, c: LatLng): LatLng[] {
  return [
    { lat: a.lat, lng: a.lng },
    { lat: a.lat, lng: c.lng },
    { lat: c.lat, lng: c.lng },
    { lat: c.lat, lng: a.lng },
  ];
}

/**
 * Polygon approximation of a circle of `radiusM` meters around `center`.
 * `segments` vertices evenly spaced; returns open ring. Radius <= 0 or
 * segments < 3 yields [].
 */
export function circleRing(center: LatLng, radiusM: number, segments = 48): LatLng[] {
  if (radiusM <= 0 || segments < 3) return [];
  const ring: LatLng[] = [];
  for (let i = 0; i < segments; i++) {
    const ang = (2 * Math.PI * i) / segments;
    const x = radiusM * Math.cos(ang);
    const y = radiusM * Math.sin(ang);
    ring.push(localToLatLng(center, x, y));
  }
  return ring;
}

/** Total length (meters) of an open polyline. < 2 points -> 0. */
export function polylineLength(points: LatLng[]): number {
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1];
    const b = points[i];
    if (a && b) total += distanceLatLng(a, b);
  }
  return total;
}
