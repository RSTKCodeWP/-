/**
 * @module energy-model
 * @description Simple, transparent flight-energy estimation for mission planning.
 * Estimates watt-hours and flight time from distance and power draw, splits a
 * mission across battery packs with a safety reserve, and derates power for wind
 * and battery capacity for temperature.
 *
 * The formulas are deliberately first-order approximations with documented
 * coefficients. They are planning aids, not a substitute for a measured power
 * curve, so no more precision is implied than the inputs justify.
 * @license GPL-3.0-only
 */

/** Watt-hours per joule-hour helper: seconds -> hours divisor. */
const SECONDS_PER_HOUR = 3600;

/** Clamp a value to an inclusive range. */
function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * Fractional change in cruise power per m/s of wind.
 * ~3% per m/s is a rough headwind/tailwind sensitivity for a small multirotor
 * or fixed-wing at typical cruise; it is a linear stand-in for the real
 * airspeed-vs-power curve.
 */
const WIND_POWER_COEFF = 0.03;

/** A strong tailwind never drives cruise power below this fraction of base. */
const WIND_MIN_FACTOR = 0.5;

/**
 * Derate (or uprate) a base power draw for wind.
 *
 * A headwind forces a higher airspeed to hold ground speed, raising power; a
 * tailwind lowers it. Modeled linearly at {@link WIND_POWER_COEFF} per m/s and
 * floored at {@link WIND_MIN_FACTOR} so a strong tailwind still leaves the power
 * needed to stay aloft.
 *
 * @param baseWatts Still-air power draw, in watts.
 * @param windMps Wind speed magnitude, in m/s. Negative values use their magnitude.
 * @param headwind True for a net headwind (raises power), false for a tailwind.
 * @returns Adjusted power draw, in watts.
 */
export function windDerate(baseWatts: number, windMps: number, headwind = true): number {
  const magnitude = Math.abs(windMps);
  const sign = headwind ? 1 : -1;
  const factor = Math.max(WIND_MIN_FACTOR, 1 + sign * WIND_POWER_COEFF * magnitude);
  return baseWatts * factor;
}

/** Temperature at which battery capacity is considered rated, in degrees Celsius. */
const NOMINAL_TEMP_C = 25;

/** Fractional capacity lost per degree C below {@link NOMINAL_TEMP_C}. */
const COLD_LOSS_PER_C = 0.01;

/** Fractional capacity lost per degree C above {@link NOMINAL_TEMP_C}. */
const HOT_LOSS_PER_C = 0.005;

/** Usable capacity never derates below this fraction of rated. */
const TEMP_MIN_FACTOR = 0.4;

/**
 * Derate usable battery capacity for temperature.
 *
 * Cold is the dominant real effect: lithium packs deliver noticeably less energy
 * below room temperature. Heat causes a milder loss. Modeled piecewise-linearly
 * around {@link NOMINAL_TEMP_C} and floored at {@link TEMP_MIN_FACTOR}.
 *
 * @param capacityWh Rated capacity, in watt-hours.
 * @param tempC Ambient (or pack) temperature, in degrees Celsius.
 * @returns Usable capacity at that temperature, in watt-hours.
 */
export function tempDerate(capacityWh: number, tempC: number): number {
  let factor: number;
  if (tempC < NOMINAL_TEMP_C) {
    factor = 1 - COLD_LOSS_PER_C * (NOMINAL_TEMP_C - tempC);
  } else {
    factor = 1 - HOT_LOSS_PER_C * (tempC - NOMINAL_TEMP_C);
  }
  return capacityWh * clamp(factor, TEMP_MIN_FACTOR, 1);
}

/** Inputs to {@link estimateEnergyWh}. */
export interface EnergyEstimateParams {
  /** Path distance to fly, in meters. */
  distanceM: number;
  /** Forward cruise speed, in m/s. Non-positive means no forward progress. */
  cruiseSpeedMps: number;
  /** Power drawn while hovering, in watts. */
  hoverWatts: number;
  /** Power drawn while cruising forward, in watts. */
  cruiseWatts: number;
  /** Seconds spent hovering (waypoint holds, takeoff/landing loiter). Default 0. */
  hoverSeconds?: number;
  /** Ambient wind speed, in m/s. When > 0, cruise power is derated. Default 0. */
  windMps?: number;
  /** True if the wind is a net headwind, false for a tailwind. Default true. */
  headwind?: boolean;
}

