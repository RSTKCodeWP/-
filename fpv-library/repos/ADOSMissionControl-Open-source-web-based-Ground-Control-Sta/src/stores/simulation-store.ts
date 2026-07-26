/**
 * @module simulation-store
 * @description Zustand store for the trajectory-preview playback state.
 * Manages playback controls, camera mode, and elapsed time.
 * Clock-backed: the CesiumJS Clock is the single source of truth for elapsed
 * time. The store delegates every time advancement to the clock and mirrors the
 * clock's elapsed back via syncFromClock() for the HUD and transport controls.
 * Non-persisted — resets on page reload.
 *
 * Decoupled from CesiumJS: the store never imports "cesium" at runtime.
 * All viewer/clock operations are delegated through callback functions
 * supplied by bindSimViewer(). This keeps cesium out of shared chunks.
 * @license GPL-3.0-only
 */

import { create } from "zustand";
import {
  clampElapsed,
  isAtEnd,
  stepBackElapsed,
  stepForwardElapsed,
} from "@/lib/sim-clock";

export type PlaybackState = "stopped" | "playing" | "paused";
export type CameraMode = "topdown" | "follow" | "orbit" | "free";

/** Position synced from CesiumJS 3D entity each tick (authoritative for HUD). */
export interface SyncedPosition {
  lat: number;
  lon: number;
  altAgl: number;
  heading: number;
  speed: number;
  waypointIndex: number;
}

interface SimulationStoreState {
  playbackState: PlaybackState;
  playbackSpeed: number;
  elapsed: number;
  totalDuration: number;
  cameraMode: CameraMode;
  /** Position synced from 3D entity — null until first tick with resolved positions. */
  syncedPosition: SyncedPosition | null;
  /** Whether follow camera heading is locked to flight heading. */
  followHeadingLocked: boolean;
  /** Monotonic counter bumped by resetCameraView() to re-run the camera
   * framing effect (re-fit / recenter the mission for the current mode). */
  cameraViewNonce: number;

  play: () => void;
  pause: () => void;
  stop: () => void;
  /** Seek to the start of the timeline while preserving the current play state. */
  seekToStart: () => void;
  /** Stop and rewind playback only — leaves camera mode and speed untouched. */
  resetPlayback: () => void;
  seek: (time: number) => void;
  stepForward: () => void;
  stepBack: () => void;
  setSpeed: (speed: number) => void;
  setCameraMode: (mode: CameraMode) => void;
  /** Re-frame the current camera mode on the mission (north-up re-fit /
   * recenter). Bumps cameraViewNonce so useSimCamera re-runs. */
  resetCameraView: () => void;
  setTotalDuration: (duration: number) => void;
  syncFromClock: () => void;
  syncPosition: (pos: SyncedPosition) => void;
  toggleFollowHeading: () => void;
  reset: () => void;
}

const POSITION_SYNC_MIN_MS = 100;

const quantizeFine = (v: number) => Math.round(v * 10_000_000) / 10_000_000;
const quantizeTenth = (v: number) => Math.round(v * 10) / 10;

let _lastPositionSyncAt = 0;

function quantizePosition(pos: SyncedPosition): SyncedPosition {
  return {
    lat: quantizeFine(pos.lat),
    lon: quantizeFine(pos.lon),
    altAgl: quantizeTenth(pos.altAgl),
    heading: quantizeTenth(pos.heading),
    speed: quantizeTenth(pos.speed),
    waypointIndex: pos.waypointIndex,
  };
}

function isSamePosition(a: SyncedPosition | null, b: SyncedPosition): boolean {
  return !!a &&
    a.lat === b.lat &&
    a.lon === b.lon &&
    a.altAgl === b.altAgl &&
    a.heading === b.heading &&
    a.speed === b.speed &&
    a.waypointIndex === b.waypointIndex;
}

// ── Viewer bridge ──────────────────────────────────────────────────────
// Instead of importing CesiumJS, the store delegates all viewer/clock
// operations through these callback functions, set by bindSimViewer().

/** Callbacks that encapsulate all CesiumJS viewer operations. */
export interface SimViewerBridge {
  /** Seek the CesiumJS clock to the given elapsed seconds. */
  seekClock: (seconds: number) => void;
  /** Request a render frame. */
  requestRender: () => void;
  /** Set clock.shouldAnimate. */
  setAnimate: (animate: boolean) => void;
  /** Set clock.multiplier. */
  setMultiplier: (multiplier: number) => void;
  /** Set clock.stopTime from elapsed seconds. */
  setStopTime: (totalDuration: number) => void;
  /** Read elapsed seconds from the clock (secondsDifference from start). */
  getElapsed: () => number;
  /** Read clock.shouldAnimate. */
  getShouldAnimate: () => boolean;
  /** Check if the viewer is still alive (not destroyed). */
  isAlive: () => boolean;
}

// Module-level bridge binding (viewer objects are not serializable in Zustand)
let _bridge: SimViewerBridge | null = null;
/** Opaque viewer reference used only for identity checks in unbind. */
let _viewerRef: unknown = null;

export function bindSimViewer(viewer: unknown, bridge: SimViewerBridge) {
  if (_viewerRef === viewer) return; // Already bound to this viewer
  _viewerRef = viewer;
  _bridge = bridge;
}

