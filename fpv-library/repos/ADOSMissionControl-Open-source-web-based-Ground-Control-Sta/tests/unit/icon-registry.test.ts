import { describe, it, expect } from "vitest";
import {
  normalizeIconName,
  resolveNamedIcon,
  hasNamedIcon,
  FALLBACK_ICON,
} from "@/lib/icons/icon-registry";

describe("icon-registry normalizeIconName", () => {
  it("lowercases and strips separators", () => {
    expect(normalizeIconName("Crosshair")).toBe("crosshair");
    expect(normalizeIconName("cross-hair")).toBe("crosshair");
    expect(normalizeIconName("cross_hair")).toBe("crosshair");
    expect(normalizeIconName("ArrowUpFromLine")).toBe("arrowupfromline");
    expect(normalizeIconName("zoom-in")).toBe("zoomin");
  });
});

describe("icon-registry resolveNamedIcon", () => {
  it("resolves lowercase-kebab plugin names (the shipped manifest form)", () => {
    // The exact names that fell back to a generic glyph before the fix.
    for (const name of ["crosshair", "camera", "gimbal", "thermometer", "compass"]) {
      expect(resolveNamedIcon(name)).not.toBe(FALLBACK_ICON);
    }
  });

  it("resolves the legacy PascalCase built-in names with zero data migration", () => {
    for (const name of [
      "Power",
      "ArrowUpFromLine",
      "ArrowDownToLine",
      "Home",
      "Pause",
      "Play",
      "XOctagon",
      "Skull",
      "LocateFixed",
      "MoveVertical",
      "Crosshair",
      "Navigation",
      "Route",
    ]) {
      expect(resolveNamedIcon(name)).not.toBe(FALLBACK_ICON);
    }
  });

  it("resolves camera/gimbal/vision vocabulary used by the retrofit plugins", () => {
    for (const name of [
      "zoom-in",
      "zoom-out",
      "palette",
      "record",
      "photo",
      "nadir",
      "recenter",
      "point-at",
      "designate",
      "laser",
      "follow",
    ]) {
      expect(resolveNamedIcon(name)).not.toBe(FALLBACK_ICON);
    }
  });

  it("is case- and separator-insensitive for the same glyph", () => {
    expect(resolveNamedIcon("crosshair")).toBe(resolveNamedIcon("Cross-Hair"));
    expect(resolveNamedIcon("zoomin")).toBe(resolveNamedIcon("Zoom In"));
  });

  it("falls back to the generic glyph for unknown or empty names", () => {
    expect(resolveNamedIcon("totally-unknown-xyz")).toBe(FALLBACK_ICON);
    expect(resolveNamedIcon("")).toBe(FALLBACK_ICON);
    expect(resolveNamedIcon(undefined)).toBe(FALLBACK_ICON);
    expect(resolveNamedIcon(null)).toBe(FALLBACK_ICON);
  });
});

describe("icon-registry hasNamedIcon", () => {
  it("reports membership honestly", () => {
    expect(hasNamedIcon("camera")).toBe(true);
    expect(hasNamedIcon("Camera")).toBe(true);
    expect(hasNamedIcon("nope-not-here")).toBe(false);
    expect(hasNamedIcon(undefined)).toBe(false);
  });
});
