/**
 * @module sun-times
 * @description Pure sun-position and golden-hour helpers for mission planning.
 * Wraps `suncalc` to expose sunrise / sunset / solar-noon / golden-hour times
 * and the live sun altitude/azimuth for a lat/lon at a given instant. All
 * angles are returned in degrees at the display boundary; suncalc works in
 * radians internally. No store, no React, no side effects.
 * @license GPL-3.0-only
 */

import SunCalc from "suncalc";

const RAD_TO_DEG = 180 / Math.PI;

/**
 * Upper bound of the golden-hour band: suncalc's `goldenHour` / `goldenHourEnd`
 * are the instants the sun crosses this altitude (6° above the horizon).
 */
const GOLDEN_HIGH_DEG = 6;

/**
 * Lower bound of the golden-hour band: the refraction-corrected horizon
 * (suncalc's sunrise/sunset angle, -0.833°). Below this the sun has set.
 */
const HORIZON_DEG = -0.833;

/** Sun event times for a single day at one location (all local wall-clock Dates). */
export interface SunTimes {
  sunrise: Date;
  sunset: Date;
  /** Evening golden hour start (sun descends to 6° above the horizon). */
  goldenHourStart: Date;
  /** Morning golden hour end (sun rises to 6° above the horizon). */
  goldenHourEnd: Date;
  solarNoon: Date;
}

/** Instantaneous sun position, degrees. */
export interface SunPosition {
  /** Altitude above the horizon; negative when the sun is below it. */
  altitudeDeg: number;
  /** Compass azimuth, clockwise from true north, normalized to [0, 360). */
  azimuthDeg: number;
}

/**
 * Sunrise / sunset / solar-noon / golden-hour times for the calendar day that
 * `date` falls on, at the given latitude/longitude (decimal degrees, WGS84).
 * At polar latitudes where the sun never rises or sets, suncalc returns
 * `Invalid Date` values; callers should guard with `Number.isNaN(d.getTime())`.
 */
export function sunTimesFor(date: Date, lat: number, lon: number): SunTimes {
  const t = SunCalc.getTimes(date, lat, lon);
  return {
    sunrise: t.sunrise,
    sunset: t.sunset,
    // suncalc "goldenHour" is the evening start; "goldenHourEnd" the morning end.
    goldenHourStart: t.goldenHour,
    goldenHourEnd: t.goldenHourEnd,
    solarNoon: t.solarNoon,
  };
}

/**
 * Sun altitude and compass azimuth at the given instant and location.
 * suncalc measures azimuth from due south, positive toward the west; this
 * converts it to a compass bearing measured clockwise from true north.
 */
export function sunPosition(date: Date, lat: number, lon: number): SunPosition {
  const p = SunCalc.getPosition(date, lat, lon);
  const azimuthDeg = ((p.azimuth * RAD_TO_DEG + 180) % 360 + 360) % 360;
  return { altitudeDeg: p.altitude * RAD_TO_DEG, azimuthDeg };
}

/**
 * True when the sun sits inside the golden-hour band (the refraction-corrected
 * horizon up to 6° altitude) at the given instant. This is exactly the union
 * of the morning [sunrise, goldenHourEnd] and evening [goldenHourStart, sunset]
 * windows, since altitude is monotonic within each half of the day.
 */
export function isGoldenHour(date: Date, lat: number, lon: number): boolean {
  const { altitudeDeg } = sunPosition(date, lat, lon);
  if (!Number.isFinite(altitudeDeg)) return false;
  return altitudeDeg >= HORIZON_DEG && altitudeDeg <= GOLDEN_HIGH_DEG;
}
