import { describe, it, expect } from 'vitest';
import { remapToCanvas } from './osd-layout';

const sz = { width: 6, height: 1 };

describe('remapToCanvas', () => {
  it('keeps a top-left element at the origin', () => {
    expect(remapToCanvas({ x: 0, y: 0 }, sz, 30, 16, 50, 18)).toEqual({ x: 0, y: 0 });
  });

  it('keeps a right-edge element pinned to the right edge of the new canvas', () => {
    // x at max for 30 cols (30-6=24) -> max for 50 cols (50-6=44)
    expect(remapToCanvas({ x: 24, y: 0 }, sz, 30, 16, 50, 18).x).toBe(44);
  });

  it('keeps a bottom-edge element pinned to the bottom', () => {
    const r = remapToCanvas({ x: 0, y: 15 }, sz, 30, 16, 50, 18);
    expect(r.y).toBe(17); // 18 rows - 1 high = 17
  });

  it('spreads an interior element proportionally onto the bigger canvas', () => {
    // x=12 of 24 usable -> 0.5 -> 22 of 44 usable
    expect(remapToCanvas({ x: 12, y: 0 }, sz, 30, 16, 50, 18).x).toBe(22);
  });

  it('never exceeds the new canvas bounds', () => {
    const big = { width: 11, height: 2 };
    const r = remapToCanvas({ x: 29, y: 15 }, big, 30, 16, 50, 18);
    expect(r.x).toBeLessThanOrEqual(50 - big.width);
    expect(r.y).toBeLessThanOrEqual(18 - big.height);
  });
});
