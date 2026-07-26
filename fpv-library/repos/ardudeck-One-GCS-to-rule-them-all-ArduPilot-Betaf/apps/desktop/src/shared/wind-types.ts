/**
 * Shared types for the animated wind overlay.
 *
 * A WindField is a small regional u/v grid sampled from Open-Meteo, plus a
 * stack of forecast-hour frames so the renderer can scrub time. Grid cells are
 * row-major with row 0 = SOUTH edge and col 0 = WEST edge:
 *   index = row * width + col
 *   lat   = south + row * (north - south) / (height - 1)
 *   lon   = west  + col * (east  - west)  / (width  - 1)
 * u is eastward (+E) and v is northward (+N), both in m/s.
 */

export interface WindBBox {
  south: number;
  north: number;
  west: number;
  east: number;
}

/** One forecast hour: u/v arrays of length width*height (row-major, south-up). */
export interface WindFrame {
  /** ISO-8601 UTC hour, e.g. "2026-06-17T14:00". */
  time: string;
  u: number[];
  v: number[];
}

export interface WindField {
  width: number;
  height: number;
  bbox: WindBBox;
  /** Above-ground level the field represents (metres). */
  altitudeM: number;
  frames: WindFrame[];
  /** Max wind magnitude (m/s) across all frames/cells — for color scaling. */
  speedMax: number;
  /** Human label, e.g. "Open-Meteo · 120 m". */
  modelLabel: string;
  /** epoch ms when this field was fetched. */
  fetchedAt: number;
}

export interface WindFetchParams {
  bbox: WindBBox;
  altitudeM: number;
}

/** Above-ground levels Open-Meteo serves wind for. */
export const WIND_ALTITUDES = [10, 80, 120, 180] as const;
export type WindAltitude = (typeof WIND_ALTITUDES)[number];
