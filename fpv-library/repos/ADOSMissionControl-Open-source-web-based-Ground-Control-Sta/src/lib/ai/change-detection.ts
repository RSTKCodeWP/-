/**
 * @module ai/change-detection
 * @description Change-detection re-fly (v1) — plan a resurvey of only the
 * subareas of an original survey that were flagged as changed.
 *
 * ## Scope (v1 = geometry only)
 * This module takes the *already-identified* changed subareas — coming from an
 * external diff, an operator's on-map selection, or a future raster
 * change-map — and clips each one to the original survey boundary. It then
 * emits a ready-to-run {@link SurveyConfig} per clipped subarea so the drone
 * re-flies ONLY those regions instead of the whole area again.
 *
 * What is intentionally OUT of scope for v1: the actual diffing that *derives*
 * the changed subareas (comparing two orthomosaics / point clouds / DSMs to
 * decide where something moved). That is a heavy raster/photogrammetry problem
 * handled by an offline processor; this module consumes its output. Feed it the
 * change polygons and it returns the flight geometry.
 *
 * The work here is pure planar polygon geometry (clip the subareas against the
 * original boundary via Sutherland–Hodgman) so it is fully unit-testable with
 * no map, store, or network access.
 *
 * @license GPL-3.0-only
 */

import type { SurveyConfig } from "@/lib/patterns/types";
import { polygonArea, isConvex } from "@/lib/drawing/geo-utils";

/** A single [lat, lon] coordinate. */
export type LatLon = [number, number];
/** A polygon ring as an ordered list of [lat, lon] vertices (unclosed). */
export type Polygon = LatLon[];

/**
 * Grid parameters applied to every per-subarea resurvey. These mirror the
 * original {@link SurveyConfig} (minus `polygon`), so a resurvey inherits the
 * same line spacing / altitude / camera cadence the first pass flew.
 */
export interface ResurveyOptions {
  /** Grid rotation angle in degrees (0 = north-south lines). */
  gridAngle: number;
  /** Distance between parallel transects in meters. */
  lineSpacing: number;
  /** Altitude AGL for generated waypoints, in meters. */
  altitude: number;
  /** Cruise speed for generated waypoints, in m/s. */
  speed: number;
  /** Overshoot past the boundary at each transect end, in meters. Default 0. */
  turnAroundDistance?: number;
  /** Bounding-box corner to start each subarea from. Default "topLeft". */
  entryLocation?: SurveyConfig["entryLocation"];
  /** Skip every other transect. Default false. */
  flyAlternateTransects?: boolean;
  /** Distance between camera triggers in meters (0 = disabled). Default 0. */
  cameraTriggerDistance?: number;
  /**
   * Drop clipped subareas smaller than this many m² as noise/slivers.
   * Default 0 (keep any subarea with positive area).
   */
  minSubareaArea?: number;
}

/** One resurvey unit: a clipped subarea plus its ready-to-run survey config. */
export interface ResurveySubarea {
  /** Index of the source subarea in the `changedSubareas` input. */
  subareaIndex: number;
  /** Clipped polygon = intersection(subarea, originalPolygon), as [lat, lon]. */
  polygon: Polygon;
  /** Area of the clipped polygon in m². */
  areaSqMeters: number;
  /** A survey grid config whose boundary is exactly the clipped polygon. */
  survey: SurveyConfig;
}

/** Result of {@link planResurvey}. */
export interface ResurveyPlan {
  /** One entry per changed subarea that intersects the original survey area. */
  subareas: ResurveySubarea[];
  /** Sum of the clipped subarea areas in m² (may double-count overlaps, v1). */
  totalAreaSqMeters: number;
  /** Area of the original survey polygon in m². */
  originalAreaSqMeters: number;
  /** Resurvey area as a fraction of the original (0..1); the flight-time win. */
  areaFraction: number;
  /** Input indices skipped: degenerate, non-intersecting, or below min area. */
  skippedSubareaIndices: number[];
}

const EPS = 1e-12;

/** Signed area (x = lon, y = lat). Positive when the ring winds CCW. */
function signedArea(ring: Polygon): number {
  let a = 0;
  for (let i = 0; i < ring.length; i++) {
    const [y1, x1] = ring[i];
    const [y2, x2] = ring[(i + 1) % ring.length];
    a += x1 * y2 - x2 * y1;
  }
  return a / 2;
}

/** Return the ring wound counter-clockwise (Sutherland–Hodgman needs a CCW clip). */
function toCcw(ring: Polygon): Polygon {
  return signedArea(ring) < 0 ? [...ring].reverse() : ring;
}

/** Remove consecutive duplicate vertices and a trailing closing duplicate. */
function cleanRing(ring: Polygon): Polygon {
  const out: Polygon = [];
  for (const p of ring) {
    const last = out[out.length - 1];
    if (!last || Math.abs(last[0] - p[0]) > EPS || Math.abs(last[1] - p[1]) > EPS) {
      out.push(p);
    }
  }
  if (out.length > 1) {
    const f = out[0];
    const l = out[out.length - 1];
    if (Math.abs(f[0] - l[0]) < EPS && Math.abs(f[1] - l[1]) < EPS) out.pop();
  }
  return out;
}

