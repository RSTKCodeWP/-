/**
 * Tests for geo-edit.ts - pure geometry edit operations.
 * Uses a small square near lat=42, lng=19 (Montenegro-ish) for known coordinates.
 *
 * The square has vertices at approximately:
 *   NW: { lat: 42.001, lng: 19.000 }
 *   NE: { lat: 42.001, lng: 19.001 }
 *   SE: { lat: 42.000, lng: 19.001 }
 *   SW: { lat: 42.000, lng: 19.000 }
 *
 * At lat=42, 1 degree lng ~= 82,200m * cos(42°) ~= 74,000m, so 0.001 deg lng ~= 74m
 * 0.001 deg lat ~= 111m
 * So the square is roughly 74m wide by 111m tall.
 */

import { describe, it, expect } from 'vitest';
import type { LatLng } from './survey-types';
import {
  snapPoint,
  nearestEdgeIndex,
  insertVertexOnEdge,
  nudgeVertex,
  removeVertexSafe,
  pointInRing,
  splitPolygon,
  ringSignedAreaLocal,
  ensureWinding,
  corridorSwath,
  rectangleRing,
  circleRing,
  polylineLength,
} from './geo-edit';
import { distanceLatLng, polygonArea } from './geo-math';

// A simple square ring (CCW order: NW, NE, SE, SW)
const SQUARE: LatLng[] = [
  { lat: 42.001, lng: 19.000 }, // 0: NW
  { lat: 42.001, lng: 19.001 }, // 1: NE
  { lat: 42.000, lng: 19.001 }, // 2: SE
  { lat: 42.000, lng: 19.000 }, // 3: SW
];

// ============================================================
// snapPoint
// ============================================================

describe('snapPoint', () => {
  it('returns null for empty targets', () => {
    expect(snapPoint({ lat: 42.000, lng: 19.000 }, [], 50)).toBeNull();
  });

  it('returns the nearest target when within tolerance', () => {
    // Point very close to SW corner (lat=42.000, lng=19.000)
    // offset ~11m south and ~7m west - well within 50m tolerance
    const p: LatLng = { lat: 41.9999, lng: 18.9999 };
    const result = snapPoint(p, SQUARE, 50);
    // SW corner is at lat=42.000, lng=19.000 - closest
    expect(result).not.toBeNull();
    expect(result?.lat).toBeCloseTo(42.000, 5);
    expect(result?.lng).toBeCloseTo(19.000, 5);
  });

  it('returns null when nearest target is beyond tolerance', () => {
    // A point far from all corners (center of square, ~50m+ from any corner)
    const p: LatLng = { lat: 42.0005, lng: 19.0005 };
    // With a tight tolerance of 5m, nothing should snap
    const result = snapPoint(p, SQUARE, 5);
    expect(result).toBeNull();
  });

  it('snaps to the nearest of multiple candidates', () => {
    const targets: LatLng[] = [
      { lat: 42.000, lng: 19.000 }, // SW
      { lat: 42.001, lng: 19.001 }, // NE
    ];
    // Point much closer to SW corner
    const p: LatLng = { lat: 42.0001, lng: 19.0001 };
    const result = snapPoint(p, targets, 200);
    expect(result?.lat).toBeCloseTo(42.000, 5);
    expect(result?.lng).toBeCloseTo(19.000, 5);
  });
});

// ============================================================
// nearestEdgeIndex
// ============================================================

