/**
 * Polygon Clipping for Survey Grid Lines
 * Clips horizontal scan lines against a polygon boundary using scan-line intersection.
 */

interface Point2D {
  x: number;
  y: number;
}

/**
 * Find X intersections of a horizontal line at Y with polygon edges.
 * Returns sorted X coordinates where the line enters/exits the polygon.
 */
function scanLineIntersections(polygon: Point2D[], y: number): number[] {
  const intersections: number[] = [];
  const n = polygon.length;

  for (let i = 0; i < n; i++) {
    const a = polygon[i]!;
    const b = polygon[(i + 1) % n]!;

    // Check if edge crosses the scan line
    if ((a.y <= y && b.y > y) || (b.y <= y && a.y > y)) {
      // Calculate X intersection using linear interpolation
      const t = (y - a.y) / (b.y - a.y);
      const x = a.x + t * (b.x - a.x);
      intersections.push(x);
    }
  }

  // Sort for proper pairing (enter/exit)
  intersections.sort((a, b) => a - b);
  return intersections;
}

export interface ClippedSegment {
  x1: number;
  x2: number;
  y: number;
}

/**
 * Clip horizontal scan lines against a polygon boundary.
 * Returns line segments that are inside the polygon.
 *
 * @param polygon - Vertices in local 2D coordinates
 * @param lineSpacing - Distance between scan lines (meters)
 * @param overshoot - Extra distance past polygon edges (meters)
 * @returns Array of clipped line segments
 */
export function clipScanLines(
  polygon: Point2D[],
  lineSpacing: number,
  overshoot: number = 0,
  holes: Point2D[][] = [],
): ClippedSegment[] {
  if (polygon.length < 3 || lineSpacing <= 0) return [];

  // Find bounding box
  let minY = Infinity, maxY = -Infinity;
  for (const p of polygon) {
    if (p.y < minY) minY = p.y;
    if (p.y > maxY) maxY = p.y;
  }

  const segments: ClippedSegment[] = [];

  // Start from half a line spacing inside the bounding box
  const startY = minY + lineSpacing / 2;

  for (let y = startY; y < maxY; y += lineSpacing) {
    // Combine the outer-boundary crossings with each hole's crossings and sort.
    // Even-odd pairing over the merged list yields the spans that are inside the
    // polygon AND outside every hole - so scan lines automatically break around
    // no-fly holes. (A hole crossing flips parity, turning a hole span into a
    // gap.)
    const xs = scanLineIntersections(polygon, y);
    if (xs.length < 2) continue;
    for (const hole of holes) {
      if (hole.length >= 3) xs.push(...scanLineIntersections(hole, y));
    }
    xs.sort((a, b) => a - b);

    const lastIdx = xs.length - 1;
    for (let i = 0; i + 1 < xs.length; i += 2) {
      // Overshoot only extends the true outer ends of the line (first/last
      // crossings), never the hole-induced split points.
      const x1 = xs[i]! - (i === 0 ? overshoot : 0);
      const x2 = xs[i + 1]! + (i + 1 === lastIdx ? overshoot : 0);
      segments.push({ x1, x2, y });
    }
  }

  return segments;
}

// ── Boustrophedon routing over disconnected regions ──────────────────────────

/**
 * Order clipped scan segments into a sensible single-pass flight path.
 *
 * The naive approach — emit segments in (y, x) order and alternate direction by
 * index — only works for a convex polygon, where every scan row yields exactly
 * one inside-span. For a concave or branching boundary (corridors, multi-arm
 * areas), a single row crosses several disjoint arms, and the naive serpentine
 * connects the end of one arm straight to the next arm ON THE SAME ROW. That
 * draws long horizontal deadheads across the empty interior on every row — the
 * vehicle would actually fly them.
 *
 * Instead we group segments into connected components (an "arm" = segments on
 * adjacent rows whose x-intervals overlap), serpentine within each arm, then
 * stitch the arms together greedily by nearest endpoint. Cross-void traversals
 * drop from one-per-row to roughly one-per-arm-boundary.
 *
 * Returns oriented segments: x1 is the entry, x2 the exit, in traversal order
 * (so x1 may be greater than x2).
 */
