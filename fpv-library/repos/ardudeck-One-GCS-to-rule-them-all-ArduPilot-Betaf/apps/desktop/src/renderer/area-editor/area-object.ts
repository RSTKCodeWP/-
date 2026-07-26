/**
 * area-object — the Area Editor's object model.
 *
 * Each drawn shape is a first-class OBJECT, not a loose ring. An object is
 * stored parametrically as a local base ring (meters, centered on the origin,
 * un-rotated) plus a world `center` and `rotationDeg`. World geometry is
 * derived on demand. This makes whole-object transforms exact and keeps
 * rectangles/circles parametric (scaling adjusts the base, so a rectangle stays
 * a rectangle) until the user explicitly converts to a free polygon.
 *
 * Renderer-agnostic and pure: no React, no map library, no DOM.
 */

import type { LatLng } from '../components/survey/survey-types';
import { latLngToLocal, localToLatLng, offsetPolygon } from '../components/survey/geo-math';

export type EditorObjectType = 'polygon' | 'corridor' | 'rectangle' | 'circle';

export interface LocalPt {
  x: number; // east, meters
  y: number; // north, meters
}

export interface EditorObject {
  id: string;
  type: EditorObjectType;
  name: string;
  visible: boolean;
  /** World placement of the local origin. */
  center: LatLng;
  /** Rotation of the base ring about the origin, degrees, CCW. */
  rotationDeg: number;
  /** Local-frame outer ring (meters, centered on origin, before rotation). Open. */
  base: LocalPt[];
  /** Local-frame holes (areas/polygons only). */
  holes: LocalPt[][];
  /** Corridor swath width (meters); only meaningful for type 'corridor'. */
  corridorWidthM?: number;
  /**
   * Corridor branches: additional local-frame centerlines that fork off `base`
   * (forked roads, power-line spurs). Same local frame as `base` (share center +
   * rotation), so whole-object transforms move them too. Only for type 'corridor'.
   */
  branches?: LocalPt[][];
  /** User-chosen fill/outline color; falls back to the index palette when unset. */
  color?: string;
  /**
   * When set, this object is a geofence of the given kind (inclusion keeps the
   * vehicle in; exclusion keeps it out). Drives green/red rendering and fence
   * upload. Only 'polygon'/'rectangle'/'circle' objects can be fences.
   */
  fenceType?: 'inclusion' | 'exclusion';
  /**
   * Commit role: 'workspace' marks this object as the allowed-flight-area whose
   * outer ring is attached to every committed survey area (for remote coverage
   * engines) instead of being surveyed itself. Undefined = 'area'. At most one
   * object holds the workspace role; only closed shapes can.
   */
  role?: 'area' | 'workspace';
}

// ---------------------------------------------------------------------------
// Local-frame math
// ---------------------------------------------------------------------------

function rot(p: LocalPt, deg: number): LocalPt {
  const a = (deg * Math.PI) / 180;
  const c = Math.cos(a);
  const s = Math.sin(a);
  return { x: p.x * c - p.y * s, y: p.x * s + p.y * c };
}

/** Centroid of a local ring (simple vertex average; fine for placement). */
function localCentroid(pts: LocalPt[]): LocalPt {
  if (pts.length === 0) return { x: 0, y: 0 };
  let sx = 0;
  let sy = 0;
  for (const p of pts) {
    sx += p.x;
    sy += p.y;
  }
  return { x: sx / pts.length, y: sy / pts.length };
}

// ---------------------------------------------------------------------------
// World <-> local
// ---------------------------------------------------------------------------

/** Map a local point through rotation + placement to a world LatLng. */
export function localToWorld(obj: EditorObject, p: LocalPt): LatLng {
  const r = rot(p, obj.rotationDeg);
  return localToLatLng(obj.center, r.x, r.y);
}

/** Inverse of localToWorld: a world LatLng back into the object's local frame. */
export function worldToLocal(obj: EditorObject, p: LatLng): LocalPt {
  const placed = latLngToLocal(obj.center, p); // relative to center, still rotated
  return rot(placed, -obj.rotationDeg); // un-rotate
}

/** The object's outer ring in world coordinates. */
export function objectWorldRing(obj: EditorObject): LatLng[] {
  return obj.base.map((p) => localToWorld(obj, p));
}

/** The object's holes in world coordinates. */
export function objectWorldHoles(obj: EditorObject): LatLng[][] {
  return obj.holes.map((h) => h.map((p) => localToWorld(obj, p)));
}