describe('nearestEdgeIndex', () => {
  it('returns -1 for rings with fewer than 2 vertices', () => {
    expect(nearestEdgeIndex([], { lat: 42, lng: 19 })).toBe(-1);
    expect(nearestEdgeIndex([{ lat: 42, lng: 19 }], { lat: 42, lng: 19 })).toBe(-1);
  });

  it('handles a 2-vertex ring (single bidirectional edge)', () => {
    const edge: LatLng[] = [SQUARE[0]!, SQUARE[1]!];
    expect(nearestEdgeIndex(edge, { lat: 42.0015, lng: 19.0005 })).toBe(0);
  });

  it('finds the north edge (index 0: NW->NE) for a point above the square', () => {
    // Point directly above the north edge midpoint
    const p: LatLng = { lat: 42.0015, lng: 19.0005 };
    const idx = nearestEdgeIndex(SQUARE, p);
    expect(idx).toBe(0); // edge 0: NW(0)->NE(1) is the north edge
  });

  it('finds the east edge (index 1: NE->SE) for a point to the right', () => {
    // Point to the right of the east edge midpoint
    const p: LatLng = { lat: 42.0005, lng: 19.0015 };
    const idx = nearestEdgeIndex(SQUARE, p);
    expect(idx).toBe(1); // edge 1: NE(1)->SE(2) is the east edge
  });

  it('finds the south edge (index 2: SE->SW) for a point below', () => {
    // Point directly below the south edge midpoint
    const p: LatLng = { lat: 41.9995, lng: 19.0005 };
    const idx = nearestEdgeIndex(SQUARE, p);
    expect(idx).toBe(2); // edge 2: SE(2)->SW(3) is the south edge
  });

  it('finds the west edge (index 3: SW->NW) for a point to the left', () => {
    // Point to the left of the west edge midpoint
    const p: LatLng = { lat: 42.0005, lng: 18.9985 };
    const idx = nearestEdgeIndex(SQUARE, p);
    expect(idx).toBe(3); // edge 3: SW(3)->NW(0) is the west edge
  });
});

// ============================================================
// insertVertexOnEdge
// ============================================================

describe('insertVertexOnEdge', () => {
  it('inserts a point on the nearest edge and returns correct index', () => {
    // Point above the north edge -> nearest edge is 0 (NW->NE)
    // Insert between index 0 (NW) and index 1 (NE)
    const newPt: LatLng = { lat: 42.0015, lng: 19.0005 };
    const { ring, index } = insertVertexOnEdge(SQUARE, newPt);
    expect(index).toBe(1); // inserted after ring[0], so index 1
    expect(ring).toHaveLength(5);
    expect(ring[1]?.lat).toBeCloseTo(42.0015, 5);
    expect(ring[1]?.lng).toBeCloseTo(19.0005, 5);
  });

  it('does not mutate the original ring', () => {
    const original = SQUARE.map(v => ({ ...v }));
    const newPt: LatLng = { lat: 42.0015, lng: 19.0005 };
    const { ring } = insertVertexOnEdge(SQUARE, newPt);
    expect(SQUARE).toEqual(original);
    expect(ring).not.toBe(SQUARE);
  });

  it('appends and returns last index for ring with 0 vertices', () => {
    const { ring, index } = insertVertexOnEdge([], { lat: 42, lng: 19 });
    expect(ring).toHaveLength(1);
    expect(index).toBe(0);
  });

  it('appends and returns last index for ring with 1 vertex', () => {
    const { ring, index } = insertVertexOnEdge([{ lat: 42, lng: 19 }], { lat: 42.001, lng: 19.001 });
    expect(ring).toHaveLength(2);
    expect(index).toBe(1);
  });

  it('inserts on the south edge correctly', () => {
    // Point below center -> south edge (index 2: SE->SW)
    const newPt: LatLng = { lat: 41.9995, lng: 19.0005 };
    const { ring, index } = insertVertexOnEdge(SQUARE, newPt);
    // Inserted after ring[2] (SE), so at index 3
    expect(index).toBe(3);
    expect(ring).toHaveLength(5);
    expect(ring[3]?.lat).toBeCloseTo(41.9995, 5);
  });
});

// ============================================================
// nudgeVertex
// ============================================================

