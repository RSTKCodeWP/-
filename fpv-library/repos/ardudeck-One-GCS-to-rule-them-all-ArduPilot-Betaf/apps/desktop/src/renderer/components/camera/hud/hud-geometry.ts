/**
 * Pure geometry for the synthetic HUD overlay.
 *
 * All helpers return normalized offsets in [-1, 1] relative to the visible
 * field-of-view band, so the SVG layer can map them onto any frame size with a
 * single multiply. No DOM, no telemetry plumbing — just math, so it's testable.
 */

/** Wrap an angle to (-180, 180]. */
export function wrap180(deg: number): number {
  let d = ((deg + 180) % 360 + 360) % 360 - 180;
  if (d === -180) d = 180;
  return d;
}

export interface HeadingTick {
  /** Compass heading this tick represents, 0..359. */
  deg: number;
  /** Horizontal position, -1 (left edge of band) .. 1 (right edge). */
  norm: number;
  /** Cardinal label (N/E/S/W) or undefined. */
  cardinal?: string;
  /** True for the labelled major ticks (every `labelEvery` degrees). */
  major: boolean;
}

const CARDINALS: Record<number, string> = { 0: 'N', 90: 'E', 180: 'S', 270: 'W' };

/**
 * Visible heading-tape ticks for a compass band `halfSpanDeg` wide on each side
 * of the current heading.
 */
export function headingTicks(
  heading: number,
  halfSpanDeg: number,
  stepDeg = 5,
  labelEvery = 15,
): HeadingTick[] {
  const ticks: HeadingTick[] = [];
  const start = Math.ceil((heading - halfSpanDeg) / stepDeg) * stepDeg;
  for (let d = start; d <= heading + halfSpanDeg; d += stepDeg) {
    const norm = wrap180(d - heading) / halfSpanDeg;
    if (norm < -1 || norm > 1) continue;
    const deg = ((d % 360) + 360) % 360;
    const major = deg % labelEvery === 0;
    ticks.push({ deg, norm, cardinal: CARDINALS[deg], major });
  }
  return ticks;
}

export interface TapeTick {
  value: number;
  /** Vertical position, -1 (top of band) .. 1 (bottom). Higher value = toward top. */
  norm: number;
  major: boolean;
}

/**
 * Visible ticks for a vertical scrolling tape (airspeed, altitude). Higher
 * values sit toward the top (norm negative).
 */
export function verticalTapeTicks(
  value: number,
  halfSpanUnits: number,
  stepMinor: number,
  stepMajor: number,
): TapeTick[] {
  const ticks: TapeTick[] = [];
  const start = Math.ceil((value - halfSpanUnits) / stepMinor) * stepMinor;
  for (let v = start; v <= value + halfSpanUnits; v += stepMinor) {
    const norm = (value - v) / halfSpanUnits; // v>value -> negative -> up
    if (norm < -1 || norm > 1) continue;
    // Use rounding to avoid float drift when testing modulo for majors.
    const major = Math.abs(Math.round(v) % stepMajor) === 0;
    ticks.push({ value: Math.round(v * 100) / 100, norm, major });
  }
  return ticks;
}

export interface LadderRung {
  /** Pitch angle in degrees (… -10, -5, 0, 5, 10 …). */
  deg: number;
  /** Vertical offset, -1 (top) .. 1 (bottom). Climb (positive pitch) is up. */
  norm: number;
}

/**
 * Visible pitch-ladder rungs within `halfSpanDeg` of the current pitch.
 * Positive pitch (climb) yields a negative norm (drawn above the boresight).
 */
export function pitchLadderRungs(pitch: number, halfSpanDeg: number, stepDeg = 5): LadderRung[] {
  const rungs: LadderRung[] = [];
  const start = Math.ceil((pitch - halfSpanDeg) / stepDeg) * stepDeg;
  for (let p = start; p <= pitch + halfSpanDeg; p += stepDeg) {
    if (p < -90 || p > 90) continue;
    const norm = (pitch - p) / halfSpanDeg; // p>pitch -> negative -> up
    if (norm < -1 || norm > 1) continue;
    rungs.push({ deg: p, norm });
  }
  return rungs;
}
