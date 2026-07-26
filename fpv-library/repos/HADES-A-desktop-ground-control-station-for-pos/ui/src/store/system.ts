import { create } from "zustand";

/* System-health store — the always-on status strip's data (impl-plan Task 5.3; design doc
 * "trust — degrade visibly, never silently"). Holds link state, telemetry freshness, GPS
 * fix, and the frame-bound heartbeat. The severity() helpers map raw state to the closed
 * status set (DESIGN-SYSTEM §2.4) so the strip uses ONE encoding.
 *
 * P0 life-safety rule: link-lost is a SYSTEM-INTEGRITY failure → `critical` (magenta), NOT
 * `warning` (orange, which is reserved for survivor world-urgency). Telemetry aging is a
 * graceful caution → stale escalation. */

export type Severity = "nominal" | "caution" | "warning" | "critical" | "stale";
export type GpsFix = "none" | "2d" | "3d";

// Telemetry-age thresholds (seconds). Below caution = fresh; past stale = unknown/degraded.
const TEL_CAUTION_S = 1.0;
const TEL_STALE_S = 4.0;

interface SystemState {
  linkUp: boolean;
  telemetryAgeS: number;
  gpsFix: GpsFix;
  gpsSats: number;
  /** The id of the most recent painted frame; the heartbeat is bound to this, not a clock. */
  lastFrameId: number | null;

  setLink: (up: boolean) => void;
  setTelemetryAge: (ageS: number) => void;
  setGps: (fix: GpsFix, sats: number) => void;
  markFrame: (frameId: number) => void;

  linkSeverity: () => Severity;
  telemetrySeverity: () => Severity;
  reset: () => void;
}

export const useSystemStore = create<SystemState>((set, get) => ({
  linkUp: true,
  telemetryAgeS: 0,
  gpsFix: "none",
  gpsSats: 0,
  lastFrameId: null,

  setLink: (up) => set({ linkUp: up }),
  setTelemetryAge: (ageS) => set({ telemetryAgeS: ageS }),
  setGps: (fix, sats) => set({ gpsFix: fix, gpsSats: sats }),
  markFrame: (frameId) => set({ lastFrameId: frameId }),

  // P0: link down = critical (magenta), never warning (orange — that's for survivors).
  linkSeverity: () => (get().linkUp ? "nominal" : "critical"),

  telemetrySeverity: () => {
    const age = get().telemetryAgeS;
    if (age >= TEL_STALE_S) return "stale";
    if (age >= TEL_CAUTION_S) return "caution";
    return "nominal";
  },

  reset: () =>
    set({ linkUp: true, telemetryAgeS: 0, gpsFix: "none", gpsSats: 0, lastFrameId: null }),
}));
