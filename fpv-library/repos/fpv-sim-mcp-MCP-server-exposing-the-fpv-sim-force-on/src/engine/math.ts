/*
 * Geometry and formatting helpers, ported verbatim from fpv-sim index.html.
 * Expression order is preserved so floating-point results are bit-identical
 * with the browser version.
 */

export const clamp = (v: number, a: number, b: number): number => Math.max(a, Math.min(b, v));
export const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;
export const smooth01 = (t: number): number => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); };
export const d2r = (d: number): number => d * Math.PI / 180;
export const r2d = (r: number): number => r * 180 / Math.PI;
export const dist = (ax: number, ay: number, bx: number, by: number): number => Math.hypot(bx - ax, by - ay);
// Bearing in radians, true north = 0, clockwise positive.
export const brgTo = (ax: number, ay: number, bx: number, by: number): number => Math.atan2(bx - ax, by - ay);
export const normAng = (a: number): number => { while (a > Math.PI) a -= 2 * Math.PI; while (a < -Math.PI) a += 2 * Math.PI; return a; };
export const pad4 = (n: number): string => String(Math.max(0, Math.min(9999, Math.round(n)))).padStart(4, "0");
export const gridRef = (x: number, y: number): string => "GRID " + pad4(x / 10) + " " + pad4(y / 10);
export const fmtT = (t: number): string => {
  const s = Math.floor(t);
  return "T+" + String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
};

export function distToSeg(px: number, py: number, ax: number, ay: number, bx: number, by: number): number {
  const dx = bx - ax, dy = by - ay;
  const L2 = dx * dx + dy * dy;
  let t = L2 ? ((px - ax) * dx + (py - ay) * dy) / L2 : 0;
  t = clamp(t, 0, 1);
  return Math.hypot(px - (ax + dx * t), py - (ay + dy * t));
}
