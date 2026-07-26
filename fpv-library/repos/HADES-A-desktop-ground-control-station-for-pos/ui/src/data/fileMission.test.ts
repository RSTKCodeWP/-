import { readFileSync } from "node:fs";
import path from "node:path";

import { beforeEach, describe, expect, it } from "vitest";

import { videoFrameSink } from "../components/VideoPanel";
import { useContactStore } from "../store/contacts";
import { useMissionLog } from "../store/missionLog";
import { useProvenanceStore } from "../store/provenance";
import { useSystemStore } from "../store/system";
import { commandSink } from "../ws/commandSink";
import { wireMission } from "./fileMission";
import { parseMission, type BakedMission } from "./mission";

/* Phase 6 Task 6.2 — the file-mission source reuses the mock transport (`MockWsServer`) but
 * adds the baked timeline (LINK-LOST window, refined-promote swap) + provenance. `wireMission`
 * is the pure wiring the `useFileMission` hook calls; we drive it with the REAL baked artifact
 * and assert the demo's end-state. intervalMs=0 = replay as fast as possible (deterministic). */

function loadBaked(): BakedMission {
  const p = path.resolve(__dirname, "../../public/mission.json");
  return parseMission(JSON.parse(readFileSync(p, "utf-8")));
}

beforeEach(() => {
  useContactStore.setState({ contacts: new Map(), latestDetection: null });
  useSystemStore.getState().reset();
  useMissionLog.getState().reset();
  useProvenanceStore.getState().setProvenance(null);
  commandSink.setHandler(null);
});

describe("wireMission (file-mission source over the mock transport)", () => {
  it("replays the baked stream into the stores and sets provenance", async () => {
    const mission = loadBaked();
    const drawnFrameIds: number[] = [];
    const probe = (f: { frame_id: number }) => drawnFrameIds.push(f.frame_id);
    videoFrameSink.subscribe(probe);

    const stop = await wireMission(mission, { intervalMs: 0 });

    const contacts = useContactStore.getState().contacts;
    expect(contacts.size).toBeGreaterThan(0);
    // a real located pin AND the honest null-coord CUE_ONLY both survive the replay
    const located = [...contacts.values()].filter((c) => c.lat !== null);
    const cue = [...contacts.values()].filter((c) => c.actionability_class === "CUE_ONLY");
    expect(located.length).toBeGreaterThan(0);
    expect(cue.length).toBeGreaterThan(0);
    expect(cue.every((c) => c.lat === null)).toBe(true);

    // provenance populated for the banner
    expect(useProvenanceStore.getState().provenance?.pipeline).toBe("real");

    // the cross-channel join held: at least one painted frame coincided with a detection so a
    // box actually drew (the silent-no-boxes guard, on the real frame_id not a local counter)
    const detIds = new Set(
      mission.json.filter((m) => m.type === "detection" && m.boxes.length > 0).map((m) => m.frame_id),
    );
    expect(drawnFrameIds.some((id) => detIds.has(id))).toBe(true);

    videoFrameSink.unsubscribe(probe);
    stop();
  });

  it("drives LINK-LOST from the baked timeline window, then recovers", async () => {
    const mission = loadBaked();
    // sample link state at each frame boundary by replaying frame-by-frame is brittle; instead
    // assert the observable record: a LINK LOST entry is appended (degrade-visibly), and the link
    // is back up by the end (recovered). The window is [fromFrame, toFrame).
    const stop = await wireMission(mission, { intervalMs: 0 });
    const loggedLinkLost = useMissionLog
      .getState()
      .entries.some((e) => e.kind === "link" && e.text.includes("LINK LOST"));
    expect(loggedLinkLost).toBe(true); // link dropped during the window (logged)
    expect(useSystemStore.getState().linkUp).toBe(true); // and recovered by the end
    stop();
  });

  it("promote swaps in the baked refined record (the honest on-demand fusion replay)", async () => {
    const mission = loadBaked();
    const stop = await wireMission(mission, { intervalMs: 0 });
    const refined = mission.promoteRefined!;
    const before = useContactStore.getState().contacts.get(refined.track_id);
    expect(before).toBeDefined();

    commandSink.promote(refined.track_id);

    const after = useContactStore.getState().contacts.get(refined.track_id)!;
    expect(after.r95_m).toBe(refined.r95_m); // the contact tightened to the refined estimate
    expect(after.lat).toBe(refined.lat);
    stop();
  });
});
