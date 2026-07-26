import { describe, expect, it } from "vitest";

import {
  computeLead,
  pushLeadSample,
  type TrackSample,
} from "@/lib/vision/target-lead";

describe("computeLead", () => {
  it("returns null with fewer than two samples", () => {
    expect(computeLead([{ t: 0, cx: 10, cy: 10 }], 600, 45)).toBeNull();
    expect(computeLead([], 600, 45)).toBeNull();
  });

  it("returns null when the samples span no time", () => {
    const s: TrackSample[] = [
      { t: 100, cx: 0, cy: 0 },
      { t: 100, cx: 50, cy: 0 },
    ];
    expect(computeLead(s, 600, 45)).toBeNull();
  });

  it("returns null for a stationary target (below the speed threshold)", () => {
    // 2 px over 1000 ms = 2 px/sec, far below the 45 px/sec floor.
    const s: TrackSample[] = [
      { t: 0, cx: 100, cy: 100 },
      { t: 1000, cx: 102, cy: 100 },
    ];
    expect(computeLead(s, 600, 45)).toBeNull();
  });

  it("projects a moving target forward by the lead time", () => {
    // 100 px in x over 1000 ms = 100 px/sec. Lead 600 ms → +60 px ahead.
    const s: TrackSample[] = [
      { t: 0, cx: 100, cy: 200 },
      { t: 1000, cx: 200, cy: 200 },
    ];
    const lead = computeLead(s, 600, 45);
    expect(lead).not.toBeNull();
    expect(lead!.cx).toBeCloseTo(260, 5);
    expect(lead!.cy).toBeCloseTo(200, 5);
    expect(lead!.speedPxPerSec).toBeCloseTo(100, 5);
  });

  it("leads along the true 2D velocity vector", () => {
    // dx=30, dy=40 over 500 ms → 60 px/sec x, 80 px/sec y (100 px/sec mag).
    const s: TrackSample[] = [
      { t: 0, cx: 0, cy: 0 },
      { t: 500, cx: 30, cy: 40 },
    ];
    const lead = computeLead(s, 500, 45);
    expect(lead).not.toBeNull();
    // +velocity*leadMs = +30 x, +40 y beyond the last sample.
    expect(lead!.cx).toBeCloseTo(60, 5);
    expect(lead!.cy).toBeCloseTo(80, 5);
    expect(lead!.speedPxPerSec).toBeCloseTo(100, 5);
  });
});

describe("pushLeadSample", () => {
  it("appends and drops samples older than the window", () => {
    const h0: TrackSample[] = [];
    const h1 = pushLeadSample(h0, { t: 0, cx: 0, cy: 0 }, 600);
    const h2 = pushLeadSample(h1, { t: 300, cx: 10, cy: 0 }, 600);
    const h3 = pushLeadSample(h2, { t: 800, cx: 20, cy: 0 }, 600);
    // At t=800 the t=0 sample (age 800 > 600) is dropped; t=300 and t=800 stay.
    expect(h3.map((s) => s.t)).toEqual([300, 800]);
  });

  it("does not mutate the input array", () => {
    const h0: TrackSample[] = [{ t: 0, cx: 0, cy: 0 }];
    const h1 = pushLeadSample(h0, { t: 100, cx: 5, cy: 0 }, 600);
    expect(h0).toHaveLength(1);
    expect(h1).toHaveLength(2);
  });
});
