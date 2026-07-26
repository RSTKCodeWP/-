import { describe, it, expect } from "vitest";
import {
  findCollisionSegments,
  hasTerrainConflict,
  DEFAULT_MIN_TERRAIN_CLEARANCE,
} from "@/lib/terrain/terrain-clearance";

const s = (distance: number, agl: number) => ({ distance, agl });

describe("terrain-clearance", () => {
  it("returns no segments when the whole path is clear", () => {
    const samples = [s(0, 20), s(100, 30), s(200, 15)];
    expect(findCollisionSegments(samples)).toEqual([]);
    expect(hasTerrainConflict(samples)).toBe(false);
  });

  it("flags a contiguous stretch below the minimum with its distance range and lowest clearance", () => {
    // The middle of the leg dips below 5m — a ridge between two clear waypoints.
    const samples = [s(0, 20), s(100, 8), s(200, 2), s(300, -3), s(400, 6), s(500, 25)];
    const segs = findCollisionSegments(samples);
    expect(segs).toHaveLength(1);
    expect(segs[0].startDistance).toBe(200);
    expect(segs[0].endDistance).toBe(300);
    expect(segs[0].minAgl).toBe(-3);
    expect(hasTerrainConflict(samples)).toBe(true);
  });

  it("separates two distinct conflict stretches", () => {
    const samples = [s(0, 2), s(50, 10), s(100, 3), s(150, 3), s(200, 20)];
    const segs = findCollisionSegments(samples);
    expect(segs).toHaveLength(2);
    expect(segs[0]).toMatchObject({ startDistance: 0, endDistance: 0 });
    expect(segs[1]).toMatchObject({ startDistance: 100, endDistance: 150 });
  });

  it("honours a custom minimum clearance", () => {
    const samples = [s(0, 12), s(100, 8)];
    expect(findCollisionSegments(samples, 5)).toEqual([]);
    expect(findCollisionSegments(samples, 10)).toHaveLength(1);
  });

  it("closes a segment that runs to the end of the path", () => {
    const samples = [s(0, 20), s(100, 2), s(200, 1)];
    const segs = findCollisionSegments(samples);
    expect(segs).toHaveLength(1);
    expect(segs[0].endDistance).toBe(200);
  });

  it("uses a 5m default clearance", () => {
    expect(DEFAULT_MIN_TERRAIN_CLEARANCE).toBe(5);
  });
});
