/* Display formatters — ONE canonical format per quantity, used identically everywhere
 * (DESIGN-SYSTEM anti-slop #3). Coordinate formatters (MGRS primary, WGS84 DDM secondary)
 * live with the detail panel; these are the time/age formats shared across surfaces. */

const pad2 = (n: number): string => String(n).padStart(2, "0");

/** UTC clock as HH:MM:SSZ (the strip's single time format). */
export function formatUtcClock(d: Date): string {
  return `${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}:${pad2(d.getUTCSeconds())}Z`;
}

/** Compact age as M:SS (e.g. 0:03, 2:18). Floors fractional seconds. */
export function formatAge(seconds: number): string {
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${pad2(s)}`;
}