/** Result of {@link estimateEnergyWh}. */
export interface EnergyEstimate {
  /** Total energy required for the flight, in watt-hours. */
  totalWh: number;
  /** Total flight time (cruise + hover), in minutes. */
  flightMinutes: number;
  /** Energy attributable to forward cruise, in watt-hours. */
  cruiseWh: number;
  /** Energy attributable to hovering, in watt-hours. */
  hoverWh: number;
  /** Cruise power after the wind derate, in watts. */
  effectiveCruiseWatts: number;
  /** Seconds spent cruising forward. */
  cruiseSeconds: number;
}

/**
 * Estimate the energy and flight time for a leg of known distance.
 *
 * Cruise energy is (effective cruise power) x (distance / speed); hover energy is
 * hover power x hover time. Wind, when supplied, derates only the cruise power
 * (where ground-vs-air speed matters); hover-in-place power is left as given.
 * A non-positive cruise speed yields zero cruise time (the leg cannot be flown
 * forward), so the caller should validate speed separately.
 */
export function estimateEnergyWh(params: EnergyEstimateParams): EnergyEstimate {
  const {
    distanceM,
    cruiseSpeedMps,
    hoverWatts,
    cruiseWatts,
    hoverSeconds = 0,
    windMps = 0,
    headwind = true,
  } = params;

  const effectiveCruiseWatts =
    windMps > 0 ? windDerate(cruiseWatts, windMps, headwind) : cruiseWatts;

  const cruiseSeconds =
    cruiseSpeedMps > 0 && distanceM > 0 ? distanceM / cruiseSpeedMps : 0;
  const hoverSecs = Math.max(0, hoverSeconds);

  const cruiseWh = (effectiveCruiseWatts * cruiseSeconds) / SECONDS_PER_HOUR;
  const hoverWh = (hoverWatts * hoverSecs) / SECONDS_PER_HOUR;
  const totalWh = cruiseWh + hoverWh;

  return {
    totalWh,
    flightMinutes: (cruiseSeconds + hoverSecs) / 60,
    cruiseWh,
    hoverWh,
    effectiveCruiseWatts,
    cruiseSeconds,
  };
}

/** Result of {@link segmentByBattery}. */
export interface BatterySegmentation {
  /** Full battery packs required. Infinity signals an infeasible pack/reserve. */
  batteriesNeeded: number;
  /** Mid-mission battery swaps (batteriesNeeded - 1, never below 0). */
  swaps: number;
  /** Watt-hours drawn from each battery, in order; the last entry is the remainder. */
  segments: number[];
  /** Usable watt-hours per battery once the reserve is held back. */
  usablePerBatteryWh: number;
}

/** Reserve is clamped below this so at least some capacity is always usable. */
const MAX_RESERVE_FRACTION = 0.99;

/**
 * Split a mission's energy demand across battery packs, holding back a reserve.
 *
 * Each pack is treated as delivering (1 - reserve) of its rated capacity before a
 * swap. The number of packs is ceil(totalWh / usablePerBattery); swaps is one
 * fewer. The per-battery segments record the Wh drawn from each pack, the final
 * one being the remainder.
 *
 * @param totalWh Total flight energy required, in watt-hours.
 * @param batteryWh Rated capacity of one pack, in watt-hours.
 * @param reserveFraction Fraction of each pack kept in reserve. Default 0.2.
 */
export function segmentByBattery(
  totalWh: number,
  batteryWh: number,
  reserveFraction = 0.2
): BatterySegmentation {
  const reserve = clamp(reserveFraction, 0, MAX_RESERVE_FRACTION);
  const usable = batteryWh * (1 - reserve);

  if (totalWh <= 0) {
    return {
      batteriesNeeded: 0,
      swaps: 0,
      segments: [],
      usablePerBatteryWh: Math.max(0, usable),
    };
  }

  if (usable <= 0) {
    // No pack under this reserve can hold any energy: the mission cannot be flown.
    return {
      batteriesNeeded: Infinity,
      swaps: Infinity,
      segments: [],
      usablePerBatteryWh: 0,
    };
  }

  const batteriesNeeded = Math.ceil(totalWh / usable);
  const segments: number[] = [];
  let remaining = totalWh;
  for (let i = 0; i < batteriesNeeded; i++) {
    const draw = Math.min(usable, remaining);
    segments.push(draw);
    remaining -= draw;
  }

  return {
    batteriesNeeded,
    swaps: batteriesNeeded - 1,
    segments,
    usablePerBatteryWh: usable,
  };
}
