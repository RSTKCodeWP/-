/**
 * Pixel -> ground geolocation for the camera feed.
 *
 * Given the vehicle pose, the gimbal pointing angles and the camera field of
 * view, projects a normalized pixel (where the operator clicked, or the frame
 * center) onto the ground and returns its lat/lon. This is what makes
 * click-on-video-to-point and the frame-center coordinate readout trustworthy.
 *
 * v1 uses a flat-earth intersection at a fixed ground elevation (the vehicle's
 * home/launch altitude by default). The signature accepts a `groundElevationM`
 * so a DEM/terrain ray-cast can be layered in later without touching callers —
 * pass the terrain height under the camera and the math is unchanged.
 *
 * Returns null when the ray points at or above the horizon (no ground hit).
 */

export interface CameraPose {
  /** Vehicle position. */
  lat: number;
  lon: number;
  /** Vehicle altitude AMSL in metres. */
  altMslM: number;
  /** Camera bearing (deg, 0=N, CW). Usually vehicleYaw + gimbalYaw. */
  bearingDeg: number;
  /** Camera depression below horizon (deg, positive = looking down). */
  pitchDownDeg: number;
  /** Horizontal field of view in degrees. */
  hfovDeg: number;
  /** Vertical field of view in degrees. */
  vfovDeg: number;
}

export interface GeoPoint {
  lat: number;
  lon: number;
  /** Slant range from camera to the point, metres. */
  slantRangeM: number;
}

const DEG = Math.PI / 180;
const EARTH_R = 6378137; // WGS84 mean radius, metres

/**
 * @param u normalized horizontal pixel offset from center, -1 (left) .. +1 (right)
 * @param v normalized vertical pixel offset from center, -1 (top) .. +1 (bottom)
 * @param groundElevationM ground AMSL elevation under the target (terrain-aware when provided)
 */
export function projectPixelToGround(
  pose: CameraPose,
  u: number,
  v: number,
  groundElevationM = 0,
): GeoPoint | null {
  const heightAboveGround = pose.altMslM - groundElevationM;
  if (heightAboveGround <= 0) return null;

  // Ray angles relative to the camera boresight, then add the gimbal pointing.
  // Down-angle increases toward the bottom of the frame (+v).
  const downAngle = (pose.pitchDownDeg + v * (pose.vfovDeg / 2)) * DEG;
  // Bearing offset increases to the right of frame (+u).
  const bearing = (pose.bearingDeg + u * (pose.hfovDeg / 2)) * DEG;

  // Need a downward component for the ray to hit the ground.
  if (downAngle <= 0.0001) return null;

  // Horizontal ground distance from the nadir to the intersection.
  const groundDist = heightAboveGround / Math.tan(downAngle);
  const slantRangeM = heightAboveGround / Math.sin(downAngle);

  // Walk groundDist along `bearing` from the camera position (equirectangular,
  // accurate at the sub-km ranges this is used for).
  const dLat = (groundDist * Math.cos(bearing)) / EARTH_R;
  const dLon = (groundDist * Math.sin(bearing)) / (EARTH_R * Math.cos(pose.lat * DEG));

  return {
    lat: pose.lat + dLat / DEG,
    lon: pose.lon + dLon / DEG,
    slantRangeM,
  };
}

/** Frame center is just the (0,0) pixel. */
export function projectFrameCenter(pose: CameraPose, groundElevationM = 0): GeoPoint | null {
  return projectPixelToGround(pose, 0, 0, groundElevationM);
}

/**
 * The four ground corners of the camera footprint, for drawing the FOV
 * trapezoid on the map. Corners that fall above the horizon are omitted, so a
 * forward-tilted camera yields a partial (near-edge only) polygon rather than
 * garbage.
 */
export function projectFootprint(pose: CameraPose, groundElevationM = 0): GeoPoint[] {
  const corners: Array<[number, number]> = [
    [-1, -1],
    [1, -1],
    [1, 1],
    [-1, 1],
  ];
  const pts: GeoPoint[] = [];
  for (const [u, v] of corners) {
    const p = projectPixelToGround(pose, u, v, groundElevationM);
    if (p) pts.push(p);
  }
  return pts;
}

/** Format a lat/lon as a compact DMS-ish decimal string for the OSD. */
export function formatCoord(lat: number, lon: number): string {
  const ns = lat >= 0 ? 'N' : 'S';
  const ew = lon >= 0 ? 'E' : 'W';
  return `${Math.abs(lat).toFixed(6)}°${ns}  ${Math.abs(lon).toFixed(6)}°${ew}`;
}
