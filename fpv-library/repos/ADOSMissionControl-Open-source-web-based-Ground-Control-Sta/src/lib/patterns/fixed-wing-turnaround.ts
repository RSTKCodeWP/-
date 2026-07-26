/**
 * @module fixed-wing-turnaround
 * @description Fixed-wing turnaround geometry for survey (lawnmower) missions.
 *
 * A fixed-wing aircraft cannot pivot on the spot, so at the end of every survey
 * transect it must fly a coordinated turn to reverse direction and line up on the
 * adjacent line. This module computes the minimum coordinated-turn radius from
 * airspeed and bank limit, the straight extension each line needs past the survey
 * boundary so the turn fits, and whether the configured line spacing is too tight
 * for a simple adjacent-line U-turn.
 *
 * Pure geometry/physics only. No React, store, or map imports.
 * @license GPL-3.0-only
 */

/**
 * Standard gravitational acceleration in m/s^2. Used to convert a coordinated
 * bank angle and airspeed into a turn radius. Kept as a named constant instead
 * of an inline literal so the physics is legible at the call site.
 */
export const GRAVITY_MPS2 = 9.80665;

/**
 * Minimum radius of a level coordinated turn.
 *
 * r = v^2 / (g * tan(bank))
 *
 * A steeper bank tightens the turn; a faster airspeed widens it. At zero bank the
 * aircraft flies straight (infinite radius); at 90 deg bank the level-turn model
 * degenerates (infinite load factor) so the radius collapses to zero and the
 * result is clamped rather than divided by an unbounded tangent.
 *
 * @param speedMps   True airspeed in m/s (cruise/survey speed).
 * @param maxBankDeg Maximum usable bank angle in degrees.
 * @returns Minimum turn radius in meters. `Infinity` when the aircraft cannot
 *          turn (bank <= 0), `0` for degenerate inputs (speed <= 0, bank >= 90).
 */
export function minTurnRadius(speedMps: number, maxBankDeg: number): number {
  if (!(speedMps > 0)) return 0;
  if (!(maxBankDeg > 0)) return Infinity;
  if (maxBankDeg >= 90) return 0;
  const bankRad = (maxBankDeg * Math.PI) / 180;
  return (speedMps * speedMps) / (GRAVITY_MPS2 * Math.tan(bankRad));
}

/**
 * Straight-line extension each survey transect needs past the mapping boundary so
 * a 180 deg turnaround completes clear of the capture area.
 *
 * For the standard semicircular U-turn the arc bulges out beyond the line end by
 * exactly one turn radius (the apex of the semicircle sits `r` past the point
 * where the arc begins). So the lead-out (and matching lead-in on the return leg)
 * is modeled as one turn radius. This is the extension a planner adds to both ends
 * of every line before laying out the transects.
 *
 * @param radius Minimum turn radius in meters (from {@link minTurnRadius}).
 * @returns Extension distance in meters. `0` for non-positive or NaN radius;
 *          `Infinity` propagates when the aircraft cannot turn at all.
 */
export function turnaroundExtension(radius: number): number {
  if (!(radius > 0)) return 0;
  return radius;
}

/**
 * Whether the configured line spacing is too tight for a simple adjacent-line
 * U-turn. A semicircular U-turn of radius `r` displaces the aircraft `2r`
 * laterally, so it only fits when the spacing is at least `2r`. When the spacing
 * is smaller the planner must use a wider maneuver (skip-line / racetrack
 * ordering) instead of turning straight onto the neighbouring line.
 *
 * @param lineSpacing Perpendicular distance between adjacent transects in meters.
 * @param radius      Minimum turn radius in meters (from {@link minTurnRadius}).
 * @returns `true` when `lineSpacing < 2 * radius` (U-turn will not fit),
 *          `false` when it fits or for degenerate inputs.
 */
export function needsTurnaround(lineSpacing: number, radius: number): boolean {
  if (!(radius > 0) || !(lineSpacing > 0)) return false;
  return lineSpacing < 2 * radius;
}