export function routeScanSegments(
  segments: ClippedSegment[],
  lineSpacing: number,
): ClippedSegment[] {
  if (segments.length <= 1) return segments;

  // Union-find over segment indices.
  const parent = segments.map((_, i) => i);
  const find = (i: number): number => {
    let r = i;
    while (parent[r] !== r) r = parent[r]!;
    while (parent[i] !== r) { const n = parent[i]!; parent[i] = r; i = n; }
    return r;
  };
  const union = (a: number, b: number) => { parent[find(a)] = find(b); };

  // Group segment indices by their (shared) row y, rows ascending.
  const rows = new Map<number, number[]>();
  segments.forEach((s, i) => {
    const bucket = rows.get(s.y);
    if (bucket) bucket.push(i);
    else rows.set(s.y, [i]);
  });
  const ys = [...rows.keys()].sort((a, b) => a - b);

  // Two segments on adjacent rows belong to the same arm if their x-intervals
  // overlap. Rows separated by more than ~1.5 line spacings (a pinch where the
  // boundary produced no span) are treated as disconnected.
  const overlaps = (a: ClippedSegment, b: ClippedSegment) =>
    Math.min(a.x1, a.x2) <= Math.max(b.x1, b.x2) &&
    Math.min(b.x1, b.x2) <= Math.max(a.x1, a.x2);

  for (let r = 0; r + 1 < ys.length; r++) {
    const y0 = ys[r]!;
    const y1 = ys[r + 1]!;
    if (y1 - y0 > lineSpacing * 1.5) continue;
    for (const i of rows.get(y0)!) {
      for (const j of rows.get(y1)!) {
        if (overlaps(segments[i]!, segments[j]!)) union(i, j);
      }
    }
  }

  // Collect components, each sorted by row then x.
  const components = new Map<number, ClippedSegment[]>();
  segments.forEach((s, i) => {
    const root = find(i);
    const list = components.get(root);
    if (list) list.push(s);
    else components.set(root, [s]);
  });
  for (const list of components.values()) {
    list.sort((a, b) => (a.y - b.y) || (Math.min(a.x1, a.x2) - Math.min(b.x1, b.x2)));
  }

  // Greedy nearest-endpoint chaining: orient each segment so its entry is the
  // end nearest the current position. Within an arm (one span per row) this
  // reproduces a serpentine; it also picks the cheaper end when crossing arms.
  const dist = (px: number, py: number, x: number, y: number) => Math.hypot(x - px, y - py);
  const chain = (segs: ClippedSegment[], px: number, py: number): {
    ordered: ClippedSegment[]; x: number; y: number;
  } => {
    const remaining = [...segs];
    const ordered: ClippedSegment[] = [];
    let cx = px, cy = py;
    while (remaining.length > 0) {
      let best = 0, reverse = false, bestD = Infinity;
      for (let k = 0; k < remaining.length; k++) {
        const s = remaining[k]!;
        const dStart = dist(cx, cy, s.x1, s.y);
        const dEnd = dist(cx, cy, s.x2, s.y);
        if (dStart < bestD) { bestD = dStart; best = k; reverse = false; }
        if (dEnd < bestD) { bestD = dEnd; best = k; reverse = true; }
      }
      const s = remaining.splice(best, 1)[0]!;
      const entry = reverse ? s.x2 : s.x1;
      const exit = reverse ? s.x1 : s.x2;
      ordered.push({ x1: entry, x2: exit, y: s.y });
      cx = exit; cy = s.y;
    }
    return { ordered, x: cx, y: cy };
  };

  // Start from the lowest-then-leftmost endpoint so the path begins at a
  // natural corner rather than mid-area.
  const start = segments.reduce((acc, s) => {
    const x = Math.min(s.x1, s.x2);
    return (s.y < acc.y || (s.y === acc.y && x < acc.x)) ? { x, y: s.y } : acc;
  }, { x: Infinity, y: Infinity });

  // Visit components greedily by whichever has an endpoint nearest the current
  // position, chaining each as we go.
  const pending = [...components.values()];
  const result: ClippedSegment[] = [];
  let cx = start.x, cy = start.y;
  while (pending.length > 0) {
    let bestIdx = 0, bestD = Infinity;
    for (let k = 0; k < pending.length; k++) {
      for (const s of pending[k]!) {
        const d = Math.min(
          dist(cx, cy, s.x1, s.y), dist(cx, cy, s.x2, s.y),
        );
        if (d < bestD) { bestD = d; bestIdx = k; }
      }
    }
    const comp = pending.splice(bestIdx, 1)[0]!;
    const { ordered, x, y } = chain(comp, cx, cy);
    result.push(...ordered);
    cx = x; cy = y;
  }

  return result;
}

// ── Hole-aware transit legs ──────────────────────────────────────────────────

/** Strict point-in-ring test (ray cast); boundary points count as outside. */
function pointStrictlyInRing(p: Point2D, ring: Point2D[]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i]!;
    const b = ring[j]!;
    if (a.y > p.y !== b.y > p.y && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x) {
      inside = !inside;
    }
  }
  return inside;
}

