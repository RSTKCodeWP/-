/**
 * @module patterns/coverage
 * @description Survey footprint and coverage-statistics computation for
 * photogrammetry / mapping missions.
 *
 * Given a survey flight route (ordered waypoints), a camera profile, and the
 * flight altitude, this module estimates:
 *   - the ground footprint of a single image (delegates to gsd-calculator),
 *   - the perpendicular spacing between adjacent flight lines,
 *   - the along-track spacing between consecutive captures,
 *   - front/side overlap percentages implied by those spacings,
 *   - the total swept ground coverage,
 *   - and a simple coverage-gap flag when the line spacing is too wide to
 *     maintain a target side overlap.
 *
 * All functions here are pure (no React / store / Leaflet imports) so they are
 * fully unit-testable. Overlap figures are ESTIMATES derived from the route
 * geometry: they are most accurate when the route waypoints are the actual
 * image-capture points, and degrade gracefully (under-reporting front overlap)
 * when the route is only the transect endpoints.
 *
 * @license GPL-3.0-only
 */

import type { Waypoint } from "@/lib/types";
import { haversineDistance } from "@/lib/telemetry-utils";
import type { CameraProfile } from "./gsd-calculator";
import { computeFootprint } from "./gsd-calculator";

// Re-export so callers get a single, gsd-consistent footprint function.
export { computeFootprint };
export type { CameraProfile };

/** Minimal geographic point accepted by the coverage functions. */
export type SurveyPoint = Readonly<Pick<Waypoint, "lat" | "lon">>;

/** Aggregate coverage statistics for a survey route. */
export interface CoverageStats {
  /** Number of capture/route waypoints (one footprint per waypoint). */
  imageCount: number;
  /**
   * Total ground area swept by the camera footprint along all flight lines,
   * in square meters. Per-line swaths are summed; adjacent-line sidelap
   * double-coverage is NOT subtracted, so this is an upper bound on unique area.
   */
  groundCoverageM2: number;
  /** Estimated forward (along-track) overlap, 0-100 %. */
  overlapFrontPct: number;
  /** Estimated side (across-track) overlap, 0-100 %. */
  overlapSidePct: number;
  /** Estimated perpendicular spacing between adjacent flight lines, meters. */
  lineSpacingM: number;
  /** Estimated spacing between consecutive along-track captures, meters. */
  alongTrackSpacingM: number;
  /** Single-image ground footprint width (across-track), meters. */
  footprintWidthM: number;
  /** Single-image ground footprint height (along-track), meters. */
  footprintHeightM: number;
}

/** Result of a coverage-gap check against a target side overlap. */
export interface CoverageGapResult {
  /** True when the estimated line spacing is too wide for the target overlap. */
  hasGap: boolean;
  /** Estimated perpendicular spacing between flight lines, meters. */
  lineSpacingM: number;
  /** Widest line spacing that still meets the target side overlap, meters. */
  maxSpacingForOverlapM: number;
  /** Amount the line spacing exceeds the allowed maximum (0 when no gap). */
  deficitM: number;
}

const DEG_TO_RAD = Math.PI / 180;
const EARTH_R = 6371000;
// Segments within ~45 deg of the dominant flight heading count as along-track;
// steeper ones count as cross (line-to-line) hops. cos(45 deg).
const ALONG_TRACK_COS = Math.SQRT1_2;

function clamp01(x: number): number {
  return Math.min(1, Math.max(0, x));
}

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

/** Keep only points with finite coordinates. */
function finitePoints(points: readonly SurveyPoint[]): SurveyPoint[] {
  return points.filter(
    (p) => Number.isFinite(p.lat) && Number.isFinite(p.lon),
  );
}

/** Equirectangular projection to local meters around a reference point. */
function toLocalXY(
  lat: number,
  lon: number,
  refLat: number,
  refLon: number,
  cosRef: number,
): [number, number] {
  return [
    (lon - refLon) * DEG_TO_RAD * EARTH_R * cosRef,
    (lat - refLat) * DEG_TO_RAD * EARTH_R,
  ];
}

interface RouteAnalysis {
  /** Estimated perpendicular spacing between flight lines, meters. */
  lineSpacingM: number;
  /** Estimated spacing between consecutive along-track captures, meters. */
  alongTrackSpacingM: number;
  /** Sum of along-track leg lengths, meters. */
  alongTrackTotalM: number;
}

/**
 * Analyse a survey route into its characteristic spacings.
 *
 * Consecutive segments are classified as along-track or cross (line-to-line)
 * by comparing their heading to the dominant flight axis. That axis is the
 * length-weighted principal orientation of all segments (a doubled-angle mean,
 * the correct average for undirected line orientations), so many short capture
 * legs correctly outweigh a few longer line-to-line hops. The along-track leg
 * lengths give the capture spacing; the cross leg lengths give the flight-line
 * spacing. Medians are used so a few entry/exit or overshoot legs do not skew
 * the estimate.
 */
