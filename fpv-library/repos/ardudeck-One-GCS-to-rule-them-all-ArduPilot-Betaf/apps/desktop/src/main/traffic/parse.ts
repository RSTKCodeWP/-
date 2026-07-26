/**
 * parse — pure normalisers turning each provider's wire format into TrafficContact.
 *
 * Network-free and side-effect-free so they're unit-testable against captured
 * fixtures. Providers do the fetching/streaming and call these.
 */

import type { TrafficCategory, TrafficContact } from '../../shared/traffic-types.js';

const FT_TO_M = 0.3048;
const KT_TO_MS = 0.514444;
const FPM_TO_MS = 0.00508; // feet/min -> m/s

// ─── ADS-B Exchange v2 shape (tar1090, airplanes.live, adsb.fi, adsbexchange) ──

interface AdsbxAircraft {
  hex?: string;
  flight?: string;
  r?: string; // registration
  t?: string; // type/model
  category?: string; // emitter category "A0".."C7"
  lat?: number;
  lon?: number;
  alt_baro?: number | 'ground';
  alt_geom?: number;
  gs?: number;
  track?: number;
  baro_rate?: number;
  geom_rate?: number;
  squawk?: string;
  seen_pos?: number;
}

/** Map an ADS-B emitter category code to our coarse class. */
function adsbCategory(cat: string | undefined): TrafficCategory {
  switch (cat) {
    case 'A7':
      return 'helicopter';
    case 'A4':
    case 'A5':
      return 'jet';
    case 'B1':
      return 'glider';
    case 'B2':
      return 'balloon';
    case 'B6':
      return 'uav';
    case 'C1':
    case 'C2':
    case 'C3':
      return 'ground';
    default:
      if (cat && cat.startsWith('A')) return 'powered';
      return 'unknown';
  }
}

/** Parse a tar1090/ADSBExchange-v2 style response. `nowMs` is the receive time
 *  used as lastSeen minus the per-aircraft `seen_pos` age. */
export function parseAdsbxV2(json: unknown, nowMs: number): TrafficContact[] {
  const obj = json as { aircraft?: AdsbxAircraft[]; ac?: AdsbxAircraft[] };
  const list = obj.aircraft ?? obj.ac ?? [];
  const out: TrafficContact[] = [];
  for (const a of list) {
    if (!a.hex || typeof a.lat !== 'number' || typeof a.lon !== 'number') continue;
    const onGround = a.alt_baro === 'ground';
    const altFt = onGround ? undefined : typeof a.alt_baro === 'number' ? a.alt_baro : a.alt_geom;
    const rate = a.baro_rate ?? a.geom_rate;
    const seenMs = typeof a.seen_pos === 'number' ? a.seen_pos * 1000 : 0;
    out.push({
      id: a.hex.toLowerCase(),
      source: 'adsb',
      callsign: a.flight?.trim() || undefined,
      registration: a.r?.trim() || undefined,
      model: a.t?.trim() || undefined,
      category: adsbCategory(a.category),
      lat: a.lat,
      lon: a.lon,
      altMeters: typeof altFt === 'number' ? altFt * FT_TO_M : undefined,
      onGround: onGround || undefined,
      groundSpeedMps: typeof a.gs === 'number' ? a.gs * KT_TO_MS : undefined,
      trackDeg: typeof a.track === 'number' ? a.track : undefined,
      verticalRateMps: typeof rate === 'number' ? rate * FPM_TO_MS : undefined,
      squawk: a.squawk || undefined,
      lastSeen: nowMs - seenMs,
    });
  }
  return out;
}

// ─── OpenSky /states/all ──────────────────────────────────────────────────────

type OpenSkyState = [
  string, // 0 icao24
  string | null, // 1 callsign
  string, // 2 origin_country
  number | null, // 3 time_position
  number, // 4 last_contact
  number | null, // 5 longitude
  number | null, // 6 latitude
  number | null, // 7 baro_altitude (m)
  boolean, // 8 on_ground
  number | null, // 9 velocity (m/s)
  number | null, // 10 true_track
  number | null, // 11 vertical_rate (m/s)
  number[] | null, // 12 sensors
  number | null, // 13 geo_altitude (m)
  string | null, // 14 squawk
  boolean, // 15 spi
  number, // 16 position_source
];

export function parseOpenSkyStates(json: unknown): TrafficContact[] {
  const obj = json as { time?: number; states?: OpenSkyState[] };
  const states = obj.states ?? [];
  const out: TrafficContact[] = [];
  for (const s of states) {
    const [icao, callsign, , timePos, lastContact, lon, lat, baroAlt, onGround, vel, track, vRate, , geoAlt, squawk] = s;
    if (typeof lat !== 'number' || typeof lon !== 'number') continue;
    const alt = typeof baroAlt === 'number' ? baroAlt : typeof geoAlt === 'number' ? geoAlt : undefined;
    const seen = (timePos ?? lastContact ?? obj.time ?? 0) * 1000;
    out.push({
      id: icao.toLowerCase(),
      source: 'adsb',
      callsign: callsign?.trim() || undefined,
      category: 'unknown',
      lat,
      lon,
      altMeters: onGround ? undefined : alt,
      onGround: onGround || undefined,
      groundSpeedMps: typeof vel === 'number' ? vel : undefined,
      trackDeg: typeof track === 'number' ? track : undefined,
      verticalRateMps: typeof vRate === 'number' ? vRate : undefined,
      squawk: squawk || undefined,
      lastSeen: seen,
    });
  }
  return out;
}

// ─── OGN APRS-IS ──────────────────────────────────────────────────────────────

// Body example:
//   /074548h4505.10N/00610.00E'086/007/A=003503 !W33! id06DDA5BA -019fpm +0.0rot
const OGN_POS_RE =
  /^\/\d{6}h(\d{2})(\d{2}\.\d+)([NS])[/\\](\d{3})(\d{2}\.\d+)([EW]).(\d{3})\/(\d{3})\/A=(-?\d{6})/;
const OGN_ID_RE = /\bid[0-9A-Fa-f]{2}([0-9A-Fa-f]{6})\b/;
const OGN_FPM_RE = /([+-]?\d+)fpm/;

/** Parse one APRS-IS line into a glider contact, or null if it isn't an OGN
 *  position packet (server comments, status lines, etc.). */
export function parseOgnAprs(line: string, nowMs: number): TrafficContact | null {
  if (!line || line.startsWith('#')) return null;
  const colon = line.indexOf(':');
  if (colon < 0) return null;
  const from = line.slice(0, line.indexOf('>'));
  const body = line.slice(colon + 1);
  const m = OGN_POS_RE.exec(body);
  if (!m) return null;

  const [, latDeg, latMin, ns, lonDeg, lonMin, ew, course, speedKt, altFt] = m;
  let lat = Number(latDeg) + Number(latMin) / 60;
  let lon = Number(lonDeg) + Number(lonMin) / 60;
  if (ns === 'S') lat = -lat;
  if (ew === 'W') lon = -lon;

  const idMatch = OGN_ID_RE.exec(body);
  const fpmMatch = OGN_FPM_RE.exec(body);

  return {
    id: (idMatch?.[1] ?? from).toUpperCase(),
    source: 'ogn',
    callsign: from || undefined,
    category: 'glider',
    lat,
    lon,
    altMeters: Number(altFt) * FT_TO_M,
    trackDeg: Number(course),
    groundSpeedMps: Number(speedKt) * KT_TO_MS,
    verticalRateMps: fpmMatch ? Number(fpmMatch[1]) * FPM_TO_MS : undefined,
    lastSeen: nowMs,
  };
}
