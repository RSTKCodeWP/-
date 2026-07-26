import { describe, it, expect } from 'vitest';
import { wrap180, headingTicks, verticalTapeTicks, pitchLadderRungs } from './hud-geometry';

describe('wrap180', () => {
  it('wraps into (-180, 180]', () => {
    expect(wrap180(0)).toBe(0);
    expect(wrap180(190)).toBe(-170);
    expect(wrap180(-190)).toBe(170);
    expect(wrap180(360)).toBe(0);
    expect(wrap180(540)).toBe(180);
  });
});

describe('headingTicks', () => {
  it('centers the current heading at norm 0 and labels cardinals', () => {
    const ticks = headingTicks(90, 30, 5, 15);
    const center = ticks.find((t) => t.deg === 90);
    expect(center?.norm).toBeCloseTo(0, 6);
    expect(center?.cardinal).toBe('E');
    // all within band
    expect(ticks.every((t) => t.norm >= -1 && t.norm <= 1)).toBe(true);
  });

  it('handles wraparound near north', () => {
    const ticks = headingTicks(5, 20, 5, 15);
    const north = ticks.find((t) => t.deg === 0);
    expect(north).toBeTruthy();
    expect(north?.cardinal).toBe('N');
    expect(north?.norm).toBeCloseTo(-5 / 20, 6); // 0 is 5deg left of heading 5
  });
});

describe('verticalTapeTicks', () => {
  it('puts higher values toward the top (negative norm)', () => {
    const ticks = verticalTapeTicks(100, 50, 10, 50);
    const above = ticks.find((t) => t.value === 120);
    const below = ticks.find((t) => t.value === 80);
    expect(above!.norm).toBeLessThan(0);
    expect(below!.norm).toBeGreaterThan(0);
    expect(ticks.every((t) => t.norm >= -1 && t.norm <= 1)).toBe(true);
  });

  it('marks majors on the major step', () => {
    const ticks = verticalTapeTicks(100, 50, 10, 50);
    expect(ticks.find((t) => t.value === 100)?.major).toBe(true);
    expect(ticks.find((t) => t.value === 150)?.major).toBe(true);
    expect(ticks.find((t) => t.value === 110)?.major).toBe(false);
  });
});

describe('pitchLadderRungs', () => {
  it('climb (positive pitch above) maps to negative norm', () => {
    const rungs = pitchLadderRungs(0, 20, 5);
    expect(rungs.find((r) => r.deg === 0)?.norm).toBeCloseTo(0, 6);
    expect(rungs.find((r) => r.deg === 10)!.norm).toBeLessThan(0);
    expect(rungs.find((r) => r.deg === -10)!.norm).toBeGreaterThan(0);
  });

  it('clamps to the visible band and never exceeds ±90 pitch', () => {
    const rungs = pitchLadderRungs(85, 20, 5);
    expect(rungs.every((r) => r.deg <= 90)).toBe(true);
    expect(rungs.every((r) => r.norm >= -1 && r.norm <= 1)).toBe(true);
  });
});