/** Monotone-chain convex hull. Returns CCW ring without repeated last point. */
function convexHull(points: Point2D[]): Point2D[] {
  const pts = [...points].sort((a, b) => a.x - b.x || a.y - b.y);
  if (pts.length <= 3) return pts;
  const cross = (o: Point2D, a: Point2D, b: Point2D) =>
    (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
  const lower: Point2D[] = [];
  for (const p of pts) {
    while (lower.length >= 2 && cross(lower[lower.length - 2]!, lower[lower.length - 1]!, p) <= 0) lower.pop();
    lower.push(p);
  }
  const upper: Point2D[] = [];
  for (let i = pts.length - 1; i >= 0; i--) {
    const p = pts[i]!;
    while (upper.length >= 2 && cross(upper[upper.length - 2]!, upper[upper.length - 1]!, p) <= 0) upper.pop();
    upper.push(p);
  }
  lower.pop();
  upper.pop();
  return [...lower, ...upper];
}

/**
 * Whether the leg a->b passes through the ring's interior. Touching the
 * boundary (scan-line ends sit exactly on hole edges) does not count - only
 * actual incursion does.
 */
export function legEntersRing(a: Point2D, b: Point2D, ring: Point2D[]): boolean {
  // Test against a ring shrunk by ~1 cm: legs hugging the hole boundary
  // (detours along hull edges, scan ends on hole edges) are legal, and the
  // ray-cast ambiguity of exactly-on-edge points disappears. Sampling instead
  // of edge-sign tests stays robust when endpoints lie on the ring.
  const cx = ring.reduce((acc, p) => acc + p.x, 0) / ring.length;
  const cy = ring.reduce((acc, p) => acc + p.y, 0) / ring.length;
  const EPS_M = 0.01;
  const shrunk = ring.map((p) => {
    const dx = p.x - cx;
    const dy = p.y - cy;
    const r = Math.hypot(dx, dy);
    const f = r > EPS_M ? (r - EPS_M) / r : 0;
    return { x: cx + dx * f, y: cy + dy * f };
  });
  const STEPS = 16;
  for (let s = 1; s < STEPS; s++) {
    const t = s / STEPS;
    const p = { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
    if (pointStrictlyInRing(p, shrunk)) return true;
  }
  return false;
}

/**
 * Cyrus-Beck style clip of the leg a->b against a convex CCW hull. Returns
 * the hull edge indices where the leg enters and exits, or null when the leg
 * misses the interior.
 */
function clipLegAgainstHull(
  a: Point2D,
  b: Point2D,
  hull: Point2D[],
): { entryEdge: number; exitEdge: number } | null {
  const d = { x: b.x - a.x, y: b.y - a.y };
  // Epsilon-open bounds: transit endpoints routinely sit exactly ON hull
  // edges (scan-line ends at hole boundaries give t = 0 / t = 1), and those
  // must still assign an entry/exit edge.
  let tEnter = -1e-9;
  let tExit = 1 + 1e-9;
  let entryEdge = -1;
  let exitEdge = -1;
  for (let i = 0; i < hull.length; i++) {
    const p0 = hull[i]!;
    const p1 = hull[(i + 1) % hull.length]!;
    // Outward normal of a CCW edge.
    const nx = p1.y - p0.y;
    const ny = p0.x - p1.x;
    const denom = nx * d.x + ny * d.y;
    const num = nx * (p0.x - a.x) + ny * (p0.y - a.y);
    if (Math.abs(denom) < 1e-12) {
      if (num < 0) return null; // parallel and fully outside this edge
      continue;
    }
    const t = num / denom;
    if (denom < 0) {
      // entering
      if (t > tEnter) {
        tEnter = t;
        entryEdge = i;
      }
    } else if (t < tExit) {
      tExit = t;
      exitEdge = i;
    }
  }
  if (tEnter >= tExit || entryEdge < 0 || exitEdge < 0) return null;
  return { entryEdge, exitEdge };
}

/**
 * Detour points that take the leg a->b around no-fly holes instead of over
 * them. Routes along the convex hull of each crossed hole (shorter side),
 * iterating until every sub-leg is clear. Returns intermediate points only;
 * empty when the direct leg is already legal.
 */
export function routeTransitAroundHoles(
  a: Point2D,
  b: Point2D,
  holes: Point2D[][],
): Point2D[] {
  const hulls = holes.filter((h) => h.length >= 3).map(convexHull);
  if (hulls.length === 0) return [];

  const path: Point2D[] = [a, b];
  let i = 0;
  let guard = 0;
  while (i + 1 < path.length && guard++ < 128) {
    const p = path[i]!;
    const q = path[i + 1]!;
    const hull = hulls.find((h) => legEntersRing(p, q, h));
    if (!hull) {
      i++;
      continue;
    }
    const clip = clipLegAgainstHull(p, q, hull);
    if (!clip) {
      i++; // numerically ambiguous corner graze - accept the leg
      continue;
    }
    const n = hull.length;
    // Forward chain: vertices after the entry edge up to the exit edge.
    const forward: Point2D[] = [];
    for (let k = (clip.entryEdge + 1) % n; ; k = (k + 1) % n) {
      forward.push(hull[k]!);
      if (k === clip.exitEdge) break;
      if (forward.length > n) break;
    }
    // Backward chain: entry-edge start walking the other way round.
    const backward: Point2D[] = [];
    for (let k = clip.entryEdge; ; k = (k - 1 + n) % n) {
      backward.push(hull[k]!);
      if (k === (clip.exitEdge + 1) % n) break;
      if (backward.length > n) break;
    }
    const len = (chain: Point2D[]) => {
      let total = 0;
      let prev = p;
      for (const v of [...chain, q]) {
        total += Math.hypot(v.x - prev.x, v.y - prev.y);
        prev = v;
      }
      return total;
    };
    const chain = len(forward) <= len(backward) ? forward : backward;
    if (chain.length === 0) {
      i++;
      continue;
    }
    path.splice(i + 1, 0, ...chain);
    // Re-check from the same index: the first sub-leg may cross another hole.
  }
  return path.slice(1, -1);
}
