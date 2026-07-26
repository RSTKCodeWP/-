import { describe, it, expect } from "vitest";
import { sunTimesFor, sunPosition, isGoldenHour } from "@/lib/sun-times";

// Bangalore, India (mid-latitude Northern Hemisphere).
const LAT = 12.9716;
const LON = 77.5946;
// A morning instant on the June solstice; getTimes resolves that calendar day.
const DAY = new Date("2026-06-21T04:00:00Z");

describe("sunTimesFor", () => {
  it("orders sunrise < solarNoon < sunset", () => {
    const t = sunTimesFor(DAY, LAT, LON);
    expect(t.sunrise.getTime()).toBeLessThan(t.solarNoon.getTime());
    expect(t.solarNoon.getTime()).toBeLessThan(t.sunset.getTime());
  });

  it("nests the golden-hour bounds inside the daylight window", () => {
    const t = sunTimesFor(DAY, LAT, LON);
    // Morning golden hour ends after sunrise; evening starts before sunset.
    expect(t.goldenHourEnd.getTime()).toBeGreaterThan(t.sunrise.getTime());
    expect(t.goldenHourEnd.getTime()).toBeLessThan(t.solarNoon.getTime());
    expect(t.goldenHourStart.getTime()).toBeGreaterThan(t.solarNoon.getTime());
    expect(t.goldenHourStart.getTime()).toBeLessThan(t.sunset.getTime());
  });
});

describe("sunPosition", () => {
  it("puts the sun above the horizon near local noon", () => {
    const t = sunTimesFor(DAY, LAT, LON);
    const p = sunPosition(t.solarNoon, LAT, LON);
    expect(p.altitudeDeg).toBeGreaterThan(0);
    expect(p.altitudeDeg).toBeLessThanOrEqual(90);
  });

  it("returns a compass azimuth normalized to [0, 360)", () => {
    const t = sunTimesFor(DAY, LAT, LON);
    const p = sunPosition(t.solarNoon, LAT, LON);
    expect(p.azimuthDeg).toBeGreaterThanOrEqual(0);
    expect(p.azimuthDeg).toBeLessThan(360);
  });

  it("has the sun below the horizon at local midnight", () => {
    const midnight = new Date("2026-06-21T18:30:00Z"); // ~00:00 IST
    expect(sunPosition(midnight, LAT, LON).altitudeDeg).toBeLessThan(0);
  });
});

describe("isGoldenHour", () => {
  it("returns a boolean", () => {
    expect(typeof isGoldenHour(DAY, LAT, LON)).toBe("boolean");
  });

  it("is false at solar noon (sun high overhead)", () => {
    const t = sunTimesFor(DAY, LAT, LON);
    expect(isGoldenHour(t.solarNoon, LAT, LON)).toBe(false);
  });

  it("is true shortly after sunrise (inside the golden-hour band)", () => {
    const t = sunTimesFor(DAY, LAT, LON);
    const justAfterSunrise = new Date(t.sunrise.getTime() + 5 * 60_000);
    expect(isGoldenHour(justAfterSunrise, LAT, LON)).toBe(true);
  });
});
