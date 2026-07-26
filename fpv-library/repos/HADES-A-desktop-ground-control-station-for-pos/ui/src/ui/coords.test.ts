import { describe, expect, it } from "vitest";

import { formatDDM, formatMGRS, formatContactCoord } from "./coords";

/* Coordinate readout (DESIGN-SYSTEM §6.3a): two canonical formats, one per role. MGRS/USNG
 * is the PRIMARY (ground SAR radio), WGS84 DDM the secondary (air/CG). Datum-explicit,
 * radio-speakable, fixed precision. Null fix → an honest "NO FIX", never a phantom coord. */

describe("formatDDM", () => {
  it("formats degrees-decimal-minutes with hemisphere letters", () => {
    // 30.215, -88.52 → N30 12.900  W088 31.200
    const s = formatDDM(30.215, -88.52);
    expect(s).toMatch(/^N30 12\.9\d{2}\s+W088 31\.\d{3}$/);
  });

  it("uses S/E for the southern/eastern hemispheres", () => {
    expect(formatDDM(-1.5, 1.5)).toMatch(/^S01 .* E001 /);
  });
});

describe("formatMGRS", () => {
  it("produces a USNG/MGRS grid string for a valid coordinate", () => {
    const s = formatMGRS(30.215, -88.52);
    // e.g. "16R EU 1234 5678" — zone digits, band letter, 100km square, then easting/northing
    expect(s).toMatch(/^\d{1,2}[C-X] [A-Z]{2} \d+ \d+$/);
  });
});

describe("formatContactCoord", () => {
  it("returns BOTH roles (grid primary + DDM secondary) with the datum tag", () => {
    const out = formatContactCoord(30.215, -88.52, "HAE");
    expect(out.grid).toMatch(/^\d{1,2}[C-X] [A-Z]{2} \d+ \d+$/);
    expect(out.geographic).toMatch(/^N30 /);
    expect(out.datum).toBe("HAE");
  });

  it("a null fix is an HONEST no-fix, never a phantom coordinate", () => {
    const out = formatContactCoord(null, null, "UNKNOWN");
    expect(out.grid).toBe("NO FIX");
    expect(out.geographic).toBe("NO FIX");
  });
});
