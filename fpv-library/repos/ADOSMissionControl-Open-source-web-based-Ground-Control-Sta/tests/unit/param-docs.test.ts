import { describe, it, expect } from "vitest";
import {
  vehicleToDocsSlug,
  vehicleToDocsTitle,
  parseFirmwareVersionTag,
  paramNameToDocFragment,
  getParamDocUrl,
  getParamDocUrlFromContext,
  resolveParamDocContext,
} from "@/lib/protocol/param-docs";
import { formatParamDisplayValue } from "@/lib/protocol/param-display";
import type { ParamMetadata } from "@/lib/protocol/param-metadata";

describe("vehicleToDocsSlug / vehicleToDocsTitle", () => {
  it("maps all ArduPilot vehicles", () => {
    expect(vehicleToDocsSlug("ArduCopter")).toBe("copter");
    expect(vehicleToDocsSlug("ArduPlane")).toBe("plane");
    expect(vehicleToDocsSlug("Rover")).toBe("rover");
    expect(vehicleToDocsSlug("ArduSub")).toBe("sub");
    expect(vehicleToDocsTitle("ArduCopter")).toBe("Copter");
    expect(vehicleToDocsTitle("ArduPlane")).toBe("Plane");
  });
});

describe("parseFirmwareVersionTag", () => {
  it("parses V-prefixed semver", () => {
    expect(parseFirmwareVersionTag("ArduCopter V4.6.3")).toBe("V4.6.3");
  });

  it("parses plain semver", () => {
    expect(parseFirmwareVersionTag("APM:Copter 4.5.7")).toBe("V4.5.7");
  });

  it("returns null when unparseable (caller uses parameters.html)", () => {
    expect(parseFirmwareVersionTag("")).toBeNull();
    expect(parseFirmwareVersionTag(null)).toBeNull();
    expect(parseFirmwareVersionTag("custom-build-xyz")).toBeNull();
  });
});

describe("paramNameToDocFragment", () => {
  it("lowercases and hyphenates underscores", () => {
    expect(paramNameToDocFragment("AHRS_GPS_MINSATS")).toBe("ahrs-gps-minsats");
    expect(paramNameToDocFragment("ARMING_CHECK")).toBe("arming-check");
  });
});

describe("getParamDocUrl", () => {
  it("builds versioned URL with hyphenated fragment", () => {
    const url = getParamDocUrl("AHRS_GPS_MINSATS", "ArduCopter", "V4.5.7");
    expect(url).toBe(
      "https://ardupilot.org/copter/docs/parameters-Copter-stable-V4.5.7.html#ahrs-gps-minsats",
    );
  });

  it("uses unversioned parameters.html when version unknown", () => {
    const url = getParamDocUrl("FLTMODE1", "ArduPlane", null);
    expect(url).toBe("https://ardupilot.org/plane/docs/parameters.html#fltmode1");
  });

  it("never emits parameters-*-stable-latest.html", () => {
    const url = getParamDocUrl("ARMING_CHECK", "ArduCopter", "latest");
    expect(url).not.toContain("stable-latest");
    expect(url).toContain("/parameters.html#arming-check");
  });

  it("returns null without context", () => {
    expect(getParamDocUrlFromContext("ARMING_CHECK", null)).toBeNull();
  });
});

describe("resolveParamDocContext", () => {
  it("resolves ardupilot-copter directly", () => {
    const ctx = resolveParamDocContext("ardupilot-copter", "ArduCopter V4.6.3", "copter");
    expect(ctx?.vehicle).toBe("ArduCopter");
    expect(ctx?.versionTag).toBe("V4.6.3");
  });

  it("returns null for px4 even with copter class", () => {
    expect(resolveParamDocContext("px4", "PX4 v1.15.0", "copter")).toBeNull();
  });

  it("falls back to vehicleClass when firmwareType is unknown", () => {
    const ctx = resolveParamDocContext("unknown", "ArduCopter V4.5.7", "copter");
    expect(ctx?.vehicle).toBe("ArduCopter");
    expect(ctx?.versionTag).toBe("V4.5.7");
  });
});

describe("formatParamDisplayValue", () => {
  const meta: ParamMetadata = {
    name: "FLTMODE1",
    humanName: "Flight Mode 1",
    description: "",
    values: new Map([
      [0, "Stabilize"],
      [5, "Loiter"],
    ]),
  };

  it("shows enum label when known", () => {
    expect(formatParamDisplayValue(5, meta)).toBe("5 \u2014 Loiter");
  });

  it("falls back to number when unknown", () => {
    expect(formatParamDisplayValue(99, meta)).toBe("99");
  });

  it("returns number without meta", () => {
    expect(formatParamDisplayValue(1.5)).toBe("1.5");
  });
});