/** The corridor's branch centerlines in world coordinates (empty for non-corridors). */
export function objectWorldBranches(obj: EditorObject): LatLng[][] {
  return (obj.branches ?? []).map((b) => b.map((p) => localToWorld(obj, p)));
}

/**
 * Snap a point onto the nearest of several polylines (the main centerline plus
 * any branches), so a new branch can attach to the main line OR to another
 * branch - branches off branches.
 */
export function snapToNearestPolyline(pt: LocalPt, lines: LocalPt[][]): LocalPt {
  let best = pt;
  let bestD = Infinity;
  for (const line of lines) {
    if (line.length < 2) continue;
    const cand = snapToPolyline(pt, line);
    const d = (cand.x - pt.x) ** 2 + (cand.y - pt.y) ** 2;
    if (d < bestD) { bestD = d; best = cand; }
  }
  return best;
}

/**
 * Project a local point onto the nearest point of an open local polyline. Used
 * to snap a new branch's first vertex onto the corridor centerline so it visibly
 * attaches at a junction.
 */
export function snapToPolyline(pt: LocalPt, line: LocalPt[]): LocalPt {
  if (line.length < 2) return line[0] ?? pt;
  let best = line[0]!;
  let bestD = Infinity;
  for (let i = 0; i < line.length - 1; i++) {
    const a = line[i]!;
    const b = line[i + 1]!;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len2 = dx * dx + dy * dy;
    let t = len2 > 0 ? ((pt.x - a.x) * dx + (pt.y - a.y) * dy) / len2 : 0;
    t = Math.max(0, Math.min(1, t));
    const cx = a.x + t * dx;
    const cy = a.y + t * dy;
    const d = (pt.x - cx) ** 2 + (pt.y - cy) ** 2;
    if (d < bestD) { bestD = d; best = { x: cx, y: cy }; }
  }
  return best;
}

/** Axis-aligned bounding box of the base ring (local, un-rotated frame). */
export function objectLocalBBox(obj: EditorObject): { minX: number; minY: number; maxX: number; maxY: number } {
  if (obj.base.length === 0) return { minX: 0, minY: 0, maxX: 0, maxY: 0 };
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const p of obj.base) {
    if (p.x < minX) minX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.x > maxX) maxX = p.x;
    if (p.y > maxY) maxY = p.y;
  }
  return { minX, minY, maxX, maxY };
}

// ---------------------------------------------------------------------------
// Transforms (pure; return a new object)
// ---------------------------------------------------------------------------

/** Move the whole object by a world delta. */
export function translateObject(obj: EditorObject, dLat: number, dLng: number): EditorObject {
  return { ...obj, center: { lat: obj.center.lat + dLat, lng: obj.center.lng + dLng } };
}

/** Rotate the whole object by an incremental angle (degrees). */
export function rotateObject(obj: EditorObject, deltaDeg: number): EditorObject {
  return { ...obj, rotationDeg: obj.rotationDeg + deltaDeg };
}

/**
 * Scale the object's base about a fixed LOCAL anchor (kept invariant). Because
 * the anchor stays fixed in the local frame and center/rotation are unchanged,
 * the anchor's WORLD position is unchanged too — so dragging a corner handle
 * keeps the opposite corner pinned. sx/sy are clamped to a small positive min.
 */
export function scaleObjectAbout(obj: EditorObject, sx: number, sy: number, anchor: LocalPt): EditorObject {
  const cx = Math.max(sx, 0.001);
  const cy = Math.max(sy, 0.001);
  const map = (p: LocalPt): LocalPt => ({
    x: (p.x - anchor.x) * cx + anchor.x,
    y: (p.y - anchor.y) * cy + anchor.y,
  });
  return {
    ...obj,
    base: obj.base.map(map),
    holes: obj.holes.map((h) => h.map(map)),
    ...(obj.branches ? { branches: obj.branches.map((b) => b.map(map)) } : {}),
  };
}

// ---------------------------------------------------------------------------
// Constructors
// ---------------------------------------------------------------------------

function newId(): string {
  return crypto.randomUUID();
}

