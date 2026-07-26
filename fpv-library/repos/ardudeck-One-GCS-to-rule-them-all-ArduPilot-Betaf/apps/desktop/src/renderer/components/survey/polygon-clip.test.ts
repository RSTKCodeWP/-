import { describe, it, expect } from 'vitest';
import { routeScanSegments, type ClippedSegment, routeTransitAroundHoles, legEntersRing } from './polygon-clip';

// Horizontal distance between the exit of one ordered segment and the entry of
// the next — i.e. the "deadhead" connector the vehicle flies between lines.
function connectors(ordered: ClippedSegment[]): number[] {
  const out: number[] = [];
  for (let i = 1; i < ordered.length; i++) {
    const prev = ordered[i - 1]!;
    const cur = ordered[i]!;
    out.push(Math.hypot(cur.x1 - prev.x2, cur.y - prev.y));
  }
  return out;
}

// A segment is preserved iff its (y, {min,max}x) span survives routing,
// regardless of orientation.
function spanKey(s: ClippedSegment): string {
  return `${s.y}:${Math.min(s.x1, s.x2)}:${Math.max(s.x1, s.x2)}`;
}

describe('routeScanSegments', () => {
  const SPACING = 10;

  it('serpentines a single column (alternating direction, short connectors)', () => {
    const segs: ClippedSegment[] = [];
    for (let y = 0; y <= 100; y += SPACING) segs.push({ x1: 0, x2: 100, y });

    const ordered = routeScanSegments(segs, SPACING);

    expect(ordered.length).toBe(segs.length);
    // Every connector should be roughly one line-spacing (the step up to the
    // next row), never a full traverse back across the line.
    for (const d of connectors(ordered)) {
      expect(d).toBeLessThanOrEqual(SPACING * 1.5);
    }
    // Alternating orientation is the signature of a serpentine.
    const orientations = ordered.map((s) => s.x2 > s.x1);
    for (let i = 1; i < orientations.length; i++) {
      expect(orientations[i]).not.toBe(orientations[i - 1]);
    }
  });

  it('does NOT cross the void on every row of a two-arm (U-shaped) region', () => {
    // Lower rows (single span) bridge two upper arms separated by a gap.
    const segs: ClippedSegment[] = [];
    for (let y = 0; y <= 40; y += SPACING) segs.push({ x1: 0, x2: 100, y }); // base
    for (let y = 50; y <= 100; y += SPACING) {
      segs.push({ x1: 0, x2: 30, y });   // left arm
      segs.push({ x1: 70, x2: 100, y }); // right arm
    }

    const ordered = routeScanSegments(segs, SPACING);

    // No segment is lost or duplicated.
    expect(new Set(ordered.map(spanKey))).toEqual(new Set(segs.map(spanKey)));

    // The void between the arms is ~40 wide. The buggy serpentine crossed it on
    // every one of the 6 upper rows; correct routing traverses one arm fully
    // before the other, crossing at most a couple of times.
    const voidCrossings = connectors(ordered).filter((d) => d > 40).length;
    expect(voidCrossings).toBeLessThanOrEqual(2);
  });

  it('returns input unchanged for 0 or 1 segments', () => {
    expect(routeScanSegments([], SPACING)).toEqual([]);
    const one: ClippedSegment[] = [{ x1: 0, x2: 5, y: 0 }];
    expect(routeScanSegments(one, SPACING)).toEqual(one);
  });
});

// ── Hole-aware transit routing ───────────────────────────────────────────────

const HOLE = [
  { x: 40, y: 0 }, { x: 60, y: 0 }, { x: 60, y: 100 }, { x: 40, y: 100 },
];

describe('routeTransitAroundHoles', () => {
  it('detects a leg through the slot', () => {
    expect(legEntersRing({ x: 40, y: 50 }, { x: 60, y: 50 }, HOLE)).toBe(true);
  });
  it('routes around a slot crossed mid-height', () => {
    const detour = routeTransitAroundHoles({ x: 40, y: 90 }, { x: 60, y: 90 }, [HOLE]);
    expect(detour.length).toBeGreaterThan(0);
    const path = [{ x: 40, y: 90 }, ...detour, { x: 60, y: 90 }];
    for (let i = 0; i + 1 < path.length; i++) {
      expect(legEntersRing(path[i]!, path[i + 1]!, HOLE), `subleg ${i}`).toBe(false);
    }
    expect(detour.every((p) => p.y === 100)).toBe(true);
  });
});
