/**
 * SLCAN mode state machine.
 *
 * Tracks the lifecycle of a single SLCAN session for the connected drone:
 *
 *   IDLE → ENTERING_SLCAN → SLCAN_ACTIVE → EXITING_SLCAN → RECONNECTING_MAVLINK → IDLE
 *
 * The flash arbiter drives the transitions; UI components subscribe via
 * selectors. A 1 Hz ticker advances `tickMs` while SLCAN_ACTIVE so the
 * banner countdown re-renders without forcing the arbiter to push state.
 *
 * @module stores/slcan-mode-store
 * @license GPL-3.0-only
 */

import { create } from "zustand";

export type SlcanModeState =
  | "IDLE"
  | "ENTERING_SLCAN"
  | "SLCAN_ACTIVE"
  | "EXITING_SLCAN"
  | "RECONNECTING_MAVLINK"
  | "ERROR";

export interface SlcanModeSnapshot {
  state: SlcanModeState;
  droneId: string | null;
  bus: 1 | 2 | null;
  bitrate: number | null;
  timeoutSec: number | null;
  enteredAt: number | null;
  autoRevertAt: number | null;
  errorMessage: string | null;
  /** Wall-clock ms used to derive countdown. Bumped by the active-state ticker. */
  tickMs: number;
  /**
   * Hand-back closure that tears down the SLCAN session and restores
   * MAVLink. Populated by the flash arbiter once SLCAN_ACTIVE is reached
   * and cleared whenever the state machine returns to IDLE. The banner
   * uses this to drive the "Resume MAVLink" button.
   */
  exitFn: (() => Promise<void>) | null;
}

export interface BeginEnteringArgs {
  droneId: string;
  bus: 1 | 2;
  bitrate: number;
  timeoutSec: number;
}

interface SlcanModeActions {
  beginEntering(args: BeginEnteringArgs): void;
  markActive(): void;
  beginExiting(): void;
  markReconnecting(): void;
  markError(message: string): void;
  reset(): void;
  /**
   * Register the closure that exits SLCAN mode. The arbiter calls this
   * right after `markActive()` so the banner can drive a "Resume MAVLink"
   * button independently of the panel that triggered entry.
   */
  setExitFn(exitFn: (() => Promise<void>) | null): void;
}

const INITIAL: SlcanModeSnapshot = {
  state: "IDLE",
  droneId: null,
  bus: null,
  bitrate: null,
  timeoutSec: null,
  enteredAt: null,
  autoRevertAt: null,
  errorMessage: null,
  tickMs: 0,
  exitFn: null,
};

export const useSlcanModeStore = create<SlcanModeSnapshot & SlcanModeActions>(
  (set, get) => ({
    ...INITIAL,

    beginEntering: ({ droneId, bus, bitrate, timeoutSec }) => {
      const s = get();
      // Single-flight — only legal from IDLE or ERROR.
      if (s.state !== "IDLE" && s.state !== "ERROR") {
        throw new Error(
          `Cannot begin SLCAN entry from state "${s.state}"; reset first`,
        );
      }
      set({
        state: "ENTERING_SLCAN",
        droneId,
        bus,
        bitrate,
        timeoutSec,
        enteredAt: null,
        autoRevertAt: null,
        errorMessage: null,
        tickMs: Date.now(),
      });
    },

    markActive: () => {
      const s = get();
      if (s.state !== "ENTERING_SLCAN") return;
      const now = Date.now();
      const ttl = s.timeoutSec != null && s.timeoutSec > 0
        ? s.timeoutSec * 1000
        : null;
      set({
        state: "SLCAN_ACTIVE",
        enteredAt: now,
        autoRevertAt: ttl != null ? now + ttl : null,
        tickMs: now,
      });
    },

    beginExiting: () => {
      const s = get();
      if (s.state !== "SLCAN_ACTIVE" && s.state !== "ERROR") return;
      // Clear the exit closure as soon as exit starts so the banner can
      // disable its Resume button (the closure is mid-flight and cannot
      // be re-entered safely).
      set({ state: "EXITING_SLCAN", tickMs: Date.now(), exitFn: null });
    },

    markReconnecting: () => {
      set({ state: "RECONNECTING_MAVLINK", tickMs: Date.now() });
    },

    markError: (message) => {
      set({ state: "ERROR", errorMessage: message, tickMs: Date.now() });
    },

    reset: () => {
      set({ ...INITIAL });
    },

    setExitFn: (exitFn) => {
      set({ exitFn });
    },
  }),
);

/**
 * Derive a `mm:ss` countdown from a snapshot. Returns null when not in
 * SLCAN_ACTIVE or when no auto-revert deadline is set.
 */
export function getCountdownLabel(s: SlcanModeSnapshot): string | null {
  if (s.state !== "SLCAN_ACTIVE" || s.autoRevertAt == null) return null;
  const remaining = Math.max(0, s.autoRevertAt - s.tickMs);
  const totalSec = Math.floor(remaining / 1000);
  const mm = Math.floor(totalSec / 60)
    .toString()
    .padStart(2, "0");
  const ss = (totalSec % 60).toString().padStart(2, "0");
  return `${mm}:${ss}`;
}