/** Half-plane test for a CCW clip edge a→b: p is "inside" when it is left of a→b. */
function insideEdge(a: LatLon, b: LatLon, p: LatLon): boolean {
  const cross = (b[1] - a[1]) * (p[0] - a[0]) - (b[0] - a[0]) * (p[1] - a[1]);
  return cross >= -EPS;
}

/** Intersection of segment p1→p2 with the infinite line through a→b. */
function segIntersect(p1: LatLon, p2: LatLon, a: LatLon, b: LatLon): LatLon {
  const x1 = p1[1];
  const y1 = p1[0];
  const x2 = p2[1];
  const y2 = p2[0];
  const x3 = a[1];
  const y3 = a[0];
  const x4 = b[1];
  const y4 = b[0];
  const denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4);
  if (Math.abs(denom) < EPS) return p2;
  const t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom;
  return [y1 + t * (y2 - y1), x1 + t * (x2 - x1)];
}

/**
 * Clip the `subject` polygon by the `clip` polygon (Sutherland–Hodgman).
 * The `clip` polygon is treated as the clip window and MUST be convex for a
 * correct result; the caller picks the convex operand. Returns the intersection
 * ring (possibly empty) with duplicate vertices removed.
 */
function clipPolygon(subject: Polygon, clip: Polygon): Polygon {
  const window = toCcw(clip);
  let output: Polygon = subject;
  for (let i = 0; i < window.length && output.length > 0; i++) {
    const a = window[i];
    const b = window[(i + 1) % window.length];
    const input = output;
    output = [];
    for (let j = 0; j < input.length; j++) {
      const cur = input[j];
      const prev = input[(j - 1 + input.length) % input.length];
      const curIn = insideEdge(a, b, cur);
      const prevIn = insideEdge(a, b, prev);
      if (curIn) {
        if (!prevIn) output.push(segIntersect(prev, cur, a, b));
        output.push(cur);
      } else if (prevIn) {
        output.push(segIntersect(prev, cur, a, b));
      }
    }
  }
  return cleanRing(output);
}

/**
 * Intersect two polygons. Sutherland–Hodgman only clips correctly against a
 * convex window, so pick whichever operand is convex as the window. If both are
 * concave, fall back to clipping the subarea by the original (best-effort) —
 * documented v1 limitation; feed convex/simple change polygons for exact cuts.
 */
function intersectPolygons(subarea: Polygon, original: Polygon): Polygon {
  if (isConvex(original)) return clipPolygon(subarea, original);
  if (isConvex(subarea)) return clipPolygon(original, subarea);
  return clipPolygon(subarea, original);
}

/** Build a SurveyConfig for a clipped subarea, inheriting the grid options. */
function buildSurvey(polygon: Polygon, o: ResurveyOptions): SurveyConfig {
  return {
    polygon,
    gridAngle: o.gridAngle,
    lineSpacing: o.lineSpacing,
    turnAroundDistance: o.turnAroundDistance ?? 0,
    entryLocation: o.entryLocation ?? "topLeft",
    flyAlternateTransects: o.flyAlternateTransects ?? false,
    cameraTriggerDistance: o.cameraTriggerDistance ?? 0,
    altitude: o.altitude,
    speed: o.speed,
  };
}

/**
 * Plan a resurvey covering only the changed subareas of an original survey.
 *
 * Each changed subarea is intersected with the original survey boundary (so a
 * subarea that spills outside the original is trimmed, and one fully outside is
 * dropped). Every surviving intersection becomes its own {@link SurveyConfig}
 * with the boundary set to the clipped polygon and the grid parameters copied
 * from `options`.
 *
 * @param originalSurveyPolygon The boundary of the original survey, [lat, lon].
 * @param changedSubareas       Polygons flagged as changed, each [lat, lon].
 * @param options               Grid parameters inherited by each resurvey.
 * @returns A {@link ResurveyPlan}; `subareas` is empty when nothing overlaps.
 */
export function planResurvey(
  originalSurveyPolygon: Polygon,
  changedSubareas: Polygon[],
  options: ResurveyOptions,
): ResurveyPlan {
  const original = cleanRing(originalSurveyPolygon);
  const originalArea = polygonArea(original);
  const minArea = Math.max(0, options.minSubareaArea ?? 0);

  const subareas: ResurveySubarea[] = [];
  const skipped: number[] = [];

  if (original.length < 3) {
    return {
      subareas: [],
      totalAreaSqMeters: 0,
      originalAreaSqMeters: originalArea,
      areaFraction: 0,
      skippedSubareaIndices: changedSubareas.map((_, i) => i),
    };
  }

  changedSubareas.forEach((raw, index) => {
    const sub = cleanRing(raw);
    if (sub.length < 3) {
      skipped.push(index);
      return;
    }

    const clipped = intersectPolygons(sub, original);
    const area = polygonArea(clipped);
    if (clipped.length < 3 || area <= minArea) {
      skipped.push(index);
      return;
    }

    subareas.push({
      subareaIndex: index,
      polygon: clipped,
      areaSqMeters: area,
      survey: buildSurvey(clipped, options),
    });
  });

  const totalArea = subareas.reduce((s, a) => s + a.areaSqMeters, 0);
  return {
    subareas,
    totalAreaSqMeters: totalArea,
    originalAreaSqMeters: originalArea,
    areaFraction: originalArea > 0 ? totalArea / originalArea : 0,
    skippedSubareaIndices: skipped,
  };
}
