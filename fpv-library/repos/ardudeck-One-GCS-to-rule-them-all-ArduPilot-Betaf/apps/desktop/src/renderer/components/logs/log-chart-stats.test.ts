import { describe, it, expect } from 'vitest';
import { lowerBoundIdx, upperBoundIdx, columnStats, fmtStat, padRange, chartCsv } from './log-chart-stats';

describe('lowerBoundIdx / upperBoundIdx (visible-window index resolution)', () => {
  const x = [0, 1, 2, 3, 4, 5];

  it('finds the window edges for an interior range', () => {
    // Visible window [1.5, 3.5] -> first idx >= 1.5 is 2, last idx <= 3.5 is 3.
    expect(upperBoundIdx(x, 1.5)).toBe(2);
    expect(lowerBoundIdx(x, 3.5)).toBe(3);
  });

  it('is inclusive on exact hits', () => {
    expect(upperBoundIdx(x, 2)).toBe(2);
    expect(lowerBoundIdx(x, 2)).toBe(2);
  });

  it('handles ranges past both ends', () => {
    expect(upperBoundIdx(x, -10)).toBe(0);
    expect(lowerBoundIdx(x, 99)).toBe(5);
    expect(lowerBoundIdx(x, -10)).toBe(-1); // nothing <= -10
    expect(upperBoundIdx(x, 99)).toBe(6); // nothing >= 99
  });

  it('resolves a single-sample overlap into a valid (lo <= hi) range', () => {
    const lo = upperBoundIdx(x, 2.9);
    const hi = lowerBoundIdx(x, 3.1);
    expect(lo).toBe(3);
    expect(hi).toBe(3);
    expect(hi >= lo).toBe(true);
  });
});

describe('columnStats', () => {
  it('computes min/avg/max/last over the index window, skipping NaN', () => {
    const col = [10, NaN, 20, 30, NaN];
    const s = columnStats(col, 0, 4)!;
    expect(s.min).toBe(10);
    expect(s.max).toBe(30);
    expect(s.avg).toBe(20);
    expect(s.last).toBe(30);
    expect(s.count).toBe(3);
  });

  it('honours the window bounds', () => {
    const col = [1, 2, 3, 4, 5];
    const s = columnStats(col, 1, 3)!; // 2,3,4
    expect(s.min).toBe(2);
    expect(s.max).toBe(4);
    expect(s.avg).toBe(3);
  });

  it('returns null when the window has no finite samples', () => {
    expect(columnStats([NaN, NaN], 0, 1)).toBeNull();
    expect(columnStats([1, 2, 3], 2, 1)).toBeNull(); // empty range
  });
});

describe('padRange (Y auto-range)', () => {
  it('adds 8% headroom to a normal range', () => {
    const [lo, hi] = padRange({ min: 0, max: 100, avg: 50, last: 100, count: 2 });
    expect(lo).toBeCloseTo(-8);
    expect(hi).toBeCloseTo(108);
  });

  it('gives a flat signal a symmetric non-zero band', () => {
    const [lo, hi] = padRange({ min: 5, max: 5, avg: 5, last: 5, count: 3 });
    expect(lo).toBeLessThan(5);
    expect(hi).toBeGreaterThan(5);
    expect(hi - lo).toBeGreaterThan(0);
  });

  it('falls back to [0,1] when there are no stats', () => {
    expect(padRange(null)).toEqual([0, 1]);
  });
});

describe('fmtStat (adaptive precision)', () => {
  it('scales precision to magnitude', () => {
    expect(fmtStat(0)).toBe('0');
    expect(fmtStat(0.1234)).toBe('0.123');
    expect(fmtStat(12.345)).toBe('12.35');
    expect(fmtStat(123.45)).toBe('123.5');
    expect(fmtStat(12345)).toBe('12345');
  });

  it('uses exponential for extremes and dashes non-finite', () => {
    expect(fmtStat(1e7)).toContain('e');
    expect(fmtStat(0.0001)).toContain('e');
    expect(fmtStat(NaN)).toBe('—');
    expect(fmtStat(Infinity)).toBe('—');
  });
});

describe('chartCsv', () => {
  it('exports the index window with header, blanking NaN gaps', () => {
    const csv = chartCsv(
      [[0, 1, 2, 3], [10, 11, NaN, 13], [20, 21, 22, 23]],
      ['ATT.Roll', 'ATT.Pitch'],
      1,
      2,
    );
    expect(csv).toBe('time_s,ATT.Roll,ATT.Pitch\n1,11,21\n2,,22');
  });

  it('escapes labels containing commas or quotes', () => {
    const csv = chartCsv([[0], [1]], ['a,"b"'], 0, 0);
    expect(csv.split('\n')[0]).toBe('time_s,"a,""b"""');
  });

  it('clamps the window to the data length', () => {
    const csv = chartCsv([[0, 1], [5, 6]], ['x'], -5, 99);
    expect(csv.split('\n')).toHaveLength(3);
  });
});
