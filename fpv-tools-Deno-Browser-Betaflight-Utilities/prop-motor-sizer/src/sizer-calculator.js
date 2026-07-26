/**
 * Prop / motor sizing math. Pure functions, no DOM.
 *
 * All estimates use simplified physics (Staples static-thrust model,
 * momentum theory for power) calibrated against typical FPV thrust-stand
 * numbers. Treat outputs as ±20-30% ballparks, not bench data.
 *
 * Conventions: prop dimensions in inches, weights in grams, voltage at
 * full charge (4.2 V/cell), RPM estimates assume props load the motor to
 * ~75% of its unloaded KV×V ceiling.
 */

export const AIR_DENSITY = 1.225; // kg/m³, sea level
export const SPEED_OF_SOUND = 343; // m/s
export const IN_TO_M = 0.0254;
export const CELL_VOLTAGE_FULL = 4.2;
export const CELL_VOLTAGE_NOMINAL = 3.7;
export const DEFAULT_LOAD_FACTOR = 0.75;
export const USABLE_BATTERY_FRACTION = 0.8;

const GRAMS_PER_NEWTON = 1000 / 9.81;

// Thrust multiplier vs a 2-blade prop at the same RPM. Extra blades add
// thrust with diminishing returns (and cost efficiency, handled elsewhere).
const BLADE_FACTORS = { 2: 1.0, 3: 1.15, 4: 1.27, 5: 1.36, 6: 1.44 };

// Stator volume (mm³) that suits a prop diameter d (inches) follows roughly
// TARGET = STATOR_COEFF × d^STATOR_EXP, fitted to well-known pairings
// (0802→1.2", 1404→3", 2207/2306→5", 2806.5→7"). The band multipliers set
// how far off-center a pairing can be and still be listed as reasonable.
const STATOR_COEFF = 67;
const STATOR_EXP = 2.2;
const STATOR_BAND = [0.6, 1.6];

// Stator sizes commonly available off the shelf, used when recommending.
const STANDARD_STATORS = [
  "0802",
  "0803",
  "1002",
  "1102",
  "1103",
  "1104",
  "1202",
  "1204",
  "1303",
  "1404",
  "1406",
  "1408",
  "1504",
  "1505",
  "1506",
  "1507",
  "1606",
  "1806",
  "2004",
  "2006",
  "2205",
  "2206",
  "2207",
  "2208",
  "2306",
  "2307",
  "2405",
  "2406",
  "2407",
  "2408",
  "2506",
  "2507",
  "2508",
  "2806",
  "2806.5",
  "2807",
  "2808",
  "3007",
  "3110",
  "3115",
];

// Pitch-to-diameter ratio bands per flying style.
const PITCH_RATIOS = {
  cinematic: [0.5, 0.75],
  longrange: [0.55, 0.8],
  freestyle: [0.7, 0.95],
  racing: [0.8, 1.1],
};

// Thrust-to-weight bands per flying style, used to recommend AUW.
const TWR_BANDS = {
  cinematic: [2.5, 4.5],
  longrange: [3, 6],
  freestyle: [5, 10],
  racing: [8, 16],
};

// Target KV is derived from an unloaded prop tip speed the class can use
// well; smaller props run slower tips (lower Reynolds, weaker motors).
const KV_STYLE_MULT = {
  cinematic: 0.85,
  longrange: 0.9,
  freestyle: 1.0,
  racing: 1.1,
};
const KV_BAND = 0.15; // ±15% around the ideal

function normalizeStyle(style) {
  return style in TWR_BANDS ? style : "freestyle";
}

// ---------------------------------------------------------------------------
// Parsing
// ---------------------------------------------------------------------------

/**
 * Parse a motor stator size like "2207", "0802", or "2806.5".
 * @param {unknown} value
 * @returns {{statorDiameter: number, statorHeight: number} | null}
 */
