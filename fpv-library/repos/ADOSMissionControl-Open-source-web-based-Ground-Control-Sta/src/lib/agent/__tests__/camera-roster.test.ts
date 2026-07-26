/**
 * @license GPL-3.0-only
 *
 * Unit tests for the camera-roster coercion + leg builders that turn the
 * agent's `GET /api/video/roster` payload into the `PUT /api/video/roster`
 * write body.
 */

import { describe, it, expect } from "vitest";

import {
  coerceRoster,
  legFromCamera,
  legsWithEdit,
  slugCameraId,
} from "../camera-roster";
import type { RosterCamera } from "../feature-types";

describe("camera-roster · bitrate/calibration round-trip", () => {
  it("coerces bitrate_kbps + calibration off the roster payload", () => {
    const roster = coerceRoster([
      {
        id: "eo",
        source: "/dev/video0",
        bitrate_kbps: 6000,
        calibration: "pinhole:fx=1024",
      },
    ]);
    expect(roster).toHaveLength(1);
    expect(roster[0].bitrate_kbps).toBe(6000);
    expect(roster[0].calibration).toBe("pinhole:fx=1024");
  });

  it("writes bitrate_kbps + calibration back onto the leg (lossless)", () => {
    const cam: RosterCamera = {
      id: "eo",
      name: "Forward EO",
      source: "/dev/video0",
      role: "primary",
      purpose: ["feed"],
      orientation: "forward",
      enabled: true,
      owner: "operator",
      state: "assigned",
      live: true,
      bitrate_kbps: 6000,
      calibration: "pinhole:fx=1024",
    };
    const leg = legFromCamera(cam);
    expect(leg.bitrate_kbps).toBe(6000);
    expect(leg.calibration).toBe("pinhole:fx=1024");
  });

  it("preserves the bitrate through a full read → edit → write cycle", () => {
    const roster = coerceRoster([
      {
        id: "eo",
        source: "/dev/video0",
        role: "primary",
        enabled: true,
        state: "assigned",
        bitrate_kbps: 6000,
        calibration: "cal-blob",
      },
    ]);
    // An unrelated edit (renaming the camera) must not drop the bitrate.
    const legs = legsWithEdit(roster, "eo", { name: "Nose cam" });
    const eo = legs.find((l) => l.id === "eo");
    expect(eo?.name).toBe("Nose cam");
    expect(eo?.bitrate_kbps).toBe(6000);
    expect(eo?.calibration).toBe("cal-blob");
  });

  it("omits bitrate/calibration from the leg when the roster has none", () => {
    const roster = coerceRoster([{ id: "usb", source: "/dev/video1" }]);
    const leg = legFromCamera(roster[0]);
    expect(leg.bitrate_kbps).toBeUndefined();
    expect(leg.calibration).toBeUndefined();
  });
});

describe("camera-roster · primary switch never leaves a non-primary main", () => {
  const roster = coerceRoster([
    {
      id: "main",
      name: "Onboard",
      source: "/dev/video0",
      role: "primary",
      enabled: true,
      state: "assigned",
    },
    {
      id: "ip-cam",
      name: "Gate cam",
      source: "rtsp://10.0.0.9/stream",
      role: null,
      enabled: true,
      state: "assigned",
    },
  ]);

  it("re-slugs the demoted main leg so no non-primary 'main' survives", () => {
    const legs = legsWithEdit(roster, "ip-cam", { role: "primary" });
    const primaries = legs.filter((l) => l.role === "primary");
    expect(primaries).toHaveLength(1);
    expect(primaries[0].id).toBe("ip-cam");
    // The old primary lost the reserved id (it is no longer primary).
    const badMain = legs.find((l) => l.id === "main" && l.role !== "primary");
    expect(badMain).toBeUndefined();
    // Its device is preserved under a fresh id.
    const demoted = legs.find((l) => l.source === "/dev/video0");
    expect(demoted).toBeDefined();
    expect(demoted?.id).not.toBe("main");
  });
});

describe("camera-roster · slugCameraId reserves the primary id", () => {
  it("never mints the reserved 'main' id for a camera named 'Main'", () => {
    const id = slugCameraId("Main", []);
    expect(id).not.toBe("main");
    expect(id.startsWith("main")).toBe(true);
  });

  it("still disambiguates against taken ids", () => {
    expect(slugCameraId("Belly cam", ["belly-cam"])).toBe("belly-cam-2");
  });
});