function analyzeRoute(points: readonly SurveyPoint[]): RouteAnalysis {
  const pts = finitePoints(points);
  if (pts.length < 2) {
    return { lineSpacingM: 0, alongTrackSpacingM: 0, alongTrackTotalM: 0 };
  }

  const refLat = pts[0].lat;
  const refLon = pts[0].lon;
  const cosRef = Math.cos(refLat * DEG_TO_RAD);

  const xy = pts.map((p) => toLocalXY(p.lat, p.lon, refLat, refLon, cosRef));

  interface Seg {
    length: number;
    ux: number;
    uy: number;
  }
  const segs: Seg[] = [];
  for (let i = 1; i < pts.length; i++) {
    const length = haversineDistance(
      pts[i - 1].lat,
      pts[i - 1].lon,
      pts[i].lat,
      pts[i].lon,
    );
    const dx = xy[i][0] - xy[i - 1][0];
    const dy = xy[i][1] - xy[i - 1][1];
    const mag = Math.hypot(dx, dy);
    if (length <= 0 || mag <= 0) continue; // skip duplicate / degenerate points
    segs.push({ length, ux: dx / mag, uy: dy / mag });
  }

  if (segs.length === 0) {
    return { lineSpacingM: 0, alongTrackSpacingM: 0, alongTrackTotalM: 0 };
  }

  // Dominant flight axis = length-weighted principal orientation. Accumulate
  // doubled-angle vectors so opposite directions (a boustrophedon flying east
  // then west) reinforce rather than cancel: cos(2t)=ux^2-uy^2, sin(2t)=2*ux*uy.
  let sum2x = 0;
  let sum2y = 0;
  for (const s of segs) {
    sum2x += s.length * (s.ux * s.ux - s.uy * s.uy);
    sum2y += s.length * (2 * s.ux * s.uy);
  }
  const axis = 0.5 * Math.atan2(sum2y, sum2x);
  const domUx = Math.cos(axis);
  const domUy = Math.sin(axis);

  const alongLengths: number[] = [];
  const crossLengths: number[] = [];
  for (const s of segs) {
    const cos = Math.abs(s.ux * domUx + s.uy * domUy);
    if (cos >= ALONG_TRACK_COS) alongLengths.push(s.length);
    else crossLengths.push(s.length);
  }

  const alongTrackTotalM = alongLengths.reduce((a, b) => a + b, 0);
  return {
    lineSpacingM: median(crossLengths),
    alongTrackSpacingM: median(alongLengths),
    alongTrackTotalM,
  };
}

/**
 * Estimate the perpendicular spacing between adjacent flight lines for a
 * survey route, in meters. Returns 0 for a single-line or empty route.
 */
export function estimateLineSpacingM(points: readonly SurveyPoint[]): number {
  return analyzeRoute(points).lineSpacingM;
}

/**
 * Compute aggregate coverage statistics for a survey route.
 *
 * @param surveyWaypoints Ordered survey route waypoints (capture or transect points).
 * @param camera          Camera sensor/lens profile.
 * @param altitudeM       Flight altitude above ground, meters.
 * @returns Coverage statistics (see {@link CoverageStats}).
 */
export function computeCoverageStats(
  surveyWaypoints: readonly SurveyPoint[],
  camera: CameraProfile,
  altitudeM: number,
): CoverageStats {
  const footprint = computeFootprint(altitudeM, camera);
  const pts = finitePoints(surveyWaypoints);
  const { lineSpacingM, alongTrackSpacingM, alongTrackTotalM } =
    analyzeRoute(surveyWaypoints);

  const overlapSidePct =
    footprint.width > 0 && lineSpacingM > 0
      ? clamp01(1 - lineSpacingM / footprint.width) * 100
      : 0;
  const overlapFrontPct =
    footprint.height > 0 && alongTrackSpacingM > 0
      ? clamp01(1 - alongTrackSpacingM / footprint.height) * 100
      : 0;

  // Swept swath = along-track distance flown x footprint width.
  const groundCoverageM2 = alongTrackTotalM * footprint.width;

  return {
    imageCount: pts.length,
    groundCoverageM2,
    overlapFrontPct,
    overlapSidePct,
    lineSpacingM,
    alongTrackSpacingM,
    footprintWidthM: footprint.width,
    footprintHeightM: footprint.height,
  };
}

/**
 * Detect a coverage gap: flags when the estimated line spacing is wider than a
 * target side overlap allows. The widest spacing that still meets the target is
 * `footprintWidth * (1 - minSideOverlap)`.
 *
 * @param surveyWaypoints Ordered survey route waypoints.
 * @param camera          Camera sensor/lens profile.
 * @param altitudeM       Flight altitude above ground, meters.
 * @param minSideOverlap  Target side overlap as a fraction 0-1 (default 0.6).
 * @returns Gap result (see {@link CoverageGapResult}).
 */
export function detectCoverageGaps(
  surveyWaypoints: readonly SurveyPoint[],
  camera: CameraProfile,
  altitudeM: number,
  minSideOverlap = 0.6,
): CoverageGapResult {
  const footprint = computeFootprint(altitudeM, camera);
  const lineSpacingM = estimateLineSpacingM(surveyWaypoints);
  const overlap = clamp01(minSideOverlap);
  const maxSpacingForOverlapM = footprint.width * (1 - overlap);

  // No second line (spacing 0) or no footprint => nothing to flag.
  const hasGap =
    lineSpacingM > 0 &&
    footprint.width > 0 &&
    lineSpacingM > maxSpacingForOverlapM;

  return {
    hasGap,
    lineSpacingM,
    maxSpacingForOverlapM,
    deficitM: hasGap ? lineSpacingM - maxSpacingForOverlapM : 0,
  };
}
