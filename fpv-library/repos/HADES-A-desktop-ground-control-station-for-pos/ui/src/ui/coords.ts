import { forward as mgrsForward } from "mgrs";

/* Coordinate readout (DESIGN-SYSTEM §6.3a). TWO canonical formats, one per consumer role:
 *  - grid (MGRS/USNG): the PRIMARY — what US ground SAR speaks on the radio (FEMA standard).
 *  - geographic (WGS84 DDM): the secondary — what air/Coast Guard navigate by.
 * Both radio-speakable, fixed precision, datum-explicit. A null fix is an HONEST "NO FIX",
 * never a phantom coordinate (the same null-island defense as the wire schema). MGRS via the
 * vetted `mgrs` lib — we never hand-roll the UTM spheroid math for a life-safety coordinate. */

const NO_FIX = "NO FIX";

/** Degrees-decimal-minutes, e.g. "N30 12.900  W088 31.200". */
export function formatDDM(lat: number, lon: number): string {
  return `${ddmPart(lat, "N", "S")}  ${ddmPart(lon, "E", "W", 3)}`;
}

function ddmPart(deg: number, pos: string, neg: string, degWidth = 2): string {
  const hemi = deg >= 0 ? pos : neg;
  const abs = Math.abs(deg);
  const d = Math.floor(abs);
  const min = (abs - d) * 60;
  return `${hemi}${String(d).padStart(degWidth, "0")} ${min.toFixed(3).padStart(6, "0")}`;
}

/** MGRS/USNG grid, spaced for voice, e.g. "16R EU 1234 5678" (10 m precision = 4+4 digits). */
export function formatMGRS(lat: number, lon: number, digits = 4): string {
  // mgrs.forward takes [lon, lat]; `accuracy` is digits per axis (4 → 10 m)
  const raw = mgrsForward([lon, lat], digits);
  // raw is like "16REU12345678"; split into zone+band, 100km square, easting, northing
  const m = raw.match(/^(\d{1,2}[C-X])([A-Z]{2})(\d+)$/);
  if (!m) return raw;
  const [, gzd, sq, en] = m;
  const half = en.length / 2;
  return `${gzd} ${sq} ${en.slice(0, half)} ${en.slice(half)}`;
}

export interface FormattedCoord {
  grid: string; // primary
  geographic: string; // secondary
  datum: string;
}

export function formatContactCoord(
  lat: number | null,
  lon: number | null,
  datum: string,
): FormattedCoord {
  if (lat === null || lon === null) {
    return { grid: NO_FIX, geographic: NO_FIX, datum };
  }
  return { grid: formatMGRS(lat, lon), geographic: formatDDM(lat, lon), datum };
}
