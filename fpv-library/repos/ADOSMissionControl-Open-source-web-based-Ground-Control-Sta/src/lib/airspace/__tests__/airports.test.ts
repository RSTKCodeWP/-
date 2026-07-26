import { describe, it, expect } from "vitest";
import { MAJOR_AIRPORTS, nearestAirport } from "../airports";

describe("MAJOR_AIRPORTS dataset", () => {
  it("holds a reasonable number of unique airports with valid coordinates", () => {
    expect(MAJOR_AIRPORTS.length).toBeGreaterThanOrEqual(40);
    const icaos = new Set(MAJOR_AIRPORTS.map((a) => a.icao));
    expect(icaos.size).toBe(MAJOR_AIRPORTS.length); // no duplicate ICAO codes
    for (const a of MAJOR_AIRPORTS) {
      expect(a.icao).toMatch(/^[A-Z]{4}$/);
      expect(a.lat).toBeGreaterThanOrEqual(-90);
      expect(a.lat).toBeLessThanOrEqual(90);
      expect(a.lon).toBeGreaterThanOrEqual(-180);
      expect(a.lon).toBeLessThanOrEqual(180);
    }
  });
});

describe("nearestAirport", () => {
  it("returns the on-field airport for a coordinate near LAX", () => {
    // A point ~1 km from the LAX reference point.
    const result = nearestAirport(33.95, -118.4);
    expect(result).not.toBeNull();
    expect(result!.airport.icao).toBe("KLAX");
    expect(result!.distanceKm).toBeLessThan(3);
  });

  it("returns the on-field airport for a coordinate near Bengaluru", () => {
    const result = nearestAirport(13.1986, 77.7066);
    expect(result).not.toBeNull();
    expect(result!.airport.icao).toBe("VOBL");
    expect(result!.distanceKm).toBeLessThan(0.5);
  });

  it("returns a large distance for a remote ocean point", () => {
    // Middle of the South Pacific — far from any airport in the set.
    const result = nearestAirport(-40, -140);
    expect(result).not.toBeNull();
    expect(result!.distanceKm).toBeGreaterThan(1000);
  });
});
