/**
 * Split a survey's waypoint path into sorties (one battery per sortie).
 *
 * A large 3D survey is many batteries of flying. Rather than make the operator
 * eyeball where to break the mission, we walk the path accumulating estimated
 * flight time (leg distance / cruise speed) and start a fresh sortie whenever
 * the next leg would blow the usable-endurance budget. Each sortie is a
 * contiguous slice of the original waypoint order, so coverage stays intact and
 * the slices can be flown back-to-back.
 *
 * Pure and dependency-free so it unit-tests in plain node.
 */
import type { LatLng } from './survey-types';

const EARTH_RADIUS_M = 6_371_000;

function haversineMeters(a: LatLng, b: LatLng): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)));
}

export interface SortieSplitOptions {
  /** Hard cap on waypoints per sortie (e.g. the FC mission-item ceiling). */
  maxWaypoints?: number;
}

/**
 * Partition `waypoints` into contiguous sorties, each estimated to fit within
 * `enduranceMinutes` of flight at `speedMps`. Returns one slice when the whole
 * survey fits a single battery. Empty input yields [].
 */
export function splitIntoSorties(
  waypoints: LatLng[],
  speedMps: number,
  enduranceMinutes: number,
  opts: SortieSplitOptions = {},
): LatLng[][] {
  if (waypoints.length === 0) return [];
  const budgetSeconds = Math.max(1, enduranceMinutes) * 60;
  const speed = speedMps > 0 ? speedMps : 1;
  const maxWp = opts.maxWaypoints && opts.maxWaypoints > 0 ? opts.maxWaypoints : Infinity;

  const sorties: LatLng[][] = [];
  let current: LatLng[] = [];
  let elapsed = 0;

  for (const wp of waypoints) {
    if (current.length === 0) {
      current.push(wp);
      continue;
    }
    const legSeconds = haversineMeters(current[current.length - 1]!, wp) / speed;
    const overTime = elapsed + legSeconds > budgetSeconds;
    const overCount = current.length >= maxWp;
    // Only break if the current sortie already covers a real leg (>=2 points),
    // otherwise a single over-budget leg would orphan a lone waypoint.
    if ((overTime || overCount) && current.length >= 2) {
      sorties.push(current);
      current = [wp];
      elapsed = 0;
    } else {
      current.push(wp);
      elapsed += legSeconds;
    }
  }
  if (current.length > 0) sorties.push(current);
  return sorties;
}