/** Rectangle of width×height meters, axis-aligned, centered at `center`. */
export function makeRectangle(center: LatLng, widthM: number, heightM: number, name: string): EditorObject {
  const hw = widthM / 2;
  const hh = heightM / 2;
  return {
    id: newId(),
    type: 'rectangle',
    name,
    visible: true,
    center,
    rotationDeg: 0,
    base: [
      { x: -hw, y: -hh },
      { x: hw, y: -hh },
      { x: hw, y: hh },
      { x: -hw, y: hh },
    ],
    holes: [],
  };
}

/** Circle (segments-gon) of radius meters, centered at `center`. */
export function makeCircle(center: LatLng, radiusM: number, name: string, segments = 48): EditorObject {
  const base: LocalPt[] = [];
  for (let i = 0; i < segments; i++) {
    const ang = (2 * Math.PI * i) / segments;
    base.push({ x: radiusM * Math.cos(ang), y: radiusM * Math.sin(ang) });
  }
  return { id: newId(), type: 'circle', name, visible: true, center, rotationDeg: 0, base, holes: [] };
}

/** Build an object from a world-space ring (its centroid becomes the center). */
export function makeFromWorldRing(
  type: EditorObjectType,
  ring: LatLng[],
  name: string,
  opts?: { holes?: LatLng[][]; corridorWidthM?: number; branches?: LatLng[][] },
): EditorObject {
  const centroid = ringCentroidWorld(ring);
  const base = ring.map((p) => latLngToLocal(centroid, p));
  const holes = (opts?.holes ?? []).map((h) => h.map((p) => latLngToLocal(centroid, p)));
  const obj: EditorObject = {
    id: newId(),
    type,
    name,
    visible: true,
    center: centroid,
    rotationDeg: 0,
    base,
    holes,
  };
  if (opts?.corridorWidthM !== undefined) obj.corridorWidthM = opts.corridorWidthM;
  if (opts?.branches && opts.branches.length > 0) {
    obj.branches = opts.branches.map((b) => b.map((p) => latLngToLocal(centroid, p)));
  }
  return obj;
}

/** World centroid of a ring (vertex average in local meters, mapped back). */
export function ringCentroidWorld(ring: LatLng[]): LatLng {
  if (ring.length === 0) return { lat: 0, lng: 0 };
  const origin = ring[0]!;
  const c = localCentroid(ring.map((p) => latLngToLocal(origin, p)));
  return localToLatLng(origin, c.x, c.y);
}

/**
 * Convert a parametric object to a free polygon: same geometry, but typed
 * 'polygon' so per-vertex editing is allowed.
 */
export function convertToPolygon(obj: EditorObject): EditorObject {
  return { ...obj, type: 'polygon' };
}

/** Deep-copy an object under a fresh id (for Duplicate). */
export function cloneObject(obj: EditorObject, name?: string): EditorObject {
  return {
    ...obj,
    id: newId(),
    name: name ?? obj.name,
    center: { ...obj.center },
    base: obj.base.map((p) => ({ ...p })),
    holes: obj.holes.map((h) => h.map((p) => ({ ...p }))),
    ...(obj.branches ? { branches: obj.branches.map((b) => b.map((p) => ({ ...p }))) } : {}),
  };
}

/** Whether per-vertex editing is allowed (parametric shapes are locked). */
export function isVertexEditable(obj: EditorObject): boolean {
  return obj.type === 'polygon' || obj.type === 'corridor';
}

// ---------------------------------------------------------------------------
// Commit payload (Send to mission)
// ---------------------------------------------------------------------------

/** One committed shape, as sent to the mission planner (preload's CommitArea). */
export interface CommitAreaPayload {
  polygon: LatLng[];
  holes?: LatLng[][];
  kind?: 'corridor';
  corridorWidth?: number;
  corridorBranches?: LatLng[][];
  config?: Record<string, unknown>;
  /** Allowed-flight-area outer ring, from the workspace-role object (if any). */
  workspace?: LatLng[];
}

/** Whether an object has enough visible geometry to be committed. */
export function isCommittable(obj: EditorObject): boolean {
  return obj.visible && objectWorldRing(obj).length >= (obj.type === 'corridor' ? 2 : 3);
}

/**
 * Build the "Send to mission" payload. The workspace-role object is not itself
 * a survey area: its outer ring rides along on every committed area as the
 * allowed flight area (holes on it are ignored - only the boundary matters to
 * coverage engines).
 */
