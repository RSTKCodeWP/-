/**
 * @module protocol/select-fc-adapter.test
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { createFcAdapter, isMspVariant } from "../select-fc-adapter";
import { MSPAdapter } from "../msp-adapter";
import { MAVLinkAdapter } from "../mavlink-adapter";

describe("isMspVariant", () => {
  it("is true for Betaflight/iNav (case- and whitespace-insensitive)", () => {
    expect(isMspVariant("betaflight")).toBe(true);
    expect(isMspVariant("inav")).toBe(true);
    expect(isMspVariant("INAV")).toBe(true);
    expect(isMspVariant(" Betaflight ")).toBe(true);
  });

  it("is false for ArduPilot / PX4 / unknown / absent", () => {
    expect(isMspVariant("ardupilot-copter")).toBe(false);
    expect(isMspVariant("px4")).toBe(false);
    expect(isMspVariant("")).toBe(false);
    expect(isMspVariant(undefined)).toBe(false);
    expect(isMspVariant(null)).toBe(false);
  });
});

describe("createFcAdapter", () => {
  it("selects the MSP adapter for a Betaflight FC", async () => {
    expect(await createFcAdapter("betaflight")).toBeInstanceOf(MSPAdapter);
  });

  it("selects the MSP adapter for an iNav FC", async () => {
    expect(await createFcAdapter("inav")).toBeInstanceOf(MSPAdapter);
  });

  it("is case- and whitespace-insensitive", async () => {
    expect(await createFcAdapter("INAV")).toBeInstanceOf(MSPAdapter);
    expect(await createFcAdapter(" Betaflight ")).toBeInstanceOf(MSPAdapter);
  });

  it("defaults to the MAVLink adapter when the variant is absent", async () => {
    expect(await createFcAdapter(undefined)).toBeInstanceOf(MAVLinkAdapter);
    expect(await createFcAdapter(null)).toBeInstanceOf(MAVLinkAdapter);
  });

  it("selects the MAVLink adapter for ArduPilot / PX4 / unknown FCs", async () => {
    expect(await createFcAdapter("ardupilot-copter")).toBeInstanceOf(
      MAVLinkAdapter,
    );
    expect(await createFcAdapter("px4")).toBeInstanceOf(MAVLinkAdapter);
    expect(await createFcAdapter("")).toBeInstanceOf(MAVLinkAdapter);
  });
});
