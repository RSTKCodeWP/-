/**
 * @module weather-go-no-go.test
 * @description Boundary coverage for the deterministic flight go/no-go
 * assessment: wind + gust caution/no-go thresholds, worst-of escalation, the
 * no-data conservative default, and custom-threshold overrides.
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import {
  assessWeather,
  DEFAULT_WEATHER_THRESHOLDS,
  type WeatherThresholds,
} from "@/lib/weather/go-no-go";

const T = DEFAULT_WEATHER_THRESHOLDS;

describe("assessWeather — wind thresholds", () => {
  it("clears GO below the caution wind threshold", () => {
    const r = assessWeather({ windSpeedMps: T.cautionWindMps - 0.01, windGustMps: 0 });
    expect(r.level).toBe("go");
    expect(r.reasons).toEqual([]);
  });

  it("escalates to CAUTION exactly at the caution wind threshold", () => {
    const r = assessWeather({ windSpeedMps: T.cautionWindMps, windGustMps: 0 });
    expect(r.level).toBe("caution");
    expect(r.reasons).toContain("windCaution");
  });

  it("stays CAUTION just below the no-go wind threshold", () => {
    const r = assessWeather({ windSpeedMps: T.nogoWindMps - 0.01, windGustMps: 0 });
    expect(r.level).toBe("caution");
    expect(r.reasons).toContain("windCaution");
  });

  it("escalates to NO-GO exactly at the no-go wind threshold", () => {
    const r = assessWeather({ windSpeedMps: T.nogoWindMps, windGustMps: 0 });
    expect(r.level).toBe("nogo");
    expect(r.reasons).toContain("windNogo");
    expect(r.reasons).not.toContain("windCaution");
  });
});

describe("assessWeather — gust thresholds", () => {
  it("clears GO below the caution gust threshold", () => {
    const r = assessWeather({ windSpeedMps: 0, windGustMps: T.cautionGustMps - 0.01 });
    expect(r.level).toBe("go");
    expect(r.reasons).toEqual([]);
  });

  it("escalates to CAUTION exactly at the caution gust threshold", () => {
    const r = assessWeather({ windSpeedMps: 0, windGustMps: T.cautionGustMps });
    expect(r.level).toBe("caution");
    expect(r.reasons).toContain("gustCaution");
  });

  it("escalates to NO-GO exactly at the no-go gust threshold", () => {
    const r = assessWeather({ windSpeedMps: 0, windGustMps: T.nogoGustMps });
    expect(r.level).toBe("nogo");
    expect(r.reasons).toContain("gustNogo");
  });
});

describe("assessWeather — worst-of escalation", () => {
  it("takes the more severe level when wind cautions but gusts are no-go", () => {
    const r = assessWeather({ windSpeedMps: T.cautionWindMps, windGustMps: T.nogoGustMps });
    expect(r.level).toBe("nogo");
    expect(r.reasons).toContain("windCaution");
    expect(r.reasons).toContain("gustNogo");
  });

  it("takes the more severe level when wind is no-go but gusts are calm", () => {
    const r = assessWeather({ windSpeedMps: T.nogoWindMps, windGustMps: 1 });
    expect(r.level).toBe("nogo");
    expect(r.reasons).toEqual(["windNogo"]);
  });
});

describe("assessWeather — missing data", () => {
  it("returns conservative CAUTION with a noData reason when both are null", () => {
    const r = assessWeather({ windSpeedMps: null, windGustMps: null });
    expect(r.level).toBe("caution");
    expect(r.reasons).toEqual(["noData"]);
  });

  it("judges from gust alone when wind is null", () => {
    const r = assessWeather({ windSpeedMps: null, windGustMps: T.cautionGustMps - 0.01 });
    expect(r.level).toBe("go");
    expect(r.reasons).toEqual([]);
  });

  it("judges from wind alone when gust is null", () => {
    const r = assessWeather({ windSpeedMps: T.nogoWindMps, windGustMps: null });
    expect(r.level).toBe("nogo");
    expect(r.reasons).toEqual(["windNogo"]);
  });

  it("treats non-finite readings as missing", () => {
    const r = assessWeather({ windSpeedMps: NaN, windGustMps: NaN });
    expect(r.level).toBe("caution");
    expect(r.reasons).toEqual(["noData"]);
  });
});

describe("assessWeather — custom thresholds", () => {
  it("honours a stricter airframe override", () => {
    const strict: WeatherThresholds = {
      cautionWindMps: 4,
      nogoWindMps: 6,
      cautionGustMps: 5,
      nogoGustMps: 7,
    };
    const r = assessWeather({ windSpeedMps: 6, windGustMps: 2 }, strict);
    expect(r.level).toBe("nogo");
    expect(r.reasons).toContain("windNogo");
  });
});