export function buildCommitAreas(
  objects: EditorObject[],
  editorConfig: Record<string, unknown>,
): CommitAreaPayload[] {
  const valid = objects.filter(isCommittable);
  const wsObj = valid.find((o) => o.role === 'workspace' && o.type !== 'corridor');
  const workspace = wsObj ? objectWorldRing(wsObj) : undefined;
  return valid
    .filter((o) => o !== wsObj)
    .map((o) =>
      o.type === 'corridor'
        ? {
            polygon: objectWorldRing(o),
            kind: 'corridor' as const,
            corridorWidth: o.corridorWidthM ?? 60,
            ...(o.branches && o.branches.length > 0 ? { corridorBranches: objectWorldBranches(o) } : {}),
            config: editorConfig,
            ...(workspace ? { workspace } : {}),
          }
        : {
            polygon: objectWorldRing(o),
            holes: objectWorldHoles(o),
            config: editorConfig,
            ...(workspace ? { workspace } : {}),
          },
    );
}

// ---------------------------------------------------------------------------
// Buffer (offset) + Split — operate in the object's local meters frame
// ---------------------------------------------------------------------------

function signedArea2D(ring: LocalPt[]): number {
  let a = 0;
  for (let i = 0; i < ring.length; i++) {
    const p = ring[i]!;
    const q = ring[(i + 1) % ring.length]!;
    a += p.x * q.y - q.x * p.y;
  }
  return a / 2;
}

/**
 * Validate an offset ring: >=3 pts, same winding, real area, and the area moved
 * in the expected DIRECTION. The direction check is what catches an over-shrink
 * that the simple miter offset reflects into a same-winding *larger* polygon.
 */
function offsetOk(ring: LocalPt[], refArea: number, expandExpected: boolean): boolean {
  if (ring.length < 3) return false;
  const a = signedArea2D(ring);
  if (Math.sign(a) !== Math.sign(refArea) || Math.abs(a) < 1) return false;
  return expandExpected ? Math.abs(a) > Math.abs(refArea) : Math.abs(a) < Math.abs(refArea);
}

/**
 * Grow (meters > 0) or shrink (meters < 0) a closed area by a distance.
 * The outer ring offsets outward and holes offset inward (so a hole shrinks as
 * the area grows). Returns null for corridors or if the offset collapses.
 * offsetPolygon's positive distance SHRINKS, so we negate for the outer ring.
 */
export function bufferObject(obj: EditorObject, meters: number): EditorObject | null {
  if (obj.type === 'corridor' || obj.base.length < 3) return null;
  const outer = offsetPolygon(obj.base, -meters) as LocalPt[];
  if (!offsetOk(outer, signedArea2D(obj.base), meters > 0)) return null;
  const holes: LocalPt[][] = [];
  for (const h of obj.holes) {
    if (h.length < 3) continue;
    const oh = offsetPolygon(h, meters) as LocalPt[];
    // A hole grows when the area shrinks, and vice versa.
    if (offsetOk(oh, signedArea2D(h), meters < 0)) holes.push(oh);
  }
  return { ...obj, base: outer, holes };
}

function pointInRing(pt: LocalPt, ring: LocalPt[]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const pi = ring[i]!;
    const pj = ring[j]!;
    if (pi.y > pt.y !== pj.y > pt.y && pt.x < ((pj.x - pi.x) * (pt.y - pi.y)) / (pj.y - pi.y) + pi.x) {
      inside = !inside;
    }
  }
  return inside;
}

function centroid(ring: LocalPt[]): LocalPt {
  let x = 0;
  let y = 0;
  for (const p of ring) {
    x += p.x;
    y += p.y;
  }
  return { x: x / ring.length, y: y / ring.length };
}

/** Whether two finite segments properly cross. */
function segmentsCross(a: LocalPt, b: LocalPt, c: LocalPt, d: LocalPt): boolean {
  const rx = b.x - a.x; const ry = b.y - a.y;
  const sx = d.x - c.x; const sy = d.y - c.y;
  const denom = rx * sy - ry * sx;
  if (Math.abs(denom) < 1e-12) return false;
  const t = ((c.x - a.x) * sy - (c.y - a.y) * sx) / denom;
  const u = ((c.x - a.x) * ry - (c.y - a.y) * rx) / denom;
  return t >= 0 && t <= 1 && u >= 0 && u <= 1;
}

/** How many times a finite segment crosses a closed ring's edges. */
function segmentRingCrossings(a: LocalPt, b: LocalPt, ring: LocalPt[]): number {
  let n = 0;
  for (let k = 0; k < ring.length; k++) {
    if (segmentsCross(a, b, ring[k]!, ring[(k + 1) % ring.length]!)) n++;
  }
  return n;
}