export function unbindSimViewer(viewer?: unknown) {
  if (viewer && _viewerRef !== viewer) return; // Different viewer, don't unbind
  // Reset every module-global singleton so a stale bridge or sync timestamp can
  // never drive a viewer that has already been torn down.
  _viewerRef = null;
  _bridge = null;
  _lastPositionSyncAt = 0;
}

function seekClock(seconds: number) {
  if (_bridge && _bridge.isAlive()) {
    _bridge.seekClock(seconds);
  }
}

export const useSimulationStore = create<SimulationStoreState>()((set, get) => ({
  playbackState: "stopped",
  playbackSpeed: 1,
  elapsed: 0,
  totalDuration: 0,
  cameraMode: "orbit",
  syncedPosition: null,
  followHeadingLocked: true,
  cameraViewNonce: 0,

  play: () => {
    if (!_bridge || !_bridge.isAlive()) return;
    const { elapsed, totalDuration } = get();
    // If parked at the end, restart from the beginning before playing.
    if (isAtEnd(elapsed, totalDuration)) {
      set({ playbackState: "playing", elapsed: 0 });
      seekClock(0);
    } else {
      set({ playbackState: "playing" });
    }
    _bridge.setAnimate(true);
  },

  pause: () => {
    set({ playbackState: "paused" });
    if (_bridge && _bridge.isAlive()) {
      _bridge.setAnimate(false);
    }
  },

  stop: () => {
    set({ playbackState: "stopped", elapsed: 0 });
    if (_bridge && _bridge.isAlive()) {
      _bridge.setAnimate(false);
    }
    seekClock(0);
  },

  seekToStart: () => {
    // Rewind to the start but keep playing if we were playing — a transport
    // skip-to-start seeks, it does not halt playback.
    set({ elapsed: 0 });
    seekClock(0);
  },

  resetPlayback: () => {
    // Reset PLAYBACK only: stop and rewind to the start. Camera mode and speed
    // are deliberately preserved (resetting the view is a separate concern).
    set({ playbackState: "stopped", elapsed: 0 });
    if (_bridge && _bridge.isAlive()) {
      _bridge.setAnimate(false);
    }
    seekClock(0);
  },

  seek: (time) => {
    const { totalDuration } = get();
    const clamped = clampElapsed(time, totalDuration);
    set({ elapsed: clamped });
    seekClock(clamped);
  },

  stepForward: () => {
    const { elapsed, totalDuration } = get();
    if (totalDuration === 0) return;
    const next = stepForwardElapsed(elapsed, totalDuration);
    set({ elapsed: next });
    // Seek the authoritative clock too, so a tick that lands between this call
    // and the next render resumes from the stepped position (not the old one).
    seekClock(next);
  },

  stepBack: () => {
    const { elapsed, totalDuration } = get();
    if (totalDuration === 0) return;
    const prev = stepBackElapsed(elapsed, totalDuration);
    set({ elapsed: prev });
    seekClock(prev);
  },

  setSpeed: (playbackSpeed) => {
    set({ playbackSpeed });
    if (_bridge && _bridge.isAlive()) {
      _bridge.setMultiplier(playbackSpeed);
    }
  },

  setCameraMode: (cameraMode) => set({ cameraMode }),

  resetCameraView: () => set((s) => ({ cameraViewNonce: s.cameraViewNonce + 1 })),

  syncPosition: (pos) => {
    const syncedPosition = quantizePosition(pos);
    const current = get().syncedPosition;
    if (isSamePosition(current, syncedPosition)) return;

    const now = Date.now();
    const waypointChanged = current?.waypointIndex !== syncedPosition.waypointIndex;
    if (!waypointChanged && now - _lastPositionSyncAt < POSITION_SYNC_MIN_MS) return;

    _lastPositionSyncAt = now;
    set({ syncedPosition });
  },

  toggleFollowHeading: () => set((s) => ({ followHeadingLocked: !s.followHeadingLocked })),

  setTotalDuration: (totalDuration) => {
    // Re-clamp the current elapsed to the new length but never re-zero a
    // non-zero position — changing the timeline length should not rewind an
    // in-progress preview.
    const { elapsed } = get();
    const clamped = clampElapsed(elapsed, totalDuration);
    set({ totalDuration, elapsed: clamped });
    if (_bridge && _bridge.isAlive()) {
      _bridge.setStopTime(totalDuration);
    }
  },

  syncFromClock: () => {
    if (!_bridge || !_bridge.isAlive()) return;
    // The clock is authoritative — mirror its elapsed into the store.
    const elapsed = _bridge.getElapsed();
    const { totalDuration, playbackState, elapsed: current } = get();
    const clamped = clampElapsed(elapsed, totalDuration);

    // Detect CesiumJS auto-stop (ClockRange.CLAMPED halts the clock at stopTime).
    // Natural completion transitions to a fully stopped state (not paused) so
    // the stopped state is reachable by a normal play-through.
    if (playbackState === "playing" && !_bridge.getShouldAnimate()) {
      set({ elapsed: clamped, playbackState: "stopped" });
    } else if (clamped !== current) {
      set({ elapsed: clamped });
    }
  },

  reset: () => {
    _lastPositionSyncAt = 0;
    set({
      playbackState: "stopped",
      playbackSpeed: 1,
      elapsed: 0,
      totalDuration: 0,
      cameraMode: "orbit",
      syncedPosition: null,
      followHeadingLocked: true,
    });
    if (_bridge && _bridge.isAlive()) {
      _bridge.setAnimate(false);
      _bridge.setMultiplier(1);
    }
    seekClock(0);
  },
}));
