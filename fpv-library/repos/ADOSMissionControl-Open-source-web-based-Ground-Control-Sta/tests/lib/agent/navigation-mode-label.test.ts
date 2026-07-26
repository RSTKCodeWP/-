import { describe, expect, it } from "vitest";

import {
  NAVIGATION_MODE_BADGES,
  navigationModeBadge,
} from "@/lib/agent/navigation-mode-label";

describe("navigationModeBadge", () => {
  it("returns null when the mode is missing", () => {
    expect(navigationModeBadge(undefined)).toBeNull();
    expect(navigationModeBadge("")).toBeNull();
  });

  it("returns null for the off mode", () => {
    // The off mode means the plugin is loaded but disabled; no pill.
    expect(navigationModeBadge("off")).toBeNull();
  });

  it("returns null for an unknown mode key", () => {
    // Forward compatibility: a future agent ships a mode the GCS does
    // not know about. Render nothing rather than a misleading badge.
    expect(navigationModeBadge("future_mode_xyz")).toBeNull();
  });

  it("returns OF with the success tone for plain optical_flow", () => {
    const badge = navigationModeBadge("optical_flow");
    expect(badge).not.toBeNull();
    expect(badge?.short).toBe("OF");
    expect(badge?.tone).toBe("ok");
  });

  it("returns OF* with the warning tone for the degraded path", () => {
    const badge = navigationModeBadge("optical_flow_degraded");
    expect(badge).not.toBeNull();
    expect(badge?.short).toBe("OF*");
    expect(badge?.tone).toBe("warn");
    // The tooltip explains the degradation explicitly.
    expect(badge?.tooltip.toLowerCase()).toMatch(/scale|baro|gps/);
  });

  it("returns VIO with the success tone for both VIO engines", () => {
    expect(navigationModeBadge("vio_openvins")?.short).toBe("VIO");
    expect(navigationModeBadge("vio_openvins")?.tone).toBe("ok");
    expect(navigationModeBadge("vio_vins_fusion")?.short).toBe("VIO");
    expect(navigationModeBadge("vio_vins_fusion")?.tone).toBe("ok");
  });

  it("returns Hybrid for the combined estimator mode", () => {
    const badge = navigationModeBadge("hybrid_of_plus_vio");
    expect(badge?.short).toBe("Hybrid");
    expect(badge?.tone).toBe("ok");
  });

  it("covers every known mode in the export map", () => {
    // Catches the regression where a new mode is added to the type
    // but no badge entry is provided.
    const keys = Object.keys(NAVIGATION_MODE_BADGES);
    expect(keys).toEqual(
      expect.arrayContaining([
        "off",
        "optical_flow",
        "optical_flow_degraded",
        "vio_openvins",
        "vio_vins_fusion",
        "hybrid_of_plus_vio",
      ]),
    );
  });
});