export function parseMotorSize(value) {
  const m = String(value ?? "").trim().match(/^(\d{2})[\sx-]?(\d{1,2}(?:\.\d)?)$/);
  if (!m) return null;
  const statorDiameter = Number(m[1]);
  const statorHeight = Number(m[2]);
  if (statorDiameter === 0 || statorHeight === 0) return null;
  return { statorDiameter, statorHeight };
}

/**
 * Stator volume in mm³, the usual proxy for torque capability.
 * @param {{statorDiameter: number, statorHeight: number}} size
 */
export function statorVolume({ statorDiameter, statorHeight }) {
  const r = statorDiameter / 2;
  return Math.PI * r * r * statorHeight;
}

// ---------------------------------------------------------------------------
// RPM and speeds
// ---------------------------------------------------------------------------

/** Unloaded RPM ceiling: KV × voltage. */
export function maxRpm(kv, voltage) {
  return kv * voltage;
}

/** Estimated RPM at full throttle under prop load. */
export function loadedRpm(kv, voltage, loadFactor = DEFAULT_LOAD_FACTOR) {
  return kv * voltage * loadFactor;
}

/**
 * Air density (kg/m³) at an altitude in meters, per the standard-atmosphere
 * troposphere model. Missing or negative altitudes read as sea level.
 */
export function airDensityAtAltitude(altitudeM) {
  const h = Math.min(11000, Math.max(0, altitudeM ?? 0));
  return AIR_DENSITY * Math.pow(1 - 2.25577e-5 * h, 4.2561);
}

/** Prop tip speed in m/s at a given RPM. */
export function tipSpeedMs(diameterIn, rpm) {
  return Math.PI * diameterIn * IN_TO_M * (rpm / 60);
}

/** Fraction of the speed of sound. */
export function machFraction(speedMs) {
  return speedMs / SPEED_OF_SOUND;
}

/** Theoretical zero-slip forward speed in km/h. */
export function pitchSpeedKmh(pitchIn, rpm) {
  return pitchIn * IN_TO_M * (rpm / 60) * 3.6;
}

// ---------------------------------------------------------------------------
// Thrust and power
// ---------------------------------------------------------------------------

function bladeFactor(blades) {
  const b = Math.min(6, Math.max(2, Math.round(blades ?? 2)));
  return BLADE_FACTORS[b];
}

/**
 * Static thrust in grams-force for one prop, per the Staples model
 * (calibrated for 2-blade props) with a blade-count multiplier.
 * @param {number} diameterIn prop diameter, inches
 * @param {number} pitchIn prop pitch, inches
 * @param {number} rpm shaft speed under load
 * @param {number} [blades]
 * @param {number} [density] air density, kg/m³
 */
export function staticThrustGrams(diameterIn, pitchIn, rpm, blades = 2, density = AIR_DENSITY) {
  const d = diameterIn * IN_TO_M;
  const discArea = (Math.PI * d * d) / 4;
  const exitVelocity = rpm * pitchIn * IN_TO_M / 60;
  const slipFactor = Math.pow(diameterIn / (3.29546 * pitchIn), 1.5);
  const newtons = density * discArea * exitVelocity * exitVelocity * slipFactor;
  return newtons * bladeFactor(blades) * GRAMS_PER_NEWTON;
}

export function thrustToWeight(totalThrustGrams, auwGrams) {
  return totalThrustGrams / auwGrams;
}

/**
 * Hover throttle estimate in percent, assuming thrust ∝ throttle².
 */
export function hoverThrottlePercent(twr) {
  return Math.sqrt(1 / twr) * 100;
}

/** All-up weight per unit of total disc area, in g/cm². */
export function discLoading(auwGrams, diameterIn, motorCount) {
  const radiusCm = (diameterIn * 2.54) / 2;
  return auwGrams / (motorCount * Math.PI * radiusCm * radiusCm);
}

/**
 * Electrical power (watts) to produce a given thrust on one prop, from
 * momentum theory divided by a figure of merit and drive efficiency.
 */
