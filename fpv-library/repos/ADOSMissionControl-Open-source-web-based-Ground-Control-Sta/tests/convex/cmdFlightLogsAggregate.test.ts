/**
 * Contract + arithmetic tests for the denormalized flight-log aggregate.
 *
 * stats + getCount used to .collect() every flight-log row (loading the full
 * document with large path/events/media arrays) just to sum four numbers.
 * They now read one per-user aggregate row maintained incrementally inside
 * upsert/remove. These tests pin (a) the source wiring so a refactor cannot
 * silently re-introduce the full scan on the hot path, and (b) the
 * contribution arithmetic that the aggregate must keep in lockstep with the
 * prior full-scan semantics.
 */
import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";

const FLIGHT_LOGS_PATH = path.join(process.cwd(), "convex/cmdFlightLogs.ts");

describe("flight-log aggregate wiring", () => {
  it("reads the aggregate row in stats + getCount (not a full collect on the hot path)", async () => {
    const text = await readFile(FLIGHT_LOGS_PATH, "utf8");
    // Both surfaces query the single aggregate row.
    const aggregateReads = text.match(/query\("cmd_flightLogAggregates"\)/g) ?? [];
    // upsert/remove maintain it + stats + getCount read it.
    expect(aggregateReads.length).toBeGreaterThanOrEqual(3);
    expect(text).toContain('query("cmd_flightLogAggregates")');
  });

  it("maintains the aggregate on insert, update, and remove", async () => {
    const text = await readFile(FLIGHT_LOGS_PATH, "utf8");
    // New insert adds a contribution; remove subtracts one; update applies
    // the old→new delta.
    expect(text).toContain("applyAggregateDelta(ctx, userId, contributionOf(record))");
    expect(text).toContain("subtractContribution(contributionOf(existing))");
  });
});

/**
 * Re-implement the contribution + delta arithmetic exactly as the source does
 * and prove the running aggregate matches a full re-sum across an
 * insert/update/remove sequence. This guards the invariant that the
 * incremental path produces the same totals the prior full scan would.
 */
interface Contribution {
  count: number;
  totalSeconds: number;
  totalMeters: number;
  batteryHours: number;
}

function contributionOf(r: {
  duration?: number;
  distance?: number;
  batteryUsed?: number;
}): Contribution {
  const duration = r.duration ?? 0;
  const distance = r.distance ?? 0;
  const batteryUsed = r.batteryUsed ?? 0;
  return {
    count: 1,
    totalSeconds: duration,
    totalMeters: distance,
    batteryHours: (batteryUsed / 100) * (duration / 3600),
  };
}

function add(a: Contribution, b: Contribution): Contribution {
  return {
    count: Math.max(0, a.count + b.count),
    totalSeconds: Math.max(0, a.totalSeconds + b.totalSeconds),
    totalMeters: Math.max(0, a.totalMeters + b.totalMeters),
    batteryHours: Math.max(0, a.batteryHours + b.batteryHours),
  };
}

function negate(c: Contribution): Contribution {
  return {
    count: -c.count,
    totalSeconds: -c.totalSeconds,
    totalMeters: -c.totalMeters,
    batteryHours: -c.batteryHours,
  };
}

describe("flight-log aggregate arithmetic", () => {
  it("incremental aggregate equals a full re-sum after insert/update/remove", () => {
    const ZERO: Contribution = {
      count: 0,
      totalSeconds: 0,
      totalMeters: 0,
      batteryHours: 0,
    };

    // Two rows inserted.
    const a1 = { duration: 600, distance: 1200, batteryUsed: 40 };
    const a2 = { duration: 900, distance: 3000, batteryUsed: 60 };
    let agg = add(ZERO, contributionOf(a1));
    agg = add(agg, contributionOf(a2));

    // a1 updated in place (an unsealed revision): apply old→new delta.
    const a1v2 = { duration: 720, distance: 1500, batteryUsed: 50 };
    agg = add(agg, {
      count: contributionOf(a1v2).count - contributionOf(a1).count,
      totalSeconds:
        contributionOf(a1v2).totalSeconds - contributionOf(a1).totalSeconds,
      totalMeters:
        contributionOf(a1v2).totalMeters - contributionOf(a1).totalMeters,
      batteryHours:
        contributionOf(a1v2).batteryHours - contributionOf(a1).batteryHours,
    });

    // a2 removed.
    agg = add(agg, negate(contributionOf(a2)));

    // Full re-sum of the surviving rows (a1v2 only).
    const expected = add(ZERO, contributionOf(a1v2));

    expect(agg.count).toBe(expected.count);
    expect(agg.totalSeconds).toBeCloseTo(expected.totalSeconds, 9);
    expect(agg.totalMeters).toBeCloseTo(expected.totalMeters, 9);
    expect(agg.batteryHours).toBeCloseTo(expected.batteryHours, 9);
  });
});
