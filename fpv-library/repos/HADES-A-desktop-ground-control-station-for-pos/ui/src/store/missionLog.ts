import { create } from "zustand";

/* Append-only mission log (impl-plan Task 5.8; design "memory layer"). The audit trail:
 * every detection, clearance change, dispatch snapshot, operator note, and link event is
 * appended with a timestamp and a monotonic id. Append-only — entries are never mutated or
 * removed, only added (and capped to keep a long mission bounded, dropping the OLDEST).
 * Timestamps are passed in (no Date.now in the store, so it stays deterministic + testable;
 * callers stamp with the frame/clock). Export/handoff is v1.x. */

export type LogKind = "detection" | "clearance" | "snapshot" | "note" | "link";

export interface LogEntryInput {
  kind: LogKind;
  text: string;
  t: number; // timestamp (ms or mission-seconds; caller's choice, consistent per session)
}

export interface LogEntry extends LogEntryInput {
  id: number;
}

const LOG_CAP = 5000;

interface MissionLogState {
  entries: LogEntry[];
  append: (e: LogEntryInput) => void;
  reset: () => void;
}

let nextId = 1;

export const useMissionLog = create<MissionLogState>((set, get) => ({
  entries: [],
  append: (e) => {
    const entries = [...get().entries, { ...e, id: nextId++ }];
    if (entries.length > LOG_CAP) entries.splice(0, entries.length - LOG_CAP);
    set({ entries });
  },
  reset: () => set({ entries: [] }),
}));