export function electricalPowerWatts(
  thrustGrams,
  diameterIn,
  figureOfMerit,
  driveEfficiency = 0.85,
  density = AIR_DENSITY,
) {
  const thrustN = thrustGrams / GRAMS_PER_NEWTON;
  const d = diameterIn * IN_TO_M;
  const discArea = (Math.PI * d * d) / 4;
  const idealWatts = Math.pow(thrustN, 1.5) / Math.sqrt(2 * density * discArea);
  return idealWatts / (figureOfMerit * driveEfficiency);
}

// ---------------------------------------------------------------------------
// Recommendations
// ---------------------------------------------------------------------------

/**
 * Unloaded tip speed (m/s) a prop class can use well. Grows with diameter
 * (tiny props can't reach the tip speeds a 5" runs) and saturates around
 * the transonic-noise limit for big props.
 */
export function targetTipSpeed(diameterIn, style = "freestyle") {
  const base = Math.min(320, Math.max(150, 120 + 36 * diameterIn));
  return base * KV_STYLE_MULT[normalizeStyle(style)];
}

/**
 * KV range for a prop diameter and (full-charge) voltage.
 * @returns {{min: number, ideal: number, max: number}}
 */
export function recommendKv(diameterIn, voltage, style = "freestyle") {
  const ideal = targetTipSpeed(diameterIn, style) /
    (Math.PI * diameterIn * IN_TO_M * voltage / 60);
  return {
    min: Math.round(ideal * (1 - KV_BAND)),
    ideal: Math.round(ideal),
    max: Math.round(ideal * (1 + KV_BAND)),
  };
}

/**
 * Battery cell count for a prop diameter and motor KV.
 * @returns {{min: number, ideal: number, max: number}}
 */
export function recommendCellCount(diameterIn, kv, style = "freestyle") {
  const idealVoltage = targetTipSpeed(diameterIn, style) /
    (Math.PI * diameterIn * IN_TO_M * kv / 60);
  const toCells = (v) => Math.min(8, Math.max(1, Math.round(v / CELL_VOLTAGE_FULL)));
  return {
    min: toCells(idealVoltage * (1 - KV_BAND)),
    ideal: toCells(idealVoltage),
    max: toCells(idealVoltage * (1 + KV_BAND)),
  };
}

/**
 * Stator sizes whose volume suits a prop diameter.
 * @returns {{targetVolume: number, sizes: string[]}}
 */
export function recommendMotorSizes(diameterIn) {
  const targetVolume = STATOR_COEFF * Math.pow(diameterIn, STATOR_EXP);
  const [lo, hi] = STATOR_BAND;
  const sizes = STANDARD_STATORS.filter((s) => {
    const vol = statorVolume(parseMotorSize(s));
    return vol >= targetVolume * lo && vol <= targetVolume * hi;
  });
  return { targetVolume, sizes };
}

/**
 * Prop diameter range that suits a motor size, inverting the stator fit.
 * @returns {{min: number, ideal: number, max: number} | null}
 */
export function recommendPropDiameter(motorSize) {
  const parsed = parseMotorSize(motorSize);
  if (!parsed) return null;
  const vol = statorVolume(parsed);
  const toDiameter = (v) => Math.pow(v / STATOR_COEFF, 1 / STATOR_EXP);
  const [lo, hi] = STATOR_BAND;
  return {
    min: round1(toDiameter(vol / hi)),
    ideal: round1(toDiameter(vol)),
    max: round1(toDiameter(vol / lo)),
  };
}

/** Pitch range for a diameter and flying style. */
export function recommendPitch(diameterIn, style = "freestyle") {
  const [lo, hi] = PITCH_RATIOS[normalizeStyle(style)];
  return { min: round1(diameterIn * lo), max: round1(diameterIn * hi) };
}

/** AUW range that puts total thrust in the style's thrust-to-weight band. */
export function recommendAuw(totalThrustGrams, style = "freestyle") {
  const [lo, hi] = TWR_BANDS[normalizeStyle(style)];
  return {
    min: Math.round(totalThrustGrams / hi),
    max: Math.round(totalThrustGrams / lo),
  };
}

function round1(n) {
  return Math.round(n * 10) / 10;
}

