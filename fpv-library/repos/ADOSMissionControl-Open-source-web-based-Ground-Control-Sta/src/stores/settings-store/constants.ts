/**
 * Static defaults and shared shape helpers for the persisted settings store.
 *
 * Lives apart from the store itself so the migration module and the test
 * suite can pull them in without having to import every action and reactive
 * hook from settings-store.ts.
 *
 * @license GPL-3.0-only
 */

import type {
  ParamColumnVisibility,
  TelemetryDeckMetricId,
  TelemetryDeckPageId,
} from "@/stores/settings-store-types";

export const DEFAULT_PARAM_COLUMNS: ParamColumnVisibility = {
  index: true,
  name: true,
  description: false,
  value: true,
  range: true,
  units: true,
  type: false,
  options: true,
};

export const DEFAULT_TELEMETRY_DECK_PAGES: Record<TelemetryDeckPageId, TelemetryDeckMetricId[]> = {
  flight: ["relAlt", "airspeed", "groundspeedMs", "climbRate", "roll", "pitch", "yaw", "windSpeed"],
  link: ["radioRssi", "remrssi", "noise", "remnoise", "rxerrors", "txbuf", "gpsFix", "satellites"],
  power: ["batteryVoltage", "batteryCurrent", "powerWatts", "batteryConsumed", "estFlightMin", "throttle"],
  tuning: ["roll", "pitch", "yaw", "vibeX", "vibeY", "vibeZ", "ekfVelRatio", "ekfPosHorizRatio"],
};

export function cloneDefaultTelemetryDeckPages(): Record<TelemetryDeckPageId, TelemetryDeckMetricId[]> {
  return {
    flight: [...DEFAULT_TELEMETRY_DECK_PAGES.flight],
    link: [...DEFAULT_TELEMETRY_DECK_PAGES.link],
    power: [...DEFAULT_TELEMETRY_DECK_PAGES.power],
    tuning: [...DEFAULT_TELEMETRY_DECK_PAGES.tuning],
  };
}

function arraysEqual(a: TelemetryDeckMetricId[], b: TelemetryDeckMetricId[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

export function normalizeTelemetryDeckPages(
  rawPages: unknown,
): Record<TelemetryDeckPageId, TelemetryDeckMetricId[]> {
  const raw = (rawPages ?? {}) as Partial<Record<TelemetryDeckPageId, unknown>>;
  const defaults = cloneDefaultTelemetryDeckPages();

  const sanitize = (page: TelemetryDeckPageId): TelemetryDeckMetricId[] => {
    const candidate = raw[page];
    if (!Array.isArray(candidate)) return defaults[page];
    const filtered = candidate.filter((m): m is TelemetryDeckMetricId => typeof m === "string");
    const deduped = [...new Set(filtered)] as TelemetryDeckMetricId[];
    return deduped.length > 0 ? deduped : defaults[page];
  };

  const normalized: Record<TelemetryDeckPageId, TelemetryDeckMetricId[]> = {
    flight: sanitize("flight"),
    link: sanitize("link"),
    power: sanitize("power"),
    tuning: sanitize("tuning"),
  };

  // Repair a common bad state: non-flight pages copied from default flight page.
  const matchesDefaultFlight = arraysEqual(normalized.flight, defaults.flight);
  if (matchesDefaultFlight && arraysEqual(normalized.link, normalized.flight)) {
    normalized.link = defaults.link;
  }
  if (matchesDefaultFlight && arraysEqual(normalized.power, normalized.flight)) {
    normalized.power = defaults.power;
  }
  if (matchesDefaultFlight && arraysEqual(normalized.tuning, normalized.flight)) {
    normalized.tuning = defaults.tuning;
  }

  return normalized;
}
