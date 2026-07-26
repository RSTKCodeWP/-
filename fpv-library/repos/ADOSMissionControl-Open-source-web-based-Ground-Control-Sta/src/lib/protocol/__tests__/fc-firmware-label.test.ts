/**
 * @license GPL-3.0-only
 *
 * Unit tests for fcFirmwareLabel: the display-name mapper for the agent's FC
 * firmware identity. The key behavior is naming ArduPilot vs PX4 distinctly
 * (both are MAVLink), preferring fc_firmware and falling back to fc_variant.
 */

import { describe, it, expect } from "vitest";
import { fcFirmwareLabel } from "../fc-firmware-label";

describe("fcFirmwareLabel", () => {
  it("names the two MAVLink stacks distinctly", () => {
    expect(fcFirmwareLabel("ardupilot")).toBe("ArduPilot");
    expect(fcFirmwareLabel("px4")).toBe("PX4");
  });

  it("normalises vehicle-suffixed ArduPilot families to ArduPilot", () => {
    expect(fcFirmwareLabel("ardupilot-copter")).toBe("ArduPilot");
    expect(fcFirmwareLabel("ardupilot-plane")).toBe("ArduPilot");
    expect(fcFirmwareLabel("ardupilot-rover")).toBe("ArduPilot");
    expect(fcFirmwareLabel("ardupilot-sub")).toBe("ArduPilot");
  });

  it("names the MSP firmwares", () => {
    expect(fcFirmwareLabel("betaflight")).toBe("Betaflight");
    expect(fcFirmwareLabel("inav")).toBe("iNav");
  });

  it("is case- and whitespace-insensitive", () => {
    expect(fcFirmwareLabel("  ArduPilot ")).toBe("ArduPilot");
    expect(fcFirmwareLabel("PX4")).toBe("PX4");
  });

  it("falls back to fc_variant when fc_firmware is absent or unknown", () => {
    expect(fcFirmwareLabel(undefined, "betaflight")).toBe("Betaflight");
    expect(fcFirmwareLabel("unknown", "inav")).toBe("iNav");
    expect(fcFirmwareLabel(null, "inav")).toBe("iNav");
  });

  it("prefers fc_firmware over fc_variant", () => {
    // A defensive case: fc_firmware wins even if a stale variant disagrees.
    expect(fcFirmwareLabel("px4", "betaflight")).toBe("PX4");
  });

  it("returns undefined when no family is identified", () => {
    expect(fcFirmwareLabel(undefined)).toBeUndefined();
    expect(fcFirmwareLabel("unknown")).toBeUndefined();
    expect(fcFirmwareLabel("", "")).toBeUndefined();
    expect(fcFirmwareLabel("gizmo")).toBeUndefined();
  });
});
