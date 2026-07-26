/**
 * @license GPL-3.0-only
 *
 * Regression test for MSP FC-variant classification. The detector must not
 * default an empty variant (an API_VERSION reply, which confirms MSP but names
 * no family) to Betaflight — otherwise an iNav board whose API_VERSION arrives
 * before its FC_VARIANT is mislabeled.
 */

import { describe, it, expect } from "vitest";

import { classifyMspVariant } from "../detector";

describe("classifyMspVariant", () => {
  it("maps the recognized identifiers to their families", () => {
    expect(classifyMspVariant("INAV")).toBe("inav");
    expect(classifyMspVariant("BTFL")).toBe("betaflight");
  });

  it("is case- and whitespace-insensitive on the identifier", () => {
    expect(classifyMspVariant(" inav ")).toBe("inav");
    expect(classifyMspVariant("btfl")).toBe("betaflight");
  });

  it("returns null for an empty variant (API_VERSION, no family yet)", () => {
    // The key regression: empty must NOT become Betaflight — the caller keeps
    // waiting for the real FC_VARIANT reply.
    expect(classifyMspVariant("")).toBeNull();
    expect(classifyMspVariant("   ")).toBeNull();
  });

  it("classifies a definitive but unmodeled variant as unknown-MSP", () => {
    // A real FC_VARIANT for a family we do not model — driven over MSP but
    // never falsely claimed to be Betaflight.
    expect(classifyMspVariant("EMUF")).toBe("unknown");
    expect(classifyMspVariant("CLFL")).toBe("unknown");
  });
});
