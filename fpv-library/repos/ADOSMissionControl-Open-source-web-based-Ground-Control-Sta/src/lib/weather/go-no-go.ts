/**
 * @module weather/go-no-go
 * @description Deterministic flight go / caution / no-go judgment from surface
 * wind speed + gusts. Pure and side-effect-free (unit-tested). Thresholds are
 * documented constants tuned for a small multirotor; callers may override per
 * airframe. Returns a level plus machine-readable reason codes the UI layer
 * translates — the function itself stays i18n-free.
 * @license GPL-3.0-only
 */

import type { WeatherReport } from "./open-meteo";

export type GoNoGoLevel = "go" | "caution" | "nogo";

/**
 * Reason codes explaining a caution / no-go verdict. The UI maps each to a
 * localized string; the assessment never returns human prose.
 */
export type WeatherReasonCode =
  | "windCaution"
  | "windNogo"
  | "gustCaution"
  | "gustNogo"
  | "noData";

export interface WeatherThresholds {
  /** Sustained 10 m wind (m/s) at/above which the verdict is CAUTION. */
  cautionWindMps: number;
  /** Sustained 10 m wind (m/s) at/above which the verdict is NO-GO. */
  nogoWindMps: number;
  /** Gust (m/s) at/above which the verdict is CAUTION. */
  cautionGustMps: number;
  /** Gust (m/s) at/above which the verdict is NO-GO. */
  nogoGustMps: number;
}

/**
 * Default thresholds for a small multirotor carrying the ADOS stack.
 * Consumer / prosumer multirotors publish a wind-resistance ceiling around
 * 10–12 m/s, so sustained wind gates CAUTION at 8 m/s and NO-GO at 12 m/s.
 * Gusts are transient but destabilising, so they sit one band higher
 * (10 / 14 m/s). Override per airframe via the `thresholds` argument.
 */
export const DEFAULT_WEATHER_THRESHOLDS: WeatherThresholds = {
  cautionWindMps: 8,
  nogoWindMps: 12,
  cautionGustMps: 10,
  nogoGustMps: 14,
};

const SEVERITY: Record<GoNoGoLevel, number> = { go: 0, caution: 1, nogo: 2 };

/** Return the more severe of two levels. */
function worst(a: GoNoGoLevel, b: GoNoGoLevel): GoNoGoLevel {
  return SEVERITY[a] >= SEVERITY[b] ? a : b;
}

export interface WeatherAssessment {
  level: GoNoGoLevel;
  reasons: WeatherReasonCode[];
}

/**
 * Assess a flight go/no-go from surface wind + gust. Each finite input that
 * crosses a threshold contributes a reason and escalates the level; the
 * returned level is the worst any input reached. When neither wind nor gust is
 * available the verdict is CAUTION with a `noData` reason — a flight is never
 * cleared without wind data.
 */
export function assessWeather(
  report: Pick<WeatherReport, "windSpeedMps" | "windGustMps">,
  thresholds: WeatherThresholds = DEFAULT_WEATHER_THRESHOLDS,
): WeatherAssessment {
  const wind = report.windSpeedMps;
  const gust = report.windGustMps;
  const windFinite = typeof wind === "number" && Number.isFinite(wind);
  const gustFinite = typeof gust === "number" && Number.isFinite(gust);

  if (!windFinite && !gustFinite) {
    return { level: "caution", reasons: ["noData"] };
  }

  let level: GoNoGoLevel = "go";
  const reasons: WeatherReasonCode[] = [];

  if (typeof wind === "number" && Number.isFinite(wind)) {
    if (wind >= thresholds.nogoWindMps) {
      level = worst(level, "nogo");
      reasons.push("windNogo");
    } else if (wind >= thresholds.cautionWindMps) {
      level = worst(level, "caution");
      reasons.push("windCaution");
    }
  }

  if (typeof gust === "number" && Number.isFinite(gust)) {
    if (gust >= thresholds.nogoGustMps) {
      level = worst(level, "nogo");
      reasons.push("gustNogo");
    } else if (gust >= thresholds.cautionGustMps) {
      level = worst(level, "caution");
      reasons.push("gustCaution");
    }
  }

  return { level, reasons };
}