describe('nudgeVertex', () => {
  it('moves the specified vertex by the given delta', () => {
    const ring = nudgeVertex(SQUARE, 0, 0.001, 0.001);
    expect(ring[0]?.lat).toBeCloseTo(42.002, 5);
    expect(ring[0]?.lng).toBeCloseTo(19.001, 5);
  });

  it('does not mutate the original ring', () => {
    const original = SQUARE.map(v => ({ ...v }));
    nudgeVertex(SQUARE, 1, 0.005, 0.005);
    expect(SQUARE).toEqual(original);
  });

  it('leaves other vertices unchanged', () => {
    const ring = nudgeVertex(SQUARE, 0, 0.001, 0.001);
    expect(ring[1]).toEqual(SQUARE[1]);
    expect(ring[2]).toEqual(SQUARE[2]);
    expect(ring[3]).toEqual(SQUARE[3]);
  });

  it('returns a copy unchanged for out-of-range index', () => {
    const ring = nudgeVertex(SQUARE, 99, 0.001, 0.001);
    expect(ring).toEqual(SQUARE);
    expect(ring).not.toBe(SQUARE); // still a new array
  });

  it('returns copy unchanged for negative index', () => {
    const ring = nudgeVertex(SQUARE, -1, 0.001, 0.001);
    expect(ring).toEqual(SQUARE);
  });
});

// ============================================================
// removeVertexSafe
// ============================================================

describe('removeVertexSafe', () => {
  it('removes a vertex when above the floor', () => {
    // SQUARE has 4 vertices, default minVertices=3, can remove one
    const ring = removeVertexSafe(SQUARE, 1);
    expect(ring).toHaveLength(3);
    // Vertex at index 1 (NE) should be gone
    const hasNE = ring.some(v => Math.abs(v.lat - 42.001) < 1e-6 && Math.abs(v.lng - 19.001) < 1e-6);
    expect(hasNE).toBe(false);
  });

  it('refuses to remove when at the floor', () => {
    const threeVerts: LatLng[] = [SQUARE[0]!, SQUARE[1]!, SQUARE[2]!];
    const ring = removeVertexSafe(threeVerts, 0, 3);
    expect(ring).toHaveLength(3);
    expect(ring).toEqual(threeVerts);
    expect(ring).not.toBe(threeVerts);
  });

  it('does not mutate the original ring', () => {
    const original = SQUARE.map(v => ({ ...v }));
    removeVertexSafe(SQUARE, 0);
    expect(SQUARE).toEqual(original);
  });

  it('returns copy unchanged for out-of-range index', () => {
    const ring = removeVertexSafe(SQUARE, 99);
    expect(ring).toEqual(SQUARE);
    expect(ring).not.toBe(SQUARE);
  });

  it('returns copy unchanged for negative index', () => {
    const ring = removeVertexSafe(SQUARE, -1);
    expect(ring).toEqual(SQUARE);
  });

  it('uses custom minVertices', () => {
    // With minVertices=5, a 4-vertex ring cannot remove any vertex
    const ring = removeVertexSafe(SQUARE, 0, 5);
    expect(ring).toHaveLength(4);
    expect(ring).toEqual(SQUARE);
  });
});

// ============================================================
// pointInRing
// ============================================================

describe('pointInRing', () => {
  it('returns false for rings with fewer than 3 vertices', () => {
    expect(pointInRing({ lat: 42.0005, lng: 19.0005 }, [])).toBe(false);
    expect(pointInRing({ lat: 42.0005, lng: 19.0005 }, [SQUARE[0]!])).toBe(false);
    expect(pointInRing({ lat: 42.0005, lng: 19.0005 }, [SQUARE[0]!, SQUARE[1]!])).toBe(false);
  });

  it('returns true for a point clearly inside the square', () => {
    const p: LatLng = { lat: 42.0005, lng: 19.0005 }; // center of the square
    expect(pointInRing(p, SQUARE)).toBe(true);
  });

  it('returns false for a point clearly outside the square', () => {
    const p: LatLng = { lat: 43.0, lng: 20.0 }; // far outside
    expect(pointInRing(p, SQUARE)).toBe(false);
  });

  it('returns false for a point to the left of the square', () => {
    const p: LatLng = { lat: 42.0005, lng: 18.999 }; // west of square
    expect(pointInRing(p, SQUARE)).toBe(false);
  });

  it('returns false for a point above the square', () => {
    const p: LatLng = { lat: 42.002, lng: 19.0005 }; // north of square
    expect(pointInRing(p, SQUARE)).toBe(false);
  });

  it('returns true for a point inside a triangle', () => {
    const triangle: LatLng[] = [
      { lat: 42.002, lng: 19.000 },
      { lat: 42.000, lng: 19.002 },
      { lat: 42.000, lng: 18.998 },
    ];
    const inside: LatLng = { lat: 42.0005, lng: 19.000 };
    expect(pointInRing(inside, triangle)).toBe(true);

    const outside: LatLng = { lat: 42.003, lng: 19.000 };
    expect(pointInRing(outside, triangle)).toBe(false);
  });
});

