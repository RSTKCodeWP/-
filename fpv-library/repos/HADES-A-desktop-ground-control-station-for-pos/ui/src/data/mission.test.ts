import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import type { ContactRecord } from "../types/wire";
import { parseMission, type BakedMission } from "./mission";

/* Phase 6 Task 6.2 — the browser file-mission source must consume the REAL baked artifact.
 * We load the actual `ui/public/mission.json` produced by `hades-record-mission` (not a
 * hand-written fixture) so this test catches Python↔TS schema drift: a field the Python
 * bake emits that `wire.ts` mis-models would pass the service-side round-trip yet break here. */

function loadBaked(): BakedMission {
  const p = path.resolve(__dirname, "../../public/mission.json");
  return parseMission(JSON.parse(readFileSync(p, "utf-8")));
}

describe("parseMission (the real baked artifact)", () => {
  it("decodes frames to byte-tagged MockFrames carrying the REAL frame_id", () => {
    const { frames } = loadBaked();
    expect(frames.length).toBeGreaterThan(0);
    // contiguous real pipeline seq from 0 (NOT a re-counted local index)
    expect(frames.map((f) => f.frame_id)).toEqual(frames.map((_, i) => i));
    for (const f of frames) {
      expect(f.jpeg).toBeInstanceOf(Uint8Array);
      expect(f.jpeg.length).toBeGreaterThan(0);
      // JPEG SOI marker — confirms base64 decoded to real image bytes
      expect(f.jpeg[0]).toBe(0xff);
      expect(f.jpeg[1]).toBe(0xd8);
    }
  });

  it("parses the JSON stream into wire types incl an honest null-coord CUE_ONLY", () => {
    const { json } = loadBaked();
    const contacts = json.filter((m): m is ContactRecord => m.type === "contact");
    expect(contacts.length).toBeGreaterThan(0);

    const located = contacts.filter((c) => c.lat !== null && c.lon !== null);
    expect(located.length).toBeGreaterThan(0); // the demo map has REAL pins
    for (const c of located) {
      expect(Number.isFinite(c.lat as number)).toBe(true);
      expect(Number.isFinite(c.r95_m)).toBe(true);
    }

    const cue = contacts.filter((c) => c.actionability_class === "CUE_ONLY");
    expect(cue.length).toBeGreaterThan(0);
    for (const c of cue) {
      expect(c.lat).toBeNull(); // null STAYS null — never a Null-Island 0,0 pin
      expect(c.lon).toBeNull();
    }
  });

  it("every JSON frame_id has a matching frame, and a detection coincides with one (a box draws)", () => {
    const { frames, json } = loadBaked();
    const frameIds = new Set(frames.map((f) => f.frame_id));
    for (const m of json) expect(frameIds.has(m.frame_id)).toBe(true);
    const detIds = json.filter((m) => m.type === "detection" && m.boxes.length > 0).map((m) => m.frame_id);
    expect(detIds.some((id) => frameIds.has(id))).toBe(true);
  });

  it("surfaces provenance + scripted demo timeline (link-lost, refined promote)", () => {
    const m = loadBaked();
    expect(m.provenance.scene).toBe("synthetic");
    expect(m.provenance.pipeline).toBe("real");
    expect(Number.isFinite(m.provenance.median_error_m)).toBe(true);
    expect(m.linkLost.fromFrame).toBeLessThan(m.linkLost.toFrame);
    expect(m.promoteRefined?.lat).not.toBeNull();
    expect(typeof m.missionEpochMs).toBe("number");
  });
});