/** Reverse a ring if needed so its signed area has the wanted sign (CCW = positive). */
function ensureWinding(ring: LocalPt[], wantPositive: boolean): LocalPt[] {
  const a = signedArea2D(ring);
  if (a === 0) return ring;
  return (a > 0) === wantPositive ? ring : [...ring].reverse();
}

/** One result polygon of a clip: an outer ring with its own holes (local frame). */
interface ClipPiece {
  outer: LocalPt[];
  holes: LocalPt[][];
}

/**
 * Clip a polygon-with-holes against a half-plane, keeping the side where
 * `keepSign * f >= 0` (f = signed distance from the directed line a->b).
 *
 * Holes the cut passes through are MERGED into the boundary rather than left as
 * separate rings, so slicing an annulus through its ring yields proper C-shaped
 * polygons (one ring each) instead of a hole that pokes across the new edge -
 * which is what produced the rendering artifact. Holes the cut misses stay as
 * holes on whichever side contains them.
 *
 * `outer` must be CCW and `holes` CW going in.
 */
function clipByHalfPlane(
  outer: LocalPt[],
  holes: LocalPt[][],
  a: LocalPt,
  b: LocalPt,
  keepSign: number,
): ClipPiece[] {
  const dir = { x: b.x - a.x, y: b.y - a.y };
  const f = (p: LocalPt): number => keepSign * (dir.x * (p.y - a.y) - dir.y * (p.x - a.x));
  const sParam = (p: LocalPt): number => (p.x - a.x) * dir.x + (p.y - a.y) * dir.y;
  const EPS = 1e-7;

  const cut = (pi: LocalPt, pj: LocalPt, fi: number, fj: number): LocalPt => {
    const t = fi / (fi - fj);
    return { x: pi.x + t * (pj.x - pi.x), y: pi.y + t * (pj.y - pi.y) };
  };

  const closedLoops: LocalPt[][] = []; // rings fully inside the kept half-plane
  const chains: { pts: LocalPt[]; sStart: number; sEnd: number }[] = [];

  for (const ring of [outer, ...holes]) {
    const m = ring.length;
    if (m < 3) continue;
    const fv = ring.map(f);
    if (fv.every((v) => v >= -EPS)) { closedLoops.push(ring); continue; }
    if (fv.every((v) => v < EPS)) continue;
    // Start at an outside vertex so each kept run opens/closes on the line cleanly.
    let start = 0;
    while (start < m && fv[start]! >= -EPS) start++;
    let curr: LocalPt[] | null = null;
    for (let step = 0; step < m; step++) {
      const i = (start + step) % m;
      const j = (start + step + 1) % m;
      const pi = ring[i]!; const pj = ring[j]!;
      const fi = fv[i]!; const fj = fv[j]!;
      const insI = fi >= -EPS; const insJ = fj >= -EPS;
      if (insI && insJ) {
        if (curr) curr.push(pj);
      } else if (insI && !insJ) {
        if (curr) {
          curr.push(cut(pi, pj, fi, fj));
          chains.push({ pts: curr, sStart: sParam(curr[0]!), sEnd: sParam(curr[curr.length - 1]!) });
          curr = null;
        }
      } else if (!insI && insJ) {
        curr = [cut(pi, pj, fi, fj), pj];
      }
    }
  }

  // Stitch the open chains into closed loops along the cut line. Walking the kept
  // boundary, after a chain's exit point we travel along the line to the nearest
  // entry point in the travel direction, then follow that chain - merging outer
  // and hole boundaries into single rings.
  const dirSign = keepSign > 0 ? 1 : -1;
  const entries = chains
    .map((c, idx) => ({ s: c.sStart, idx }))
    .sort((x, y) => dirSign * x.s - dirSign * y.s);
  const nextChainAfter = (exitS: number): number => {
    for (const e of entries) if (dirSign * e.s > dirSign * exitS + EPS) return e.idx;
    return entries[0]?.idx ?? -1;
  };
  const used = new Array<boolean>(chains.length).fill(false);
  for (let startIdx = 0; startIdx < chains.length; startIdx++) {
    if (used[startIdx]) continue;
    const loop: LocalPt[] = [];
    let idx = startIdx;
    let guard = 0;
    while (idx >= 0 && !used[idx] && guard++ <= chains.length) {
      used[idx] = true;
      loop.push(...chains[idx]!.pts);
      idx = nextChainAfter(chains[idx]!.sEnd);
    }
    if (loop.length >= 3) closedLoops.push(loop);
  }

  // Classify loops: CCW = outer ring of a piece, CW = a hole. Assign holes to the
  // outer that contains them.
  const pieces: ClipPiece[] = [];
  const holeLoops: LocalPt[][] = [];
  for (const loop of closedLoops) {
    const area = signedArea2D(loop);
    if (Math.abs(area) < 0.5) continue; // drop degenerate slivers
    if (area > 0) pieces.push({ outer: loop, holes: [] });
    else holeLoops.push(loop);
  }
  for (const h of holeLoops) {
    const owner = pieces.find((p) => pointInRing(centroid(h), p.outer));
    if (owner) owner.holes.push(h);
  }
  return pieces;
}

