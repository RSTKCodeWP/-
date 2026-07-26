/**
 * @module dronecan/flash-store
 * @description Zustand store for the DroneCAN firmware-update (OTA) UI.
 *
 * Receives snapshots from the OTA orchestrator and exposes a flat shape the
 * Flash panel can render. The orchestrator owns the state machine; this
 * store is a passive mirror with a small transition log for the debug view.
 *
 * @license GPL-3.0-only
 */

import { create } from "zustand";
import type { OtaSnapshot, OtaState } from "@/lib/dronecan/ota";

export type { OtaSnapshot, OtaState };

export interface OtaTransition {
  t: number;
  from: OtaState;
  to: OtaState;
  note?: string;
}

const TRANSITION_LOG_CAP = 128;

interface FlashStoreState {
  state: OtaState;
  percent: number;
  bytesSent: number;
  bytesTotal: number;
  lastOffset: number;
  lastChunkLen: number;
  retries: number;
  timeouts: number;
  transitionLog: OtaTransition[];
  errorMessage?: string;
  _version: number;

  setSnapshot: (snapshot: OtaSnapshot) => void;
  reset: () => void;
}

const INITIAL: Omit<FlashStoreState, "setSnapshot" | "reset" | "_version"> = {
  state: "IDLE",
  percent: 0,
  bytesSent: 0,
  bytesTotal: 0,
  lastOffset: 0,
  lastChunkLen: 0,
  retries: 0,
  timeouts: 0,
  transitionLog: [],
  errorMessage: undefined,
};

export const useDroneCanFlashStore = create<FlashStoreState>((set, get) => ({
  ...INITIAL,
  _version: 0,

  setSnapshot: (snapshot) => {
    const prev = get();
    let transitionLog = prev.transitionLog;
    if (snapshot.state !== prev.state) {
      const next: OtaTransition = {
        t: Date.now(),
        from: prev.state,
        to: snapshot.state,
        note: snapshot.errorMessage,
      };
      transitionLog = prev.transitionLog.concat(next);
      if (transitionLog.length > TRANSITION_LOG_CAP) {
        transitionLog = transitionLog.slice(
          transitionLog.length - TRANSITION_LOG_CAP,
        );
      }
    }
    set({
      state: snapshot.state,
      percent: snapshot.percent,
      bytesSent: snapshot.bytesSent,
      bytesTotal: snapshot.bytesTotal,
      lastOffset: snapshot.lastOffset,
      lastChunkLen: snapshot.lastChunkLen,
      retries: snapshot.retries,
      timeouts: snapshot.timeouts,
      errorMessage: snapshot.errorMessage,
      transitionLog,
      _version: prev._version + 1,
    });
  },

  reset: () => {
    set({ ...INITIAL, _version: get()._version + 1 });
  },
}));
