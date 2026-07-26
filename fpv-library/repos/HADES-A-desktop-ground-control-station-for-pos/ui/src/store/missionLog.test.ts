import { beforeEach, describe, expect, it } from "vitest";

import { useMissionLog } from "./missionLog";

/* Append-only mission log (impl-plan Task 5.8; design "memory layer"). Every meaningful
 * event — detection, clearance change, dispatch snapshot, operator note, link event — is
 * appended with a timestamp. Append-only: entries are never mutated or removed (the audit
 * trail), only added. Timestamps are injected (testable, no Date.now in the store). */

describe("mission log", () => {
  beforeEach(() => useMissionLog.getState().reset());

  it("starts empty", () => {
    expect(useMissionLog.getState().entries).toHaveLength(0);
  });

  it("appends a typed, timestamped entry", () => {
    useMissionLog.getState().append({ kind: "detection", text: "trk 42 NEW PINPOINT", t: 1000 });
    const e = useMissionLog.getState().entries[0];
    expect(e.kind).toBe("detection");
    expect(e.text).toBe("trk 42 NEW PINPOINT");
    expect(e.t).toBe(1000);
  });

  it("is append-only and chronological (newest last)", () => {
    const log = useMissionLog.getState();
    log.append({ kind: "detection", text: "a", t: 1 });
    log.append({ kind: "clearance", text: "b", t: 2 });
    log.append({ kind: "link", text: "c", t: 3 });
    expect(useMissionLog.getState().entries.map((e) => e.text)).toEqual(["a", "b", "c"]);
  });

  it("assigns a stable monotonic id to each entry (for keys / ordering)", () => {
    const log = useMissionLog.getState();
    log.append({ kind: "note", text: "x", t: 1 });
    log.append({ kind: "note", text: "y", t: 2 });
    const [a, b] = useMissionLog.getState().entries;
    expect(b.id).toBeGreaterThan(a.id);
  });

  it("caps the log so a long mission stays bounded, keeping the most recent", () => {
    const log = useMissionLog.getState();
    for (let i = 0; i < 6000; i++) log.append({ kind: "detection", text: `e${i}`, t: i });
    const entries = useMissionLog.getState().entries;
    expect(entries.length).toBeLessThanOrEqual(5000);
    expect(entries[entries.length - 1].text).toBe("e5999"); // newest retained
  });
});