// ============================================================
// splitPolygon
// ============================================================

describe('splitPolygon', () => {
  // SQUARE: [A(0), B(1), C(2), D(3)]
  // A = NW, B = NE, C = SE, D = SW

  it('splits a square at indices 0 and 2 into two triangles', () => {
    // Chord: A(0) -> C(2)
    // Ring1 = [A, B, C] (0 to 2 walking forward)
    // Ring2 = [C, D, A] (2 to 0 walking forward, wrapping)
    const result = splitPolygon(SQUARE, 0, 2);
    expect(result).not.toBeNull();
    const [r1, r2] = result!;

    expect(r1).toHaveLength(3);
    expect(r2).toHaveLength(3);

    // Ring1 should be A, B, C
    expect(r1[0]).toEqual(SQUARE[0]); // A
    expect(r1[1]).toEqual(SQUARE[1]); // B
    expect(r1[2]).toEqual(SQUARE[2]); // C

    // Ring2 should be C, D, A
    expect(r2[0]).toEqual(SQUARE[2]); // C
    expect(r2[1]).toEqual(SQUARE[3]); // D
    expect(r2[2]).toEqual(SQUARE[0]); // A
  });

  it('splits correctly with wrapped indices (aIndex > bIndex)', () => {
    // Chord: C(2) -> A(0), which is same split but swapped order
    // Ring1 = [C, D, A] (2 to 0 walking forward, wrapping)
    // Ring2 = [A, B, C] (0 to 2 walking forward)
    const result = splitPolygon(SQUARE, 2, 0);
    expect(result).not.toBeNull();
    const [r1, r2] = result!;

    expect(r1).toHaveLength(3);
    expect(r2).toHaveLength(3);

    expect(r1[0]).toEqual(SQUARE[2]); // C
    expect(r1[1]).toEqual(SQUARE[3]); // D
    expect(r1[2]).toEqual(SQUARE[0]); // A

    expect(r2[0]).toEqual(SQUARE[0]); // A
    expect(r2[1]).toEqual(SQUARE[1]); // B
    expect(r2[2]).toEqual(SQUARE[2]); // C
  });

  it('returns null when ring has fewer than 4 vertices', () => {
    const triangle: LatLng[] = [SQUARE[0]!, SQUARE[1]!, SQUARE[2]!];
    expect(splitPolygon(triangle, 0, 2)).toBeNull();
    expect(splitPolygon([], 0, 1)).toBeNull();
  });

  it('returns null when indices are equal', () => {
    expect(splitPolygon(SQUARE, 1, 1)).toBeNull();
  });

  it('returns null when indices are adjacent (would produce degenerate ring)', () => {
    // Adjacent: 0 and 1 -> ring1 = [A, B] (only 2 vertices)
    expect(splitPolygon(SQUARE, 0, 1)).toBeNull();
    expect(splitPolygon(SQUARE, 1, 2)).toBeNull();
    // Wrapped adjacency: 3 and 0
    expect(splitPolygon(SQUARE, 3, 0)).toBeNull();
  });

  it('returns null when index is out of range', () => {
    expect(splitPolygon(SQUARE, -1, 2)).toBeNull();
    expect(splitPolygon(SQUARE, 0, 4)).toBeNull();
    expect(splitPolygon(SQUARE, 0, 99)).toBeNull();
  });

  it('does not mutate the original ring', () => {
    const original = SQUARE.map(v => ({ ...v }));
    splitPolygon(SQUARE, 0, 2);
    expect(SQUARE).toEqual(original);
  });

  it('produces new arrays (not aliased from original)', () => {
    const result = splitPolygon(SQUARE, 0, 2);
    expect(result).not.toBeNull();
    const [r1, r2] = result!;
    expect(r1).not.toBe(SQUARE);
    expect(r2).not.toBe(SQUARE);
    // Mutating r1 should not affect original
    r1[0] = { lat: 0, lng: 0 };
    expect(SQUARE[0]).toEqual({ lat: 42.001, lng: 19.000 });
  });
});

