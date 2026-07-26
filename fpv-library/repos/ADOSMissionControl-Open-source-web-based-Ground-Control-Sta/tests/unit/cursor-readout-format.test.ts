/**
 * Unit tests for the cursor-readout coordinate formatter. Asserts the
 * `coordFormat` switch routes to the right presentation for each of the four
 * display formats (dd / dms / utm / mgrs) without rendering the overlay.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { formatCursorCoord } from "@/lib/planner/cursor-coord";

// A concrete reference point (Bangalore) → UTM zone 43, latitude band P.
const LAT = 12.9716;
const LON = 77.5946;

describe("formatCursorCoord", () => {
  it("dd gives signed decimal degrees to 6 places", () => {
    expect(formatCursorCoord(LAT, LON, "dd")).toBe("12.971600, 77.594600");
  });

  it("dd carries the sign of a southern/western point", () => {
    const out = formatCursorCoord(-33.8688, 151.2093, "dd");
    expect(out).toBe("-33.868800, 151.209300");
  });

  it("dms renders degree/minute/second with hemisphere letters", () => {
    const out = formatCursorCoord(LAT, LON, "dms");
    expect(out).toContain("°");
    expect(out).toContain("'");
    expect(out).toContain('"');
    // Northern + eastern hemisphere for the reference point.
    expect(out).toContain(" N");
    expect(out).toContain(" E");
  });

  it("utm gives a compact zone + band + rounded easting/northing string", () => {
    const out = formatCursorCoord(LAT, LON, "utm");
    // "<zone><band> <easting>E <northing>N", integer metres.
    expect(out).toMatch(/^\d+[A-Z] \d+E \d+N$/);
    expect(out.startsWith("43P ")).toBe(true);
  });

  it("mgrs gives the compact grid reference (zone + band prefix)", () => {
    const out = formatCursorCoord(LAT, LON, "mgrs");
    expect(out.startsWith("43P")).toBe(true);
    expect(out.length).toBeGreaterThan(5);
  });

  it("routes each format to a distinct presentation", () => {
    const dd = formatCursorCoord(LAT, LON, "dd");
    const dms = formatCursorCoord(LAT, LON, "dms");
    const utm = formatCursorCoord(LAT, LON, "utm");
    const mgrs = formatCursorCoord(LAT, LON, "mgrs");
    const all = new Set([dd, dms, utm, mgrs]);
    expect(all.size).toBe(4);
  });
});
