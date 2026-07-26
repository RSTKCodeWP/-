/**
 * @module geocoding/parse-latlon
 * @description Parse a free-typed coordinate string into { lat, lon } so the map
 * search box resolves coordinates offline (no network) before falling back to
 * forward geocoding. Accepts decimal ("12.97, 77.59"), signed, hemisphere
 * suffixes/prefixes ("12.97N 77.59E", "N12.97 E77.59"), and lat/lon separated by
 * comma or whitespace. Returns null when the string is not a coordinate.
 * @license GPL-3.0-only
 */

export interface LatLon {
  lat: number;
  lon: number;
}

/** One signed decimal degrees value with an optional N/S/E/W hemisphere. */
function parseComponent(raw: string): { value: number; hemi?: "N" | "S" | "E" | "W" } | null {
  const s = raw.trim().toUpperCase();
  if (!s) return null;
  const m = s.match(/^([NSEW])?\s*([+-]?\d+(?:\.\d+)?)\s*°?\s*([NSEW])?$/);
  if (!m) return null;
  const hemi = (m[1] || m[3]) as "N" | "S" | "E" | "W" | undefined;
  if (m[1] && m[3]) return null; // hemisphere on both ends is malformed
  const value = Number(m[2]);
  if (!Number.isFinite(value)) return null;
  return { value, hemi };
}

/** Apply a hemisphere sign to a magnitude. */
function signed(value: number, hemi?: "N" | "S" | "E" | "W"): number {
  if (hemi === "S" || hemi === "W") return -Math.abs(value);
  if (hemi === "N" || hemi === "E") return Math.abs(value);
  return value;
}

/**
 * Parse "lat, lon" (comma or whitespace separated). Returns null if the string
 * is not two valid coordinate components in range.
 */
export function parseLatLon(input: string): LatLon | null {
  if (!input) return null;
  const parts = input.trim().split(/\s*,\s*|\s+/).filter(Boolean);
  // Rejoin when hemispheres are attached ("12.97N" is one token, fine; but
  // "N 12.97" splits into two — recombine adjacent hemisphere+number).
  const tokens: string[] = [];
  for (let i = 0; i < parts.length; i++) {
    if (/^[NSEW]$/i.test(parts[i]) && i + 1 < parts.length && /\d/.test(parts[i + 1])) {
      tokens.push(`${parts[i]}${parts[i + 1]}`);
      i++;
    } else {
      tokens.push(parts[i]);
    }
  }
  if (tokens.length !== 2) return null;

  const a = parseComponent(tokens[0]);
  const b = parseComponent(tokens[1]);
  if (!a || !b) return null;

  // Decide which token is latitude: an explicit N/S wins; else assume lat first.
  const aIsLat = a.hemi === "N" || a.hemi === "S";
  const bIsLat = b.hemi === "N" || b.hemi === "S";
  let latC = a, lonC = b;
  if (bIsLat && !aIsLat) { latC = b; lonC = a; }

  const lat = signed(latC.value, latC.hemi);
  const lon = signed(lonC.value, lonC.hemi);
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;
  return { lat, lon };
}
