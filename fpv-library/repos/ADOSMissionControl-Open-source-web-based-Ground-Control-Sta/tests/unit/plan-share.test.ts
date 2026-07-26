/**
 * Client-only share links: a plan round-trips losslessly through encode→decode, and
 * any malformed / tampered / oversized fragment decodes to null (never a partial plan).
 * @license GPL-3.0-only
 */
import { describe, it, expect } from "vitest";
import {
  buildMissionFile,
  encodePlan,
  decodePlan,
  makeShareLink,
  buildShareUrl,
  readPlanFromHash,
  SHARE_MAX_ENCODED_LEN,
} from "@/lib/plan-share";
import type { Waypoint } from "@/lib/types";
import type { MissionMetadata } from "@/lib/mission-io";

const META: MissionMetadata = { name: "Test Mission", createdAt: 1000, updatedAt: 2000 };
const WPS: Waypoint[] = [
  { id: "a", lat: 12.5, lon: 77.5, alt: 50, command: "WAYPOINT" },
  { id: "b", lat: 12.51, lon: 77.51, alt: 60, command: "WAYPOINT" },
];

describe("plan-share round-trip", () => {
  it("encodes and decodes a plan losslessly", () => {
    const file = buildMissionFile(WPS, META);
    const decoded = decodePlan(encodePlan(file));
    expect(decoded).not.toBeNull();
    expect(decoded!.waypoints).toHaveLength(2);
    expect(decoded!.waypoints[0].lat).toBeCloseTo(12.5);
    expect(decoded!.metadata.name).toBe("Test Mission");
    expect(decoded!.version).toBe(1);
  });

  it("carries geofence + rally extras when present", () => {
    const file = buildMissionFile(WPS, META, {
      geofence: { enabled: true, fenceType: "circle", circleCenter: [12.5, 77.5], circleRadius: 100 },
      rally: [{ id: "r1", lat: 12.5, lon: 77.5, alt: 40 }],
    } as never);
    const decoded = decodePlan(encodePlan(file));
    expect(decoded!.geofence).toBeDefined();
    expect(decoded!.rally).toHaveLength(1);
  });

  it("reads a plan from a URL hash string", () => {
    const encoded = encodePlan(buildMissionFile(WPS, META));
    expect(readPlanFromHash(`#plan=${encoded}`)).not.toBeNull();
    expect(readPlanFromHash(`plan=${encoded}`)).not.toBeNull();
  });

  it("builds a share URL", () => {
    expect(buildShareUrl("https://x.test", "/plan", "ABC")).toBe("https://x.test/plan#plan=ABC");
  });
});

describe("plan-share defensive decode", () => {
  it("rejects an empty / non-base64 / non-deflate fragment", () => {
    expect(decodePlan("")).toBeNull();
    expect(decodePlan("!!!not base64!!!")).toBeNull();
    expect(decodePlan("aGVsbG8")).toBeNull(); // valid base64 ("hello") but not deflate
  });

  it("rejects a fragment whose JSON is not a valid mission shape", () => {
    // Encode arbitrary (non-mission) JSON and confirm it does not decode to a plan.
    const badFile = { version: 2, waypoints: "nope" } as never;
    expect(decodePlan(encodePlan(badFile))).toBeNull();
  });

  it("reports oversized plans via makeShareLink instead of a bad link", () => {
    const many: Waypoint[] = Array.from({ length: 4000 }, (_, i) => ({
      id: `w${i}`, lat: 12.5 + i * 1e-5, lon: 77.5, alt: 50, command: "WAYPOINT",
    }));
    const res = makeShareLink(buildMissionFile(many, META));
    expect(res.tooLarge).toBe(true);
    expect(res.encoded).toBeNull();
    expect(res.length).toBeGreaterThan(SHARE_MAX_ENCODED_LEN);
  });
});
