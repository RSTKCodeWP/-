/**
 * @module sim-replay-store
 * @description Session-only Zustand store holding a recorded flight track that
 * the operator loads to overlay the ACTUAL flown path on the planned mission in
 * the simulation viewer. Reuses the existing dataflash / ulog / tlog parsers to
 * turn a raw log file into an ordered `{ lat, lon, alt }[]` position array —
 * only real logged positions are kept; a parse failure or a log with no GPS fix
 * leaves the track null and records a stable error code (never a fabricated
 * path). NOT persisted — the loaded track lives for the current session only.
 * @license GPL-3.0-only
 */

import { create } from "zustand";
import type { TelemetryFrame } from "@/lib/telemetry-recorder";

/** A single ordered point of the flown track. `alt` is the logged altitude in metres. */
export interface TrackPoint {
  lat: number;
  lon: number;
  alt: number;
  /**
   * True when `alt` is an absolute MSL/AMSL altitude (the log's `alt` channel);
   * false when it is the `relativeAlt` fallback (height above home, already
   * ellipsoidal-ish for placement). Lets the Cesium overlay geoid-correct only
   * the AMSL points so the flown track does not float off the plan by the geoid
   * undulation.
   */
  amsl?: boolean;
}

/** A loaded actual track. */
export interface ActualTrack {
  positions: TrackPoint[];
  /** Source log filename, shown in the control. */
  name: string;
}

/**
 * Stable, i18n-agnostic error codes. The control maps each to a translated hint
 * so the store never holds user-facing text.
 * - `unsupported`   — file extension is not a recognised log format.
 * - `no-positions`  — log parsed but carried fewer than two GPS-fixed positions.
 * - `parse-failed`  — the parser threw on a corrupt / unreadable file.
 */
export type SimReplayErrorCode = "unsupported" | "no-positions" | "parse-failed";

interface SimReplayState {
  /** The loaded actual track, or null when nothing is loaded. */
  track: ActualTrack | null;
  /** Last error code, or null. Cleared on a successful load or `clear()`. */
  error: SimReplayErrorCode | null;
  /** Parse a recorded log file and extract its flown positions. */
  loadFromFile: (file: File) => Promise<void>;
  /** Drop the loaded track and any error (reset). */
  clear: () => void;
}

/** True when a lat/lon pair is a plausible real fix (finite, in range, not the 0/0 null-island no-fix). */
function isValidFix(lat: number, lon: number): boolean {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return false;
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return false;
  if (lat === 0 && lon === 0) return false;
  return true;
}

/**
 * Extract an ordered position array from parsed telemetry frames.
 *
 * Reads only `position` / `globalPosition` channel frames (the parsers emit
 * these from ArduPilot POS / MAVLink GLOBAL_POSITION_INT rows), preferring the
 * absolute `alt` and falling back to `relativeAlt` so the overlay sits at a
 * defensible height. Frames without a valid GPS fix are skipped — never faked.
 *
 * Exported for unit testing of the parse→positions mapping.
 */
export function extractPositions(frames: TelemetryFrame[]): TrackPoint[] {
  const positions: TrackPoint[] = [];
  for (const frame of frames) {
    if (frame.channel !== "position" && frame.channel !== "globalPosition") continue;
    const d = frame.data as Record<string, unknown>;
    const lat = typeof d.lat === "number" ? d.lat : NaN;
    const lon = typeof d.lon === "number" ? d.lon : NaN;
    if (!isValidFix(lat, lon)) continue;
    // The absolute `alt` channel is MSL/AMSL and needs geoid correction for
    // Cesium placement; the `relativeAlt` fallback is height-above-home and does
    // not. Tag the point so the overlay only corrects the AMSL ones.
    let alt: number;
    let amsl: boolean;
    if (typeof d.alt === "number") {
      alt = d.alt;
      amsl = true;
    } else if (typeof d.relativeAlt === "number") {
      alt = d.relativeAlt;
      amsl = false;
    } else {
      alt = 0;
      amsl = false;
    }
    positions.push({ lat, lon, alt, amsl });
  }
  return positions;
}

/** Lowercase file extension (without the dot), or "". */
function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : "";
}

export const useSimReplayStore = create<SimReplayState>((set) => ({
  track: null,
  error: null,

  loadFromFile: async (file: File) => {
    const name = file.name;
    const ext = extensionOf(name);

    try {
      const buffer = await file.arrayBuffer();
      let positions: TrackPoint[] = [];

      if (ext === "bin" || ext === "log") {
        // ArduPilot DataFlash binary. Parse in-memory and pull frames directly —
        // deliberately NOT via import.ts, which also persists to IndexedDB.
        const { parseDataflashLog } = await import("@/lib/dataflash/parser");
        const { dataflashToFlightRecords } = await import("@/lib/dataflash/to-flight-record");
        const log = parseDataflashLog(new Uint8Array(buffer));
        const flights = dataflashToFlightRecords(log, { sourceFilename: name });
        positions = extractPositions(flights.flatMap((f) => f.frames));
      } else if (ext === "ulg") {
        // PX4 ULog.
        const { parseUlog } = await import("@/lib/ulog/parser");
        const { ulogToFlightRecords } = await import("@/lib/ulog/to-flight-record");
        const log = parseUlog(buffer);
        const flights = ulogToFlightRecords(log, name);
        positions = extractPositions(flights.flatMap((f) => f.frames));
      } else if (ext === "tlog") {
        // MAVLink telemetry log.
        const { parseTlog, tlogToFlightRecord } = await import("@/lib/tlog/parser");
        const packets = parseTlog(buffer);
        const result = tlogToFlightRecord(packets, name);
        positions = result ? extractPositions(result.frames) : [];
      } else {
        set({ error: "unsupported", track: null });
        return;
      }

      if (positions.length < 2) {
        set({ error: "no-positions", track: null });
        return;
      }

      set({ track: { positions, name }, error: null });
    } catch {
      set({ error: "parse-failed", track: null });
    }
  },

  clear: () => set({ track: null, error: null }),
}));