// ---------------------------------------------------------------------------
// Orchestration
// ---------------------------------------------------------------------------

/**
 * Compute every metric, recommendation, and verdict the given (possibly
 * partial) inputs allow.
 *
 * Advanced inputs (all optional): `loadFactor` overrides the 75% loaded-RPM
 * assumption; `cellVoltage` sets the per-cell voltage metrics are computed at
 * (recommendations always use `cellVoltageFull`, the community's full-charge
 * KV convention); `altitudeM` derates air density; `capacityMah` (with
 * `cellVoltageNominal` for energy) enables a hover-endurance estimate; and
 * `measuredThrustG` rescales the thrust model to a bench-tested value.
 *
 * @param {{
 *   diameterIn?: number, pitchIn?: number, blades?: number,
 *   motorSize?: string, kv?: number, cells?: number, auwGrams?: number,
 *   motorCount?: number, style?: string, loadFactor?: number,
 *   cellVoltage?: number, cellVoltageFull?: number, cellVoltageNominal?: number,
 *   altitudeM?: number, capacityMah?: number, measuredThrustG?: number,
 * }} inputs
 * @returns {{metrics: object, recommendations: object, verdicts: Array<{level: string, text: string}>}}
 */
export function analyze(inputs) {
  const {
    diameterIn,
    pitchIn,
    blades = 3,
    kv,
    cells,
    auwGrams,
    capacityMah,
    measuredThrustG,
  } = inputs;
  const style = normalizeStyle(inputs.style);
  const stator = parseMotorSize(inputs.motorSize);

  const has = (n) => typeof n === "number" && Number.isFinite(n) && n > 0;

  // Used as a divisor throughout, so an explicit 0/negative/NaN from a
  // programmatic caller must fall back to a quad rather than poison the math.
  const motorCount = has(inputs.motorCount) ? Math.round(inputs.motorCount) : 4;

  const loadFactor = has(inputs.loadFactor) ? inputs.loadFactor : DEFAULT_LOAD_FACTOR;
  const cellVoltage = has(inputs.cellVoltage) ? inputs.cellVoltage : CELL_VOLTAGE_FULL;
  const cellVoltageFull = has(inputs.cellVoltageFull) ? inputs.cellVoltageFull : CELL_VOLTAGE_FULL;
  const cellVoltageNominal = has(inputs.cellVoltageNominal)
    ? inputs.cellVoltageNominal
    : CELL_VOLTAGE_NOMINAL;
  const density = airDensityAtAltitude(inputs.altitudeM);

  const metrics = {};
  const recommendations = {};
  const verdicts = [];

  if (stator) metrics.statorVolumeMm3 = statorVolume(stator);
  if (has(cells)) metrics.voltage = cells * cellVoltage;
  if (has(inputs.altitudeM)) metrics.airDensity = density;

  if (has(kv) && has(cells)) {
    metrics.maxRpm = maxRpm(kv, metrics.voltage);
    metrics.loadedRpm = loadedRpm(kv, metrics.voltage, loadFactor);
  }

  if (has(diameterIn) && has(metrics.loadedRpm)) {
    metrics.tipSpeedMs = tipSpeedMs(diameterIn, metrics.loadedRpm);
    metrics.tipMach = machFraction(metrics.tipSpeedMs);
  }

  if (has(pitchIn) && has(metrics.loadedRpm)) {
    metrics.pitchSpeedKmh = pitchSpeedKmh(pitchIn, metrics.loadedRpm);
    metrics.pitchSpeedMph = metrics.pitchSpeedKmh / 1.609344;
  }

  if (has(diameterIn) && has(pitchIn) && has(metrics.loadedRpm)) {
    const motors = has(motorCount) ? motorCount : 4;
    metrics.thrustPerMotorG = staticThrustGrams(
      diameterIn,
      pitchIn,
      metrics.loadedRpm,
      blades,
      density,
    );
    if (has(measuredThrustG)) {
      metrics.calibrationFactor = measuredThrustG / metrics.thrustPerMotorG;
      metrics.thrustPerMotorG = measuredThrustG;
    }
    metrics.totalThrustG = metrics.thrustPerMotorG * motors;
    metrics.maxPowerW =
      electricalPowerWatts(metrics.thrustPerMotorG, diameterIn, 0.55, 0.85, density) *
      motors;
    metrics.maxCurrentA = metrics.maxPowerW / metrics.voltage;
    metrics.maxCurrentPerMotorA = metrics.maxCurrentA / motors;
  }

  if (has(auwGrams) && has(metrics.totalThrustG)) {
    metrics.twr = thrustToWeight(metrics.totalThrustG, auwGrams);
    metrics.hoverThrottlePct = hoverThrottlePercent(metrics.twr);
  }

  if (has(auwGrams) && has(diameterIn)) {
    const motors = has(motorCount) ? motorCount : 4;
    metrics.discLoadingGCm2 = discLoading(auwGrams, diameterIn, motors);
    if (has(metrics.voltage)) {
      metrics.hoverPowerW =
        electricalPowerWatts(auwGrams / motors, diameterIn, 0.65, 0.85, density) *
        motors;
      metrics.hoverCurrentA = metrics.hoverPowerW / metrics.voltage;
      if (has(capacityMah) && has(cells)) {
        const energyWh = (capacityMah / 1000) * cells * cellVoltageNominal;
        metrics.hoverFlightTimeMin = (energyWh * USABLE_BATTERY_FRACTION) /
          metrics.hoverPowerW * 60;
      }
    }
  }

  // --- Recommendations for whatever was left unset -------------------------

  if (!has(kv) && has(diameterIn) && has(cells)) {
    recommendations.kv = {
      ...recommendKv(diameterIn, cells * cellVoltageFull, style),
      basis: `${diameterIn}″ prop at ${cells}S`,
    };
  }

  if (!has(cells) && has(diameterIn) && has(kv)) {
    recommendations.cells = {
      ...recommendCellCount(diameterIn, kv, style),
      basis: `${diameterIn}″ prop at ${kv}KV`,
    };
  }

  if (!stator && has(diameterIn)) {
    recommendations.motorSizes = {
      ...recommendMotorSizes(diameterIn),
      basis: `${diameterIn}″ prop`,
    };
  }

  if (!has(diameterIn) && stator) {
    recommendations.diameter = {
      ...recommendPropDiameter(inputs.motorSize),
      basis: `${inputs.motorSize} stator`,
    };
  }

  if (!has(pitchIn) && has(diameterIn)) {
    recommendations.pitch = {
      ...recommendPitch(diameterIn, style),
      basis: `${diameterIn}″ prop, ${style}`,
    };
  }

  if (!has(auwGrams) && has(metrics.totalThrustG)) {
    recommendations.auw = {
      ...recommendAuw(metrics.totalThrustG, style),
      basis: `${Math.round(metrics.totalThrustG)}g total thrust, ${style}`,
    };
  }

  // --- Verdicts ------------------------------------------------------------

  if (has(metrics.twr)) {
    const twr = metrics.twr;
    if (twr < 1.3) {
      verdicts.push({
        level: "bad",
        text: `Thrust-to-weight ${
          twr.toFixed(1)
        }:1 — not enough thrust to hover reliably. This won't fly.`,
      });
    } else if (twr < 2.5) {
      verdicts.push({
        level: "warn",
        text: `Thrust-to-weight ${
          twr.toFixed(1)
        }:1 — very heavily loaded. Sluggish; only workable for heavy-lift or cinelifter duty.`,
      });
    } else if (twr < 5) {
      verdicts.push({
        level: "good",
        text: `Thrust-to-weight ${
          twr.toFixed(1)
        }:1 — smooth and efficient. Cinematic or long-range cruising territory.`,
      });
    } else if (twr < 8) {
      verdicts.push({
        level: "good",
        text: `Thrust-to-weight ${
          twr.toFixed(1)
        }:1 — relaxed freestyle. Playful with reasonable flight times.`,
      });
    } else if (twr < 13) {
      verdicts.push({
        level: "good",
        text: `Thrust-to-weight ${
          twr.toFixed(1)
        }:1 — modern freestyle sweet spot. Plenty of punch for tricks and race-capable.`,
      });
    } else {
      verdicts.push({
        level: "info",
        text: `Thrust-to-weight ${
          twr.toFixed(1)
        }:1 — race-spec violence. Demands throttle discipline; expect short flights.`,
      });
    }
  }

  if (has(metrics.tipMach)) {
    if (metrics.tipMach > 0.85) {
      verdicts.push({
        level: "warn",
        text: `Prop tips reach Mach ${
          metrics.tipMach.toFixed(2)
        } at full throttle — transonic tips are loud, inefficient, and hard on props. Consider lower KV, fewer cells, or a smaller prop.`,
      });
    } else if (metrics.tipMach > 0.7) {
      verdicts.push({
        level: "info",
        text: `Prop tips reach Mach ${
          metrics.tipMach.toFixed(2)
        } at full throttle — on the loud side, typical of aggressive builds.`,
      });
    }
  }

  if (has(metrics.hoverThrottlePct)) {
    if (metrics.hoverThrottlePct > 45) {
      verdicts.push({
        level: "warn",
        text: `Hovering near ${
          Math.round(metrics.hoverThrottlePct)
        }% throttle leaves little headroom for climbing or stopping a descent.`,
      });
    }
  }

  if (stator && has(diameterIn)) {
    const target = STATOR_COEFF * Math.pow(diameterIn, STATOR_EXP);
    const ratio = statorVolume(stator) / target;
    if (ratio < 0.6) {
      verdicts.push({
        level: "bad",
        text:
          `Motor looks undersized for a ${diameterIn}″ prop — expect bogging in hard maneuvers, hot motors, and mushy response.`,
      });
    } else if (ratio < 0.8) {
      verdicts.push({
        level: "warn",
        text:
          `Motor is on the small side for a ${diameterIn}″ prop — fine for light, efficient builds; may run warm when pushed.`,
      });
    } else if (ratio <= 1.3) {
      verdicts.push({
        level: "good",
        text: `Motor size is well matched to a ${diameterIn}″ prop.`,
      });
    } else if (ratio <= 1.8) {
      verdicts.push({
        level: "info",
        text:
          `Motor has torque to spare for a ${diameterIn}″ prop — authoritative, at the cost of some weight.`,
      });
    } else {
      verdicts.push({
        level: "warn",
        text:
          `Motor looks oversized for a ${diameterIn}″ prop — you're carrying motor weight the prop can't use.`,
      });
    }
  }

  if (has(metrics.calibrationFactor)) {
    const factor = metrics.calibrationFactor;
    const divergent = factor < 0.7 || factor > 1.4;
    verdicts.push({
      level: divergent ? "warn" : "info",
      text: `Thrust model calibrated ×${factor.toFixed(2)} to your measured ${
        Math.round(measuredThrustG)
      }g/motor${divergent ? " — the model diverges a lot here, trust the bench numbers" : ""}.`,
    });
  }

  if (has(kv) && has(cells) && has(diameterIn)) {
    const ideal = recommendKv(diameterIn, cells * cellVoltageFull, style).ideal;
    const ratio = kv / ideal;
    if (ratio > 1.25) {
      verdicts.push({
        level: "warn",
        text:
          `${kv}KV on ${cells}S over-revs a ${diameterIn}″ prop (ideal ≈ ${ideal}KV) — expect high current draw and heat.`,
      });
    } else if (ratio < 0.75) {
      verdicts.push({
        level: "warn",
        text:
          `${kv}KV on ${cells}S under-revs a ${diameterIn}″ prop (ideal ≈ ${ideal}KV) — soft top end; efficient but slow.`,
      });
    } else {
      verdicts.push({
        level: "good",
        text: `${kv}KV is well matched to a ${diameterIn}″ prop on ${cells}S.`,
      });
    }
  }

  return { metrics, recommendations, verdicts };
}