/**
 * Slice a closed area with a straight line (two world points) into pieces. The
 * line is treated as infinite: every region on each side becomes its own polygon,
 * and holes the cut crosses are merged into the boundary (an annulus sliced
 * across its ring yields C-shaped polygons). Returns null if the line doesn't
 * actually divide the area (caller treats as a no-op).
 */
export function splitObjectByLine(obj: EditorObject, p1: LatLng, p2: LatLng): EditorObject[] | null {
  if (obj.type === 'corridor' || obj.base.length < 3) return null;

  const a = worldToLocal(obj, p1);
  const b = worldToLocal(obj, p2);
  if (Math.hypot(b.x - a.x, b.y - a.y) < 1e-6) return null;

  const outer = ensureWinding(obj.base, true);
  const holes = obj.holes.filter((h) => h.length >= 3).map((h) => ensureWinding(h, false));

  // The drawn stroke must actually reach the area; a far-off line whose infinite
  // extension happens to pass through must not silently split it.
  if (segmentRingCrossings(a, b, outer) < 1 && !pointInRing(a, outer) && !pointInRing(b, outer)) {
    return null;
  }

  const pieces = [
    ...clipByHalfPlane(outer, holes, a, b, 1),
    ...clipByHalfPlane(outer, holes, a, b, -1),
  ].filter((p) => p.outer.length >= 3);
  if (pieces.length < 2) return null; // line outside / tangent -> nothing split

  return pieces.map((piece, i) => {
    const world = piece.outer.map((p) => localToWorld(obj, p));
    const worldHoles = piece.holes.map((h) => h.map((p) => localToWorld(obj, p)));
    const suffix = String.fromCharCode(65 + (i % 26));
    const built = makeFromWorldRing('polygon', world, `${obj.name} ${suffix}`, { holes: worldHoles });
    return obj.color ? { ...built, color: obj.color } : built;
  });
}

// ---------------------------------------------------------------------------
// Polygon ∩ polygon (Greiner-Hormann) — used to clip a drawn hole to its area
// ---------------------------------------------------------------------------

interface GHNode {
  x: number;
  y: number;
  next: GHNode;
  prev: GHNode;
  intersect: boolean;
  entry: boolean;
  neighbor: GHNode | null;
  alpha: number;
  visited: boolean;
}

function ghBuild(pts: LocalPt[]): GHNode[] {
  const nodes: GHNode[] = pts.map((p) => ({
    x: p.x, y: p.y, next: null as unknown as GHNode, prev: null as unknown as GHNode,
    intersect: false, entry: false, neighbor: null, alpha: 0, visited: false,
  }));
  const n = nodes.length;
  for (let i = 0; i < n; i++) {
    nodes[i]!.next = nodes[(i + 1) % n]!;
    nodes[i]!.prev = nodes[(i - 1 + n) % n]!;
  }
  return nodes;
}

/** Insert an intersection node along the edge that starts at `start`, ordered by alpha. */
function ghInsert(ins: GHNode, start: GHNode, end: GHNode): void {
  let curr = start.next;
  while (curr !== end && curr.alpha < ins.alpha) curr = curr.next;
  ins.prev = curr.prev;
  ins.next = curr;
  curr.prev.next = ins;
  curr.prev = ins;
}

