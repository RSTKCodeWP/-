import { describe, expect, it } from "vitest";

import { statusGlyph, statusTextClass, statusToken } from "./status";

/* The status encoding is a closed state-machine with ONE encoding everywhere
 * (DESIGN-SYSTEM §6.4): every severity maps to exactly one color token AND one glyph, so
 * pin / row / panel / strip never disagree, and color is always backed by a shape. */

describe("status encoding", () => {
  it("maps every severity to its single design-system color token", () => {
    expect(statusToken("nominal")).toBe("st-nominal");
    expect(statusToken("info")).toBe("st-info");
    expect(statusToken("caution")).toBe("st-caution");
    expect(statusToken("warning")).toBe("st-warning");
    expect(statusToken("critical")).toBe("st-critical");
    expect(statusToken("stale")).toBe("st-stale");
  });

  it("gives every severity a non-color glyph backup (CVD/glare survival, §6.5)", () => {
    for (const sev of ["nominal", "info", "caution", "warning", "critical", "stale"] as const) {
      expect(statusGlyph(sev).length).toBeGreaterThan(0);
    }
  });

  it("warning and critical have DISTINCT glyphs (the survivor vs system-failure pair)", () => {
    expect(statusGlyph("warning")).not.toBe(statusGlyph("critical"));
  });

  it("emits a tailwind text-color class bound to the token", () => {
    expect(statusTextClass("critical")).toBe("text-st-critical");
  });
});