// ============================================================
// ringSignedAreaLocal
// ============================================================

describe('ringSignedAreaLocal', () => {
  it('returns 0 for rings with fewer than 3 vertices', () => {
    expect(ringSignedAreaLocal([])).toBe(0);
    expect(ringSignedAreaLocal([SQUARE[0]!])).toBe(0);
    expect(ringSignedAreaLocal([SQUARE[0]!, SQUARE[1]!])).toBe(0);
  });

  it('returns negative value for SQUARE ring (which is CW in local projection)', () => {
    // SQUARE is [NW, NE, SE, SW]: in local coords (x=east, y=north),
    // walking NW->NE->SE->SW traces clockwise -> negative signed area.
    const area = ringSignedAreaLocal(SQUARE);
    expect(area).toBeLessThan(0);
  });

  it('returns positive value for reversed SQUARE ring (CCW)', () => {
    // Reversing SQUARE makes it CCW -> positive signed area
    const ccwSquare = [...SQUARE].reverse();
    const area = ringSignedAreaLocal(ccwSquare);
    expect(area).toBeGreaterThan(0);
  });

  it('magnitude matches the rectangle area (approximately)', () => {
    // The SQUARE spans ~74m (lng) x ~111m (lat) at lat=42
    // Area should be roughly 74*111 = ~8214 m²
    const area = Math.abs(ringSignedAreaLocal(SQUARE));
    expect(area).toBeGreaterThan(7000);
    expect(area).toBeLessThan(10000);
  });
});

// ============================================================
// ensureWinding
// ============================================================

describe('ensureWinding', () => {
  // SQUARE is [NW, NE, SE, SW]: CW in local projection (negative signed area)

  it('returns a copy when winding already matches (SQUARE is CW, clockwise=true)', () => {
    const result = ensureWinding(SQUARE, true);
    expect(result).toEqual(SQUARE);
    expect(result).not.toBe(SQUARE);
  });

  it('returns a reversed copy when winding does not match (SQUARE is CW, clockwise=false requested)', () => {
    const result = ensureWinding(SQUARE, false);
    expect(result).toEqual([...SQUARE].reverse());
    expect(result).not.toBe(SQUARE);
  });

  it('returns a copy when CCW ring matches clockwise=false', () => {
    const ccwSquare = [...SQUARE].reverse();
    const result = ensureWinding(ccwSquare, false);
    expect(result).toEqual(ccwSquare);
    expect(result).not.toBe(ccwSquare);
  });

  it('reverses CCW ring when clockwise=true is requested', () => {
    const ccwSquare = [...SQUARE].reverse();
    const result = ensureWinding(ccwSquare, true);
    expect(result).toEqual(SQUARE);
  });

  it('does not mutate the original ring', () => {
    const original = SQUARE.map(v => ({ ...v }));
    ensureWinding(SQUARE, false);
    expect(SQUARE).toEqual(original);
  });
});

// ============================================================
// corridorSwath
// ============================================================

