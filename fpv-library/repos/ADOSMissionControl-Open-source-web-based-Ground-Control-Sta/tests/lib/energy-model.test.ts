import { describe, it, expect } from "vitest";
import {
  estimateEnergyWh,
  segmentByBattery,
  windDerate,
  tempDerate,
} from "@/lib/energy-model";

describe("estimateEnergyWh", () => {
  it("gives a sane Wh and flight time for a known distance and power", () => {
    // 3600 m at 10 m/s = 360 s = 0.1 h of cruise at 200 W = 20 Wh.
    const est = estimateEnergyWh({
      distanceM: 3600,
      cruiseSpeedMps: 10,
      hoverWatts: 300,
      cruiseWatts: 200,
    });
    expect(est.cruiseSeconds).toBeCloseTo(360, 6);
    expect(est.totalWh).toBeCloseTo(20, 6);
    expect(est.cruiseWh).toBeCloseTo(20, 6);
    expect(est.hoverWh).toBe(0);
    expect(est.flightMinutes).toBeCloseTo(6, 6);
    expect(est.effectiveCruiseWatts).toBe(200);
  });

  it("adds hover energy and hover time", () => {
    // 60 s hover at 300 W = 5 Wh on top of the 20 Wh cruise.
    const est = estimateEnergyWh({
      distanceM: 3600,
      cruiseSpeedMps: 10,
      hoverWatts: 300,
      cruiseWatts: 200,
      hoverSeconds: 60,
    });
    expect(est.hoverWh).toBeCloseTo(5, 6);
    expect(est.totalWh).toBeCloseTo(25, 6);
    expect(est.flightMinutes).toBeCloseTo(7, 6);
  });

  it("raises cruise energy for a headwind", () => {
    const still = estimateEnergyWh({
      distanceM: 3600,
      cruiseSpeedMps: 10,
      hoverWatts: 300,
      cruiseWatts: 200,
    });
    const headwind = estimateEnergyWh({
      distanceM: 3600,
      cruiseSpeedMps: 10,
      hoverWatts: 300,
      cruiseWatts: 200,
      windMps: 5,
      headwind: true,
    });
    // 3% per m/s * 5 m/s = +15% cruise power.
    expect(headwind.effectiveCruiseWatts).toBeCloseTo(230, 6);
    expect(headwind.totalWh).toBeGreaterThan(still.totalWh);
    expect(headwind.cruiseWh).toBeCloseTo(23, 6);
  });

  it("yields zero cruise energy when the speed is non-positive", () => {
    const est = estimateEnergyWh({
      distanceM: 3600,
      cruiseSpeedMps: 0,
      hoverWatts: 300,
      cruiseWatts: 200,
      hoverSeconds: 120,
    });
    expect(est.cruiseSeconds).toBe(0);
    expect(est.cruiseWh).toBe(0);
    // Only the hover contribution remains: 120 s at 300 W = 10 Wh.
    expect(est.totalWh).toBeCloseTo(10, 6);
    expect(est.flightMinutes).toBeCloseTo(2, 6);
  });
});

describe("segmentByBattery", () => {
  it("splits energy across packs holding back the reserve", () => {
    // 100 Wh pack, 20% reserve -> 80 Wh usable each. 200 Wh needs 3 packs.
    const seg = segmentByBattery(200, 100, 0.2);
    expect(seg.usablePerBatteryWh).toBeCloseTo(80, 6);
    expect(seg.batteriesNeeded).toBe(3);
    expect(seg.swaps).toBe(2);
    expect(seg.segments).toHaveLength(3);
    expect(seg.segments[0]).toBeCloseTo(80, 6);
    expect(seg.segments[1]).toBeCloseTo(80, 6);
    expect(seg.segments[2]).toBeCloseTo(40, 6);
    // Segments sum back to the total demand.
    const sum = seg.segments.reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(200, 6);
  });

  it("needs a single pack and no swaps when demand fits the usable capacity", () => {
    const seg = segmentByBattery(80, 100, 0.2);
    expect(seg.batteriesNeeded).toBe(1);
    expect(seg.swaps).toBe(0);
    expect(seg.segments).toEqual([80]);
  });

  it("uses the default 20% reserve when none is given", () => {
    const seg = segmentByBattery(80, 100);
    expect(seg.usablePerBatteryWh).toBeCloseTo(80, 6);
    expect(seg.batteriesNeeded).toBe(1);
  });

  it("needs more packs as the reserve grows", () => {
    const low = segmentByBattery(200, 100, 0.2);
    const high = segmentByBattery(200, 100, 0.5);
    expect(high.batteriesNeeded).toBeGreaterThan(low.batteriesNeeded);
    expect(high.usablePerBatteryWh).toBeCloseTo(50, 6);
    expect(high.batteriesNeeded).toBe(4);
  });

  it("returns no packs for zero energy demand", () => {
    const seg = segmentByBattery(0, 100, 0.2);
    expect(seg.batteriesNeeded).toBe(0);
    expect(seg.swaps).toBe(0);
    expect(seg.segments).toEqual([]);
  });

  it("signals infeasibility with a zero-capacity pack", () => {
    const seg = segmentByBattery(200, 0, 0.2);
    expect(Number.isFinite(seg.batteriesNeeded)).toBe(false);
    expect(seg.usablePerBatteryWh).toBe(0);
    expect(seg.segments).toEqual([]);
  });
});

describe("windDerate", () => {
  it("raises power for a headwind", () => {
    expect(windDerate(200, 5, true)).toBeCloseTo(230, 6);
    expect(windDerate(200, 5, true)).toBeGreaterThan(200);
  });

  it("lowers power for a tailwind", () => {
    expect(windDerate(200, 5, false)).toBeCloseTo(170, 6);
    expect(windDerate(200, 5, false)).toBeLessThan(200);
  });

  it("leaves power unchanged in still air", () => {
    expect(windDerate(200, 0, true)).toBe(200);
    expect(windDerate(200, 0, false)).toBe(200);
  });

  it("defaults to treating wind as a headwind", () => {
    expect(windDerate(200, 5)).toBeCloseTo(230, 6);
  });

  it("floors a strong tailwind above zero power", () => {
    // 3% per m/s * 100 m/s would go negative; the floor holds it at 50%.
    expect(windDerate(200, 100, false)).toBeCloseTo(100, 6);
  });
});

describe("tempDerate", () => {
  it("returns rated capacity at the nominal temperature", () => {
    expect(tempDerate(100, 25)).toBeCloseTo(100, 6);
  });

  it("loses capacity in the cold", () => {
    // 20 C below nominal at 1% per C = -20%.
    expect(tempDerate(100, 5)).toBeCloseTo(80, 6);
    expect(tempDerate(100, 5)).toBeLessThan(100);
  });

  it("loses a little capacity in the heat", () => {
    // 20 C above nominal at 0.5% per C = -10%.
    expect(tempDerate(100, 45)).toBeCloseTo(90, 6);
    expect(tempDerate(100, 45)).toBeLessThan(100);
  });

  it("floors usable capacity at extreme cold", () => {
    expect(tempDerate(100, -80)).toBeCloseTo(40, 6);
  });
});
