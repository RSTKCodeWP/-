"use client";

/**
 * @module atlas-readiness-store
 * @description Per-drone Atlas capture-readiness cache, keyed by the bare device
 * id. `use-atlas-control` polls `GET /api/atlas/readiness` for the focused drone
 * (local-first, Rule 39) and writes the snapshot here; the node-detail surface
 * registry reads {@link AtlasReadinessState.isCapturing} synchronously (via
 * `getState()`) to decide whether the "Live World" tab is shown — one tab when
 * the drone is not capturing, two while it is.
 *
 * Not persisted: readiness is live agent state, re-fetched on tab mount. The
 * store keeps last-known readiness per device so switching drones reads a
 * different key rather than clobbering a shared slice.
 *
 * @license GPL-3.0-only
 */

import { create } from "zustand";

import {
  isActiveCaptureState,
  type AtlasReadiness,
} from "@/lib/agent/atlas-control-client";

interface AtlasReadinessState {
  /** Last-known readiness snapshot per bare device id. */
  readiness: Record<string, AtlasReadiness>;
  /** Store (replace) the readiness snapshot for a device. */
  setReadiness: (deviceId: string, readiness: AtlasReadiness) => void;
  /** Drop the readiness for a device (e.g. on unpair). */
  clear: (deviceId: string) => void;
  /** The last-known readiness for a device, or null. */
  getReadiness: (deviceId: string) => AtlasReadiness | null;
  /** Whether the device is actively capturing. Derived from BOTH the standalone
   * `capturing` bool AND the lifecycle `state` (capturing / paused / finalizing)
   * so a paused session — where an agent may report `capturing:false` while
   * `state:"paused"` — still keeps the Live World tab visible (Rule 44).
   * Synchronous; safe to read from a surface `when()` via
   * `useAtlasReadinessStore.getState().isCapturing(deviceId)`. */
  isCapturing: (deviceId: string) => boolean;
}

export const useAtlasReadinessStore = create<AtlasReadinessState>((set, get) => ({
  readiness: {},
  setReadiness: (deviceId, readiness) =>
    set((state) => ({
      readiness: { ...state.readiness, [deviceId]: readiness },
    })),
  clear: (deviceId) =>
    set((state) => {
      if (!(deviceId in state.readiness)) return state;
      const next = { ...state.readiness };
      delete next[deviceId];
      return { readiness: next };
    }),
  getReadiness: (deviceId) => get().readiness[deviceId] ?? null,
  isCapturing: (deviceId) => {
    const r = get().readiness[deviceId];
    return r ? r.capturing === true || isActiveCaptureState(r.state) : false;
  },
}));