describe('corridorSwath', () => {
  // A straight ~111m east-west centerline at lat 42 (0.001 deg lng ~= 74m, but
  // we run it north-south here for a clean width check).
  const LINE: LatLng[] = [
    { lat: 42.000, lng: 19.000 },
    { lat: 42.001, lng: 19.000 }, // due north, ~111m
  ];

  it('returns empty for < 2 points or non-positive width', () => {
    expect(corridorSwath([], 50)).toEqual([]);
    expect(corridorSwath([{ lat: 42, lng: 19 }], 50)).toEqual([]);
    expect(corridorSwath(LINE, 0)).toEqual([]);
    expect(corridorSwath(LINE, -10)).toEqual([]);
  });

  it('produces a closed-able band with two vertices per centerline point', () => {
    const swath = corridorSwath(LINE, 60);
    // left side (n points) + right side (n points)
    expect(swath.length).toBe(LINE.length * 2);
  });

  it('offsets each side by half the width', () => {
    const widthM = 60;
    const swath = corridorSwath(LINE, widthM);
    // For a due-north line, the swath edges sit ~width/2 east and west of the
    // centerline endpoints. Check the first centerline point against its two
    // corresponding swath vertices (index 0 = left, last = right).
    const left = swath[0]!;
    const right = swath[swath.length - 1]!;
    const distLeft = distanceLatLng(LINE[0]!, left);
    const distRight = distanceLatLng(LINE[0]!, right);
    expect(distLeft).toBeGreaterThan(widthM / 2 - 5);
    expect(distLeft).toBeLessThan(widthM / 2 + 5);
    expect(distRight).toBeGreaterThan(widthM / 2 - 5);
    expect(distRight).toBeLessThan(widthM / 2 + 5);
  });

  it('widens as the width grows', () => {
    const narrow = corridorSwath(LINE, 30);
    const wide = corridorSwath(LINE, 120);
    const narrowSpan = distanceLatLng(narrow[0]!, narrow[narrow.length - 1]!);
    const wideSpan = distanceLatLng(wide[0]!, wide[wide.length - 1]!);
    expect(wideSpan).toBeGreaterThan(narrowSpan);
  });
});

// ============================================================
// rectangleRing / circleRing / polylineLength
// ============================================================

describe('rectangleRing', () => {
  it('returns 4 corners spanning both opposite points', () => {
    const a: LatLng = { lat: 42.000, lng: 19.000 };
    const c: LatLng = { lat: 42.001, lng: 19.001 };
    const ring = rectangleRing(a, c);
    expect(ring).toHaveLength(4);
    const lats = ring.map((p) => p.lat);
    const lngs = ring.map((p) => p.lng);
    expect(Math.min(...lats)).toBeCloseTo(42.000);
    expect(Math.max(...lats)).toBeCloseTo(42.001);
    expect(Math.min(...lngs)).toBeCloseTo(19.000);
    expect(Math.max(...lngs)).toBeCloseTo(19.001);
  });
});

describe('circleRing', () => {
  const center: LatLng = { lat: 42, lng: 19 };

  it('returns [] for non-positive radius or too few segments', () => {
    expect(circleRing(center, 0)).toEqual([]);
    expect(circleRing(center, -5)).toEqual([]);
    expect(circleRing(center, 100, 2)).toEqual([]);
  });

  it('places every vertex ~radius from the center', () => {
    const r = 100;
    const ring = circleRing(center, r, 32);
    expect(ring).toHaveLength(32);
    for (const v of ring) {
      const d = distanceLatLng(center, v);
      expect(d).toBeGreaterThan(r - 2);
      expect(d).toBeLessThan(r + 2);
    }
  });

  it('encloses an area approximating pi*r^2', () => {
    const r = 200;
    const ring = circleRing(center, r, 64);
    const area = polygonArea(ring);
    const ideal = Math.PI * r * r;
    expect(area).toBeGreaterThan(ideal * 0.97);
    expect(area).toBeLessThan(ideal * 1.01);
  });
});

describe('polylineLength', () => {
  it('is 0 for < 2 points', () => {
    expect(polylineLength([])).toBe(0);
    expect(polylineLength([{ lat: 42, lng: 19 }])).toBe(0);
  });

  it('sums segment lengths', () => {
    const pts: LatLng[] = [
      { lat: 42.000, lng: 19.000 },
      { lat: 42.001, lng: 19.000 }, // ~111m north
      { lat: 42.002, lng: 19.000 }, // ~111m north again
    ];
    const len = polylineLength(pts);
    expect(len).toBeGreaterThan(210);
    expect(len).toBeLessThan(235);
  });
});
