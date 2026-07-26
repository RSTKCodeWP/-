/**
 * Compute a destination lat/lon given an origin, a true-north bearing (degrees)
 * and a distance (meters). Uses the spherical great-circle destination formula.
 */
const EARTH_RADIUS_M = 6371000;
const DEG_TO_RAD = Math.PI / 180;
const RAD_TO_DEG = 180 / Math.PI;

export function computeOffsetPosition(
  originLat: number,
  originLon: number,
  bearingDeg: number,
  distanceM: number,
): { lat: number; lon: number } {
  const angularDist = distanceM / EARTH_RADIUS_M;
  const bearing = bearingDeg * DEG_TO_RAD;
  const lat1 = originLat * DEG_TO_RAD;
  const lon1 = originLon * DEG_TO_RAD;

  const sinLat1 = Math.sin(lat1);
  const cosLat1 = Math.cos(lat1);
  const sinAng = Math.sin(angularDist);
  const cosAng = Math.cos(angularDist);

  const sinLat2 = sinLat1 * cosAng + cosLat1 * sinAng * Math.cos(bearing);
  const lat2 = Math.asin(sinLat2);
  const lon2 =
    lon1 +
    Math.atan2(
      Math.sin(bearing) * sinAng * cosLat1,
      cosAng - sinLat1 * sinLat2,
    );

  // Normalize longitude to [-180, 180]
  const lonDeg = ((lon2 * RAD_TO_DEG + 540) % 360) - 180;

  return { lat: lat2 * RAD_TO_DEG, lon: lonDeg };
}
