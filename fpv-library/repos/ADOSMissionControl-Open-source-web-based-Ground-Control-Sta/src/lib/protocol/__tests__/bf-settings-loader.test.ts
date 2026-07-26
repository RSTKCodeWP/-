/**
 * @module protocol/bf-settings-loader.test
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { bfCatalogVersionKey, pickBfCatalog, SHIPPED_BF_CATALOGS } from "../param-metadata/bf-settings";

describe("bfCatalogVersionKey", () => {
  it("extracts a MAJOR.MINOR key from a version string", () => {
    expect(bfCatalogVersionKey("2026.6.0-alpha")).toBe("2026.6");
    expect(bfCatalogVersionKey("BTFL 2026.6.0 (MSP API 1.47)")).toBe("2026.6");
    expect(bfCatalogVersionKey("4.5.1")).toBe("4.5");
    expect(bfCatalogVersionKey(undefined)).toBeNull();
    expect(bfCatalogVersionKey("no-numbers")).toBeNull();
  });
});

describe("pickBfCatalog", () => {
  it("returns the exact shipped catalog when the version matches", () => {
    expect(pickBfCatalog("2026.6.0-alpha")).toBe("2026.6");
  });
  it("falls back to the newest shipped catalog on a mismatch or no version", () => {
    expect(pickBfCatalog("9.9.9")).toBe(SHIPPED_BF_CATALOGS[0]);
    expect(pickBfCatalog(undefined)).toBe(SHIPPED_BF_CATALOGS[0]);
  });
});
