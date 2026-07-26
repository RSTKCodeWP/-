import { describe, expect, it } from "vitest";

import { formatUtcClock, formatAge } from "./format";

/* Display formatters — one canonical format per quantity, used identically everywhere
 * (DESIGN-SYSTEM anti-slop #3). Time = UTC HH:MM:SSZ; age = compact M:SS. */

describe("formatUtcClock", () => {
  it("formats a Date as zero-padded UTC HH:MM:SSZ", () => {
    const d = new Date(Date.UTC(2026, 5, 25, 14, 22, 7));
    expect(formatUtcClock(d)).toBe("14:22:07Z");
  });

  it("zero-pads single-digit fields", () => {
    const d = new Date(Date.UTC(2026, 0, 1, 1, 2, 3));
    expect(formatUtcClock(d)).toBe("01:02:03Z");
  });
});

describe("formatAge", () => {
  it("formats seconds as M:SS", () => {
    expect(formatAge(3)).toBe("0:03");
    expect(formatAge(41)).toBe("0:41");
    expect(formatAge(138)).toBe("2:18");
  });

  it("floors fractional seconds", () => {
    expect(formatAge(3.9)).toBe("0:03");
  });
});
