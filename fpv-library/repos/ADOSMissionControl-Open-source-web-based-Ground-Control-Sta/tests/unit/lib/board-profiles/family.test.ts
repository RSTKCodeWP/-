import { describe, it, expect } from "vitest";
import {
  detectChipFamily,
  chipFamilyRequiresReboot,
} from "@/lib/board-profiles/family";

describe("detectChipFamily", () => {
  it("resolves F4 from MatekF405-SE (board id 1022)", () => {
    expect(detectChipFamily(1022)).toBe("F4");
  });

  it("resolves H7 from MatekH743 (board id 1013)", () => {
    expect(detectChipFamily(1013)).toBe("H7");
  });

  it("resolves F4 from SpeedyBee F405 V3 (board id 1031)", () => {
    expect(detectChipFamily(1031)).toBe("F4");
  });

  it("resolves F7 from SpeedyBee F7 V3 (board id 1045)", () => {
    expect(detectChipFamily(1045)).toBe("F7");
  });

  it("resolves F4 from Pixhawk1 reference (board id 5)", () => {
    expect(detectChipFamily(5)).toBe("F4");
  });

  it("resolves F7 from Pixhawk 4 / FMUv5 (board id 50)", () => {
    expect(detectChipFamily(50)).toBe("F7");
  });

  it("resolves H7 from Pixhawk 6X (board id 54)", () => {
    expect(detectChipFamily(54)).toBe("H7");
  });

  it("falls back to F4 when the board ID is unknown", () => {
    expect(detectChipFamily(987654)).toBe("F4");
  });
});

describe("chipFamilyRequiresReboot", () => {
  it("returns true for F4", () => {
    expect(chipFamilyRequiresReboot("F4")).toBe(true);
  });

  it("returns true for unknown (conservative default)", () => {
    expect(chipFamilyRequiresReboot("unknown")).toBe(true);
  });

  it("returns false for F7", () => {
    expect(chipFamilyRequiresReboot("F7")).toBe(false);
  });

  it("returns false for H7", () => {
    expect(chipFamilyRequiresReboot("H7")).toBe(false);
  });

  it("returns false for G4", () => {
    expect(chipFamilyRequiresReboot("G4")).toBe(false);
  });
});
