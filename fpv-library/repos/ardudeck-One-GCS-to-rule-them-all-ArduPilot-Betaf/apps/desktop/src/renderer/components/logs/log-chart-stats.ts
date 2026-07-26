// Pure numeric helpers for the log chart's visible-window statistics and
// auto-ranging. Kept free of uPlot/DOM imports so they can be unit-tested and
// reused without pulling the heavy chart module.

// Shared series palette: lives here (not in the panel) so the spectrum panel
// and any future plot reuse identical colors for identical series indexes.
export const SERIES_COLORS = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
];

/** Largest index i where x[i] <= target, on an ascending array. -1 if none. */
export function lowerBoundIdx(x: ArrayLike<number>, target: number): number {
  let lo = 0;
  let hi = x.length - 1;
  let ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (x[mid]! <= target) { ans = mid; lo = mid + 1; } else { hi = mid - 1; }
  }
  return ans;
}

/** Smallest index i where x[i] >= target, on an ascending array. length if none. */
export function upperBoundIdx(x: ArrayLike<number>, target: number): number {
  let lo = 0;
  let hi = x.length - 1;
  let ans = x.length;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (x[mid]! >= target) { ans = mid; hi = mid - 1; } else { lo = mid + 1; }
  }
  return ans;
}

export interface FieldStats { min: number; avg: number; max: number; last: number; count: number }

/** min / avg / max / last of a column over inclusive index range, skipping NaN. */
export function columnStats(col: ArrayLike<number>, i0: number, i1: number): FieldStats | null {
  let min = Infinity;
  let max = -Infinity;
  let sum = 0;
  let count = 0;
  let last = NaN;
  for (let i = i0; i <= i1; i++) {
    const v = col[i]!;
    if (!Number.isFinite(v)) continue;
    if (v < min) min = v;
    if (v > max) max = v;
    sum += v;
    last = v;
    count++;
  }
  if (count === 0) return null;
  return { min, avg: sum / count, max, last, count };
}

/** Compact numeric formatting for the stats readout (adaptive precision). */
export function fmtStat(v: number): string {
  if (!Number.isFinite(v)) return '—';
  const a = Math.abs(v);
  if (a === 0) return '0';
  if (a >= 100000 || a < 0.001) return v.toExponential(1);
  if (a >= 1000) return v.toFixed(0);
  if (a >= 100) return v.toFixed(1);
  if (a >= 1) return v.toFixed(2);
  return v.toFixed(3);
}

/**
 * Padded [min, max] for a Y auto-range. A flat signal (min === max) gets a
 * symmetric band so it doesn't collapse to a zero-height line; otherwise 8%
 * headroom keeps extremes off the plot edge.
 */
export function padRange(st: FieldStats | null): [number, number] {
  if (!st) return [0, 1];
  const { min, max } = st;
  if (min === max) { const p = Math.abs(min) || 1; return [min - p * 0.1, max + p * 0.1]; }
  const pad = (max - min) * 0.08;
  return [min - pad, max + pad];
}

/**
 * CSV of chart columns over an inclusive index window. First column is time,
 * NaN cells (union-time gaps between different sample rates) become empty.
 */
export function chartCsv(
  data: ArrayLike<number>[],
  labels: string[],
  i0: number,
  i1: number,
): string {
  const esc = (s: string) => (/[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
  const lines: string[] = [['time_s', ...labels].map(esc).join(',')];
  const time = data[0]!;
  for (let i = Math.max(0, i0); i <= Math.min(i1, time.length - 1); i++) {
    const row: string[] = [String(time[i]!)];
    for (let c = 1; c < data.length; c++) {
      const v = data[c]![i]!;
      row.push(Number.isFinite(v) ? String(v) : '');
    }
    lines.push(row.join(','));
  }
  return lines.join('\n');
}
