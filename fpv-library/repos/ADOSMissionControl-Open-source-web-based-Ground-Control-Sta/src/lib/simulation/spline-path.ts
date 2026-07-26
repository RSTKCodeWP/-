/**
 * @module simulation/spline-path
 * @description Catmull-Rom corner rounding for the mission simulation display.
 *
 * VISUALIZATION AID ONLY. The flight controller flies straight legs between
 * waypoints (a smoothed cornering path is followed only for waypoints whose
 * command is SPLINE_WAYPOINT). This module produces a rounded polyline purely
 * so the simulated flight path can be drawn with soft turns instead of hard
 * corners. It never changes the mission, the uploaded waypoints, or the timing
 * used by the simulator — it is a rendering convenience and is off by default.
 * @license GPL-3.0-only
 */

/** Minimal 3D point used by the spline math. Lon/lat degrees, alt meters. */
export interface SplinePoint {
  lat: number;
  lon: number;
  alt: number;
}

/** Anything with lat/lon/alt can seed the path (e.g. a mission Waypoint). */
export interface LatLonAlt {
  lat: number;
  lon: number;
  alt: number;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * Uniform Catmull-Rom interpolation of a single scalar channel.
 *
 * The curve passes through p1 (t=0) and p2 (t=1); p0 and p3 shape the tangents
 * at each end. The basis is a partition of unity (coefficients sum to 1), so the
 * interpolation commutes with affine maps — a collinear set of control points
 * yields a collinear result.
 */
function catmullRomScalar(
  p0: number,
  p1: number,
  p2: number,
  p3: number,
  t: number,
): number {
  const t2 = t * t;
  const t3 = t2 * t;
  return (
    0.5 *
    (2 * p1 +
      (-p0 + p2) * t +
      (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
      (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
  );
}

/**
 * Uniform Catmull-Rom interpolation of a 3D point.
 *
 * Interpolates the segment p1 -> p2, using p0 and p3 as the neighbouring
 * control points that set the tangents. `t` in [0, 1]: 0 returns p1 exactly,
 * 1 returns p2 exactly.
 */
export function catmullRomPoint(
  p0: SplinePoint,
  p1: SplinePoint,
  p2: SplinePoint,
  p3: SplinePoint,
  t: number,
): SplinePoint {
  const clamped = clamp(t, 0, 1);
  return {
    lat: catmullRomScalar(p0.lat, p1.lat, p2.lat, p3.lat, clamped),
    lon: catmullRomScalar(p0.lon, p1.lon, p2.lon, p3.lon, clamped),
    alt: catmullRomScalar(p0.alt, p1.alt, p2.alt, p3.alt, clamped),
  };
}

function toPoint(w: LatLonAlt): SplinePoint {
  return { lat: w.lat, lon: w.lon, alt: w.alt };
}

function lerpPoint(a: SplinePoint, b: SplinePoint, t: number): SplinePoint {
  return {
    lat: a.lat + (b.lat - a.lat) * t,
    lon: a.lon + (b.lon - a.lon) * t,
    alt: a.alt + (b.alt - a.alt) * t,
  };
}

/**
 * Produce a densified, corner-rounded polyline through the given waypoints, for
 * drawing the simulated flight path only.
 *
 * The result passes through every input waypoint exactly (each segment starts on
 * its waypoint and the final waypoint is appended), so no distance or timing is
 * implied by the extra vertices. Between waypoints, each sample blends the
 * straight-line position with the Catmull-Rom position by `tension`:
 *
 *   - tension = 0  -> the straight-line path (no rounding; densified legs)
 *   - tension = 1  -> full Catmull-Rom rounding at the corners
 *
 * Endpoints are clamped (the first and last waypoints are duplicated as the
 * missing neighbours) so the path stays anchored at both ends. Fewer than two
 * waypoints cannot be smoothed and are returned as plain points.
 *
 * @param waypoints ordered path vertices (lat/lon/alt)
 * @param tension rounding strength in [0, 1] (values outside are clamped)
 * @param samplesPerSeg vertices emitted per segment (clamped to >= 1)
 */
export function roundCorners(
  waypoints: readonly LatLonAlt[],
  tension: number,
  samplesPerSeg: number,
): SplinePoint[] {
  if (waypoints.length < 2) {
    return waypoints.map(toPoint);
  }

  const t = clamp(tension, 0, 1);
  const samples = Math.max(1, Math.floor(samplesPerSeg));
  const pts = waypoints.map(toPoint);
  const last = pts.length - 1;
  const out: SplinePoint[] = [];

  for (let i = 0; i < last; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(last, i + 2)];

    // Emit t in [0, 1) for this segment; the final vertex is appended once
    // after the loop so shared segment boundaries are not duplicated.
    for (let s = 0; s < samples; s++) {
      const localT = s / samples;
      const straight = lerpPoint(p1, p2, localT);
      if (t === 0) {
        out.push(straight);
        continue;
      }
      const curved = catmullRomPoint(p0, p1, p2, p3, localT);
      out.push(lerpPoint(straight, curved, t));
    }
  }

  out.push(pts[last]);
  return out;
}
