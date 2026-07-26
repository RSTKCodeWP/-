/**
 * @module calibration.test
 * @description Unit tests for the pure WFB link auto-calibration engine:
 * sample averaging, cell classification, best-pick ranking, and the sweep
 * orchestration (order, abort, progress). No network or React.
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi } from "vitest";
import {
  AbortError,
  averageSamples,
  evaluateCell,
  pickBest,
  runCalibration,
  DEFAULT_CAL_CONFIG,
  type CalCellResult,
  type CalMeasurement,
  type CalTrio,
} from "@/lib/api/ground-station/calibration";

const m = (over: Partial<CalMeasurement> = {}): CalMeasurement => ({
  lossPercent: 0,
  fecFailed: 0,
  validRxPacketsPerS: 800,
  bitrateKbps: 4000,
  rssiDbm: -50,
  ...over,
});

const cell = (
  trio: CalTrio,
  avg: CalMeasurement,
  threshold = 2,
): CalCellResult => evaluateCell(trio, avg, threshold);

describe("averageSamples", () => {
  it("averages finite fields and sums fecFailed", () => {
    const avg = averageSamples([
      m({ lossPercent: 1, fecFailed: 0, bitrateKbps: 4000 }),
      m({ lossPercent: 3, fecFailed: 2, bitrateKbps: 3000 }),
    ]);
    expect(avg.lossPercent).toBe(2);
    expect(avg.fecFailed).toBe(2);
    expect(avg.bitrateKbps).toBe(3500);
  });

  it("returns null for an all-null field", () => {
    const avg = averageSamples([
      m({ bitrateKbps: null }),
      m({ bitrateKbps: null }),
    ]);
    expect(avg.bitrateKbps).toBeNull();
  });
});

describe("evaluateCell", () => {
  const trio = { mcs: 3, fecK: 8, fecN: 12 };

  it("flags link_lost when no valid packets decode", () => {
    expect(cell(trio, m({ validRxPacketsPerS: 0 })).verdict).toBe("link_lost");
    expect(cell(trio, m({ validRxPacketsPerS: null })).verdict).toBe("link_lost");
  });

  it("flags fec_fail on any unrecoverable block (received-side)", () => {
    expect(cell(trio, m({ fecFailed: 1 })).verdict).toBe("fec_fail");
  });

  it("flags lossy above the loss threshold", () => {
    expect(cell(trio, m({ lossPercent: 5 })).verdict).toBe("lossy");
  });

  it("passes a clean cell", () => {
    expect(cell(trio, m()).verdict).toBe("ok");
  });
});

describe("pickBest", () => {
  it("maximizes goodput among clean cells", () => {
    const results = [
      cell({ mcs: 1, fecK: 8, fecN: 12 }, m({ bitrateKbps: 2000 })),
      cell({ mcs: 3, fecK: 8, fecN: 12 }, m({ bitrateKbps: 4000 })),
      cell({ mcs: 5, fecK: 8, fecN: 10 }, m({ fecFailed: 1 })), // rejected
    ];
    const { best, marginal } = pickBest(results);
    expect(marginal).toBe(false);
    expect(best?.trio.mcs).toBe(3);
    expect(best?.goodputKbps).toBe(4000);
  });

  it("tie-breaks equal goodput toward the lower MCS", () => {
    const results = [
      cell({ mcs: 5, fecK: 8, fecN: 10 }, m({ bitrateKbps: 4000 })),
      cell({ mcs: 1, fecK: 8, fecN: 12 }, m({ bitrateKbps: 4000 })),
    ];
    expect(pickBest(results).best?.trio.mcs).toBe(1);
  });

  it("falls back to the lowest-loss survivor when nothing is fully clean", () => {
    const results = [
      cell({ mcs: 5, fecK: 8, fecN: 10 }, m({ lossPercent: 8 })),
      cell({ mcs: 1, fecK: 8, fecN: 16 }, m({ lossPercent: 4 })),
    ];
    const { best, marginal } = pickBest(results);
    expect(marginal).toBe(true);
    expect(best?.trio.fecN).toBe(16);
  });

  it("returns null when every cell lost the link", () => {
    const results = [
      cell({ mcs: 5, fecK: 8, fecN: 10 }, m({ validRxPacketsPerS: 0 })),
    ];
    expect(pickBest(results).best).toBeNull();
  });
});

describe("runCalibration", () => {
  const instantSleep = () => Promise.resolve();

  it("sweeps every cell in order and recommends the best", async () => {
    const swept: CalTrio[] = [];
    const grid: CalTrio[] = [
      { mcs: 1, fecK: 8, fecN: 16 },
      { mcs: 3, fecK: 8, fecN: 12 },
    ];
    // Cell 0 decodes at 2 Mbps clean; cell 1 at 4 Mbps clean → cell 1 wins.
    const byTrio = new Map<number, CalMeasurement>([
      [1, m({ bitrateKbps: 2000 })],
      [3, m({ bitrateKbps: 4000 })],
    ]);
    let current = 1;
    const out = await runCalibration(
      { ...DEFAULT_CAL_CONFIG, grid, samples: 2 },
      {
        sweep: async (t) => {
          swept.push(t);
          current = t.mcs;
        },
        measure: async () => byTrio.get(current)!,
        sleep: instantSleep,
      },
    );
    expect(swept).toEqual(grid);
    expect(out.results).toHaveLength(2);
    expect(out.best?.trio.mcs).toBe(3);
    expect(out.marginal).toBe(false);
  });

  it("reports progress per cell", async () => {
    const onCell = vi.fn();
    await runCalibration(
      {
        grid: [{ mcs: 1, fecK: 8, fecN: 12 }],
        settleMs: 0,
        measureMs: 0,
        samples: 1,
        lossThresholdPct: 2,
      },
      { sweep: async () => {}, measure: async () => m(), sleep: instantSleep, onCell },
    );
    expect(onCell).toHaveBeenCalledTimes(1);
    expect(onCell).toHaveBeenCalledWith(1, 1, expect.objectContaining({ verdict: "ok" }));
  });

  it("aborts mid-sweep when the signal trips", async () => {
    const signal = { aborted: false };
    const sweep = vi.fn(async (t: CalTrio) => {
      if (t.mcs === 3) signal.aborted = true; // trip after the 2nd cell starts
    });
    await expect(
      runCalibration(
        {
          grid: [
            { mcs: 1, fecK: 8, fecN: 12 },
            { mcs: 3, fecK: 8, fecN: 12 },
            { mcs: 5, fecK: 8, fecN: 10 },
          ],
          settleMs: 0,
          measureMs: 0,
          samples: 1,
          lossThresholdPct: 2,
        },
        { sweep, measure: async () => m(), sleep: instantSleep, signal },
      ),
    ).rejects.toBeInstanceOf(AbortError);
    // The 3rd cell never starts.
    expect(sweep).toHaveBeenCalledTimes(2);
  });
});
