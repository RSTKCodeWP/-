/**
 * @module sim-replay-store.test
 * @description Unit tests for the sim-replay store's parse→positions mapping:
 * `extractPositions` channel filtering, no-fix / invalid-frame rejection, and
 * altitude preference, plus the store's `clear` reset and the unsupported-format
 * branch of `loadFromFile`. Synthetic frames only — no real coordinates.
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeEach } from "vitest";
import type { TelemetryFrame } from "@/lib/telemetry-recorder";
import {
  extractPositions,
  useSimReplayStore,
} from "@/stores/sim-replay-store";

describe("extractPositions", () => {
  it("keeps only position / globalPosition frames in order", () => {
    const frames: TelemetryFrame[] = [
      { offsetMs: 0, channel: "position", data: { lat: 1.23, lon: 4.56, alt: 100 } },
      { offsetMs: 100, channel: "attitude", data: { roll: 0, pitch: 0, yaw: 0 } },
      { offsetMs: 200, channel: "globalPosition", data: { lat: 1.24, lon: 4.57, alt: 110, relativeAlt: 50 } },
      { offsetMs: 300, channel: "battery", data: { voltage: 16 } },
    ];
    const positions = extractPositions(frames);
    // amsl=true because the absolute `alt` channel supplied the altitude.
    expect(positions).toEqual([
      { lat: 1.23, lon: 4.56, alt: 100, amsl: true },
      { lat: 1.24, lon: 4.57, alt: 110, amsl: true },
    ]);
  });

  it("prefers absolute alt, falling back to relativeAlt then 0", () => {
    const frames: TelemetryFrame[] = [
      { offsetMs: 0, channel: "position", data: { lat: 2, lon: 3, relativeAlt: 42 } },
      { offsetMs: 1, channel: "position", data: { lat: 2.1, lon: 3.1 } },
    ];
    // relativeAlt fallback and the 0 default are height-above-home, not MSL.
    expect(extractPositions(frames)).toEqual([
      { lat: 2, lon: 3, alt: 42, amsl: false },
      { lat: 2.1, lon: 3.1, alt: 0, amsl: false },
    ]);
  });

  it("skips 0/0 null-island no-fix frames", () => {
    const frames: TelemetryFrame[] = [
      { offsetMs: 0, channel: "position", data: { lat: 0, lon: 0, alt: 0 } },
      { offsetMs: 1, channel: "position", data: { lat: 5, lon: 6, alt: 10 } },
    ];
    expect(extractPositions(frames)).toEqual([{ lat: 5, lon: 6, alt: 10, amsl: true }]);
  });

  it("skips frames with non-finite or out-of-range coordinates", () => {
    const frames: TelemetryFrame[] = [
      { offsetMs: 0, channel: "position", data: { lat: Number.NaN, lon: 4.5, alt: 0 } },
      { offsetMs: 1, channel: "position", data: { lat: 95, lon: 4.5, alt: 0 } },
      { offsetMs: 2, channel: "position", data: { lat: 4.5, lon: 200, alt: 0 } },
      { offsetMs: 3, channel: "position", data: { lat: 4.5, lon: 4.5, alt: 7 } },
    ];
    expect(extractPositions(frames)).toEqual([{ lat: 4.5, lon: 4.5, alt: 7, amsl: true }]);
  });

  it("returns an empty array when there are no position frames", () => {
    const frames: TelemetryFrame[] = [
      { offsetMs: 0, channel: "attitude", data: { roll: 0 } },
    ];
    expect(extractPositions(frames)).toEqual([]);
  });
});

describe("useSimReplayStore", () => {
  beforeEach(() => {
    useSimReplayStore.getState().clear();
  });

  it("clear() resets track and error", () => {
    useSimReplayStore.setState({
      track: { positions: [{ lat: 1, lon: 2, alt: 3 }], name: "x.bin" },
      error: "parse-failed",
    });
    useSimReplayStore.getState().clear();
    expect(useSimReplayStore.getState().track).toBeNull();
    expect(useSimReplayStore.getState().error).toBeNull();
  });

  it("loadFromFile rejects an unsupported extension without a track", async () => {
    const file = new File([new Uint8Array([1, 2, 3])], "notes.csv", {
      type: "text/csv",
    });
    await useSimReplayStore.getState().loadFromFile(file);
    expect(useSimReplayStore.getState().track).toBeNull();
    expect(useSimReplayStore.getState().error).toBe("unsupported");
  });
});
