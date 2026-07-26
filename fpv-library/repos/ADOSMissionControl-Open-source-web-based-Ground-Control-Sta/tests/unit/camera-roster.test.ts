/**
 * Verifies the camera-roster helpers: defensive coercion of the agent payload
 * and the leg-list builders the `PUT /api/video/cameras` write uses.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import type { RosterCamera } from "@/lib/agent/feature-types";
import {
  coerceRoster,
  isOperatorDeclared,
  legFromCamera,
  legsWithAdd,
  legsWithEdit,
  legsWithRemove,
  legsWithToggle,
  rosterToLegs,
  slugCameraId,
} from "@/lib/agent/camera-roster";

function cam(overrides: Partial<RosterCamera> & { id: string }): RosterCamera {
  return {
    name: null,
    source: "/dev/video0",
    role: null,
    purpose: [],
    orientation: null,
    enabled: true,
    owner: "operator",
    state: "assigned",
    live: null,
    device_path: null,
    width: null,
    height: null,
    fps: null,
    codec: null,
    match: null,
    fov_deg: null,
    mount_pitch_deg: null,
    ...overrides,
  };
}

describe("coerceRoster", () => {
  it("coerces rows and drops idless / non-object entries", () => {
    const rows = coerceRoster([
      {
        id: "eo",
        name: "Forward",
        source: "/dev/video0",
        role: "primary",
        purpose: ["feed", "detect"],
        orientation: "forward",
        enabled: true,
        owner: "operator",
        state: "assigned",
        live: true,
        width: 1920,
        height: 1080,
        match: { usb: "046d:0825" },
      },
      { name: "no id" },
      "garbage",
      null,
    ]);
    expect(rows).toHaveLength(1);
    expect(rows[0].id).toBe("eo");
    expect(rows[0].purpose).toEqual(["feed", "detect"]);
    expect(rows[0].live).toBe(true);
    expect(rows[0].match).toEqual({ usb: "046d:0825" });
    // absent optional → null, never fabricated
    expect(rows[0].fov_deg).toBeNull();
  });

  it("returns [] for a non-array and normalizes an unknown state", () => {
    expect(coerceRoster(undefined)).toEqual([]);
    expect(coerceRoster("nope")).toEqual([]);
    const [row] = coerceRoster([{ id: "x", state: "bogus" }]);
    expect(row.state).toBe("assigned");
  });

  it("drops an empty fingerprint to null", () => {
    const [row] = coerceRoster([{ id: "x", match: {} }]);
    expect(row.match).toBeNull();
  });
});

describe("leg building", () => {
  it("isOperatorDeclared excludes plugin + discovered rows", () => {
    expect(isOperatorDeclared(cam({ id: "a", state: "assigned" }))).toBe(true);
    expect(isOperatorDeclared(cam({ id: "a", state: "offline" }))).toBe(true);
    expect(
      isOperatorDeclared(cam({ id: "a", state: "plugin_owned" })),
    ).toBe(false);
    expect(
      isOperatorDeclared(cam({ id: "a", state: "discovered_unassigned" })),
    ).toBe(false);
  });

  it("legFromCamera omits null numeric/codec fields and applies a patch", () => {
    const leg = legFromCamera(
      cam({ id: "eo", codec: null, width: null, fps: null }),
      { name: "Renamed", purpose: ["detect"] },
    );
    expect(leg).not.toHaveProperty("codec");
    expect(leg).not.toHaveProperty("width");
    expect(leg).not.toHaveProperty("fps");
    expect(leg.name).toBe("Renamed");
    expect(leg.purpose).toEqual(["detect"]);
    // present values ride through
    const leg2 = legFromCamera(cam({ id: "b", codec: "h264", width: 1280 }));
    expect(leg2.codec).toBe("h264");
    expect(leg2.width).toBe(1280);
  });

  it("rosterToLegs keeps only operator-declared legs", () => {
    const roster = [
      cam({ id: "eo", state: "assigned" }),
      cam({ id: "gone", state: "offline" }),
      cam({ id: "ir", state: "plugin_owned", owner: "com.x.pod" }),
      cam({ id: "video4", state: "discovered_unassigned", owner: null }),
    ];
    expect(rosterToLegs(roster).map((l) => l.id)).toEqual(["eo", "gone"]);
  });

  it("legsWithEdit patches an assigned leg", () => {
    const roster = [cam({ id: "eo", state: "assigned", orientation: "forward" })];
    const legs = legsWithEdit(roster, "eo", { orientation: "down" });
    expect(legs).toHaveLength(1);
    expect(legs[0].orientation).toBe("down");
  });

  it("legsWithEdit promotes a discovered device to a new enabled leg", () => {
    const roster = [
      cam({ id: "eo", state: "assigned", role: "primary" }),
      cam({
        id: "video4",
        state: "discovered_unassigned",
        source: "/dev/video4",
        enabled: false,
        owner: null,
      }),
    ];
    const legs = legsWithEdit(roster, "video4", { purpose: ["detect"] });
    expect(legs.map((l) => l.id)).toEqual(["eo", "video4"]);
    const added = legs.find((l) => l.id === "video4")!;
    expect(added.enabled).toBe(true);
    expect(added.purpose).toEqual(["detect"]);
  });

  it("designating a primary demotes any other primary", () => {
    const roster = [
      cam({ id: "eo", state: "assigned", role: "primary" }),
      cam({ id: "wide", state: "assigned", role: null }),
    ];
    const legs = legsWithEdit(roster, "wide", { role: "primary" });
    expect(legs.find((l) => l.id === "wide")!.role).toBe("primary");
    expect(legs.find((l) => l.id === "eo")!.role).toBeNull();
  });

  it("legsWithToggle flips enabled, legsWithRemove drops, legsWithAdd appends", () => {
    const roster = [cam({ id: "eo", state: "assigned", enabled: true })];
    expect(legsWithToggle(roster, "eo", false)[0].enabled).toBe(false);
    expect(legsWithRemove(roster, "eo")).toEqual([]);
    const added = legsWithAdd(roster, {
      id: "dome",
      source: "rtsp://x/y",
      enabled: true,
    });
    expect(added.map((l) => l.id)).toEqual(["eo", "dome"]);
  });
});

describe("slugCameraId", () => {
  it("slugs a name and disambiguates against taken ids", () => {
    expect(slugCameraId("Belly Cam", [])).toBe("belly-cam");
    expect(slugCameraId("Belly Cam!!", ["belly-cam"])).toBe("belly-cam-2");
    expect(slugCameraId("", [])).toBe("ip-cam");
  });
});
