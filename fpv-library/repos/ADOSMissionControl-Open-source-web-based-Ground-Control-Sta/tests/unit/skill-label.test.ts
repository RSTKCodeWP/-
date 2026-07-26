import { describe, it, expect } from "vitest";
import { resolveContribLabel } from "@/lib/skills/skill-label";

describe("resolveContribLabel", () => {
  it("humanizes a dotted lowercase i18n key (the raw-key leak the pop-up showed)", () => {
    expect(resolveContribLabel("skill.track")).toBe("Track");
    expect(resolveContribLabel("skill.record")).toBe("Record");
    expect(resolveContribLabel("camera.zoom_in")).toBe("Zoom In");
    expect(resolveContribLabel("siyi.fire_lrf")).toBe("Fire Lrf");
  });

  it("humanizes a bare lowercase token/id", () => {
    expect(resolveContribLabel("follow-me")).toBe("Follow Me");
    expect(resolveContribLabel("nadir")).toBe("Nadir");
  });

  it("passes through a human display string untouched", () => {
    expect(resolveContribLabel("Follow Me")).toBe("Follow Me");
    expect(resolveContribLabel("SIYI Pod")).toBe("SIYI Pod");
    expect(resolveContribLabel("Point at target")).toBe("Point at target");
  });

  it("handles empty and whitespace input", () => {
    expect(resolveContribLabel("")).toBe("");
    expect(resolveContribLabel("  Track  ")).toBe("Track");
  });
});
