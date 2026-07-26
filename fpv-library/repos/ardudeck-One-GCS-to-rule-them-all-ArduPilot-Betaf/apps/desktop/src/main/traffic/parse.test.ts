import { describe, it, expect } from 'vitest';
import { parseAdsbxV2, parseOpenSkyStates, parseOgnAprs } from './parse';

describe('parseAdsbxV2', () => {
  // tar1090 / airplanes.live / adsb.fi / adsbexchange all share this shape.
  const sample = {
    now: 1_700_000_000,
    aircraft: [
      {
        hex: 'a1b2c3',
        flight: 'DAL123  ',
        r: 'N123DL',
        t: 'B738',
        category: 'A3',
        lat: 45.1,
        lon: -75.2,
        alt_baro: 35000, // feet
        gs: 450, // knots
        track: 270.5,
        baro_rate: -640, // feet/min
        squawk: '1200',
        seen_pos: 0.4,
      },
      {
        hex: 'dd1234',
        category: 'A7', // rotorcraft
        lat: 45.0,
        lon: -75.0,
        alt_baro: 'ground',
        gs: 0,
        seen_pos: 1.2,
      },
    ],
  };

  it('maps adsbx fields to contacts with SI units', () => {
    const out = parseAdsbxV2(sample, 1_700_000_000_000);
    expect(out).toHaveLength(2);
    const a = out[0]!;
    expect(a.id).toBe('a1b2c3');
    expect(a.source).toBe('adsb');
    expect(a.callsign).toBe('DAL123');
    expect(a.registration).toBe('N123DL');
    expect(a.model).toBe('B738');
    expect(a.altMeters).toBeCloseTo(35000 * 0.3048, 1);
    expect(a.groundSpeedMps).toBeCloseTo(450 * 0.514444, 1);
    expect(a.trackDeg).toBe(270.5);
    expect(a.verticalRateMps).toBeCloseTo(-640 * 0.00508, 2);
    expect(a.squawk).toBe('1200');
    expect(a.category).toBe('powered');
  });

  it('handles "ground" altitude and rotorcraft category', () => {
    const h = parseAdsbxV2(sample, 1_700_000_000_000)[1]!;
    expect(h.onGround).toBe(true);
    expect(h.altMeters).toBeUndefined();
    expect(h.category).toBe('helicopter');
  });

  it('accepts the alternate "ac" array key (airplanes.live)', () => {
    const out = parseAdsbxV2({ ac: [{ hex: 'abc', lat: 1, lon: 2, seen_pos: 0 }] }, 0);
    expect(out).toHaveLength(1);
    expect(out[0]!.id).toBe('abc');
  });

  it('drops entries without a position', () => {
    const out = parseAdsbxV2({ aircraft: [{ hex: 'nopos', gs: 100 }] }, 0);
    expect(out).toHaveLength(0);
  });
});

describe('parseOpenSkyStates', () => {
  const sample = {
    time: 1_700_000_000,
    states: [
      // icao24, callsign, country, time_pos, last_contact, lon, lat, baro_alt(m),
      // on_ground, velocity(m/s), true_track, vertical_rate(m/s), ...
      ['c0ffee', 'ACA456 ', 'Canada', 1_700_000_000, 1_700_000_000, -75.5, 45.5, 10000, false, 230, 90, 5.2, null, 9000, '7000', false, 0],
      ['deadbe', null, 'X', 1_700_000_000, 1_700_000_000, null, null, null, true, 0, null, null],
    ],
  };

  it('maps state vectors to contacts', () => {
    const out = parseOpenSkyStates(sample);
    expect(out).toHaveLength(1); // second has no position -> dropped
    const a = out[0]!;
    expect(a.id).toBe('c0ffee');
    expect(a.source).toBe('adsb');
    expect(a.callsign).toBe('ACA456');
    expect(a.lat).toBe(45.5);
    expect(a.lon).toBe(-75.5);
    expect(a.altMeters).toBe(10000);
    expect(a.groundSpeedMps).toBe(230);
    expect(a.trackDeg).toBe(90);
    expect(a.verticalRateMps).toBe(5.2);
    expect(a.squawk).toBe('7000');
    expect(a.lastSeen).toBe(1_700_000_000 * 1000);
  });
});

describe('parseOgnAprs', () => {
  const line =
    "FLRDDA5BA>APRS,qAS,LFMX:/074548h4505.10N/00610.00E'086/007/A=003503 !W33! id06DDA5BA -019fpm +0.0rot 5.5dB";

  it('parses an OGN position packet', () => {
    const c = parseOgnAprs(line, 1_700_000_000_000)!;
    expect(c).not.toBeNull();
    expect(c.source).toBe('ogn');
    expect(c.id).toBe('DDA5BA');
    expect(c.category).toBe('glider');
    expect(c.lat).toBeCloseTo(45 + 5.1 / 60, 4);
    expect(c.lon).toBeCloseTo(6 + 10 / 60, 4);
    expect(c.trackDeg).toBe(86);
    expect(c.groundSpeedMps).toBeCloseTo(7 * 0.514444, 2);
    expect(c.altMeters).toBeCloseTo(3503 * 0.3048, 1);
    expect(c.verticalRateMps).toBeCloseTo(-19 * 0.00508, 2);
  });

  it('handles west/south hemispheres', () => {
    const w =
      "FLRXX>APRS,qAS,X:/074548h4505.10S/00610.00W'086/007/A=000000 id06ABCDEF";
    const c = parseOgnAprs(w, 0)!;
    expect(c.lat).toBeLessThan(0);
    expect(c.lon).toBeLessThan(0);
  });

  it('returns null for server comments and non-position lines', () => {
    expect(parseOgnAprs('# aprsc 2.1.0', 0)).toBeNull();
    expect(parseOgnAprs('FLRXX>APRS,qAS,X:>status text only', 0)).toBeNull();
  });
});