function ghLineCross(
  p1: LocalPt, p2: LocalPt, q1: LocalPt, q2: LocalPt,
): { aP: number; aQ: number; x: number; y: number } | null {
  const rx = p2.x - p1.x; const ry = p2.y - p1.y;
  const sx = q2.x - q1.x; const sy = q2.y - q1.y;
  const denom = rx * sy - ry * sx;
  if (Math.abs(denom) < 1e-12) return null;
  const t = ((q1.x - p1.x) * sy - (q1.y - p1.y) * sx) / denom;
  const u = ((q1.x - p1.x) * ry - (q1.y - p1.y) * rx) / denom;
  // Skip hits at an endpoint to dodge the classic Greiner-Hormann degeneracies.
  if (t <= 1e-9 || t >= 1 - 1e-9 || u <= 1e-9 || u >= 1 - 1e-9) return null;
  return { aP: t, aQ: u, x: p1.x + t * rx, y: p1.y + t * ry };
}

/**
 * Intersect two simple polygons and return the overlapping region(s) as rings
 * (Greiner-Hormann). Both may be concave. Used to clip a freehand hole to the
 * area it was drawn into, so a hole that pokes past the boundary (or across
 * neighbouring objects) is trimmed to the part actually inside - rather than
 * stored as a ring that crosses the outline and triangulates into garbage.
 */
export function clipRingToPolygon(subjectPts: LocalPt[], clipPts: LocalPt[]): LocalPt[][] {
  if (subjectPts.length < 3 || clipPts.length < 3) return [];
  const subj = signedArea2D(subjectPts) < 0 ? [...subjectPts].reverse() : subjectPts;
  const clip = signedArea2D(clipPts) < 0 ? [...clipPts].reverse() : clipPts;

  const sNodes = ghBuild(subj);
  const cNodes = ghBuild(clip);

  let crossed = false;
  for (let i = 0; i < sNodes.length; i++) {
    const s1 = sNodes[i]!; const s2 = sNodes[(i + 1) % sNodes.length]!;
    for (let j = 0; j < cNodes.length; j++) {
      const c1 = cNodes[j]!; const c2 = cNodes[(j + 1) % cNodes.length]!;
      const hit = ghLineCross(s1, s2, c1, c2);
      if (!hit) continue;
      crossed = true;
      const a: GHNode = { x: hit.x, y: hit.y, next: s2, prev: s1, intersect: true, entry: false, neighbor: null, alpha: hit.aP, visited: false };
      const b: GHNode = { x: hit.x, y: hit.y, next: c2, prev: c1, intersect: true, entry: false, neighbor: null, alpha: hit.aQ, visited: false };
      a.neighbor = b; b.neighbor = a;
      ghInsert(a, s1, s2);
      ghInsert(b, c1, c2);
    }
  }

  if (!crossed) {
    // No crossings: either fully inside, fully containing, or disjoint.
    if (pointInRing(subj[0]!, clip)) return [subj.map((p) => ({ ...p }))];
    if (pointInRing(clip[0]!, subj)) return [clip.map((p) => ({ ...p }))];
    return [];
  }

  // Mark each intersection as an entry to / exit from the other polygon.
  const mark = (start: GHNode, otherPts: LocalPt[]): void => {
    let inside = pointInRing({ x: start.x, y: start.y }, otherPts);
    let node = start;
    do {
      if (node.intersect) { node.entry = !inside; inside = !inside; }
      node = node.next;
    } while (node !== start);
  };
  mark(sNodes[0]!, clip);
  mark(cNodes[0]!, subj);

  // Trace the intersection: at an entry walk forward, at an exit walk backward,
  // switching polygons at every intersection.
  const result: LocalPt[][] = [];
  const starts: GHNode[] = [];
  let scan = sNodes[0]!;
  do { if (scan.intersect) starts.push(scan); scan = scan.next; } while (scan !== sNodes[0]!);

  for (const start of starts) {
    if (start.visited) continue;
    const poly: LocalPt[] = [];
    let current = start;
    let guard = 0;
    do {
      current.visited = true;
      if (current.neighbor) current.neighbor.visited = true;
      if (current.entry) {
        do { current = current.next; poly.push({ x: current.x, y: current.y }); } while (!current.intersect && guard++ < 100000);
      } else {
        do { current = current.prev; poly.push({ x: current.x, y: current.y }); } while (!current.intersect && guard++ < 100000);
      }
      if (!current.neighbor) break;
      current = current.neighbor;
    } while (current !== start && guard++ < 100000);
    if (poly.length >= 3) result.push(poly);
  }
  return result;
}
