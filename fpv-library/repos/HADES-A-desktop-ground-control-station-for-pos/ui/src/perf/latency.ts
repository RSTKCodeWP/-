/* Glass-to-glass latency instrument (impl-plan Task 5.11 / M3). Records per-frame stage
 * timestamps (socket-receive → decoded → painted) and reports the distribution against the
 * ≤120 ms IN-APP budget (frame on socket → painted with overlay + pin; drone-link latency is
 * excluded — it's outside the app). Times are injected (performance.now() at the call sites),
 * so this stays pure and the measurement harness can assert exact values.
 *
 * Honest provenance: a number from this meter is the IN-APP path only, on whatever hardware
 * it ran. The field ≤120 ms gate is a manual on-device run; this proves the in-app stages and
 * gives the methodology + per-stage sub-budget. */

export type Stage = "socket" | "decoded" | "painted";

export interface Sample {
  frameId: number;
  totalMs: number; // painted - socket
  decodeMs: number; // decoded - socket (0 if no decode mark)
  paintMs: number; // painted - decoded (or - socket if no decode mark)
}

export interface LatencyReport {
  count: number;
  p50Ms: number;
  p95Ms: number;
  maxMs: number;
  meanMs: number;
  withinBudgetMs: (budget: number) => boolean; // p95 ≤ budget
}

export class LatencyMeter {
  readonly samples: Sample[] = [];
  private pending = new Map<number, Partial<Record<Stage, number>>>();

  constructor(private readonly cap = 600) {}

  mark(frameId: number, stage: Stage, t: number): void {
    const m = this.pending.get(frameId) ?? {};
    m[stage] = t;
    this.pending.set(frameId, m);
  }

  /** Finalize a frame: emit a sample iff it has both socket and painted marks. */
  commit(frameId: number): void {
    const m = this.pending.get(frameId);
    this.pending.delete(frameId);
    if (!m || m.socket === undefined || m.painted === undefined) return; // incomplete → no sample
    const decodeMs = m.decoded !== undefined ? m.decoded - m.socket : 0;
    const paintMs = m.decoded !== undefined ? m.painted - m.decoded : m.painted - m.socket;
    this.samples.push({ frameId, totalMs: m.painted - m.socket, decodeMs, paintMs });
    if (this.samples.length > this.cap) this.samples.shift();
  }

  get count(): number {
    return this.samples.length;
  }

  report(): LatencyReport {
    const totals = this.samples.map((s) => s.totalMs).sort((a, b) => a - b);
    const pct = (p: number) =>
      totals.length === 0 ? 0 : totals[Math.min(totals.length - 1, Math.floor((p / 100) * totals.length))];
    const mean = totals.length === 0 ? 0 : totals.reduce((a, b) => a + b, 0) / totals.length;
    const p95 = pct(95);
    return {
      count: totals.length,
      p50Ms: pct(50),
      p95Ms: p95,
      maxMs: totals.length === 0 ? 0 : totals[totals.length - 1],
      meanMs: mean,
      withinBudgetMs: (budget: number) => totals.length > 0 && p95 <= budget,
    };
  }
}

// app-wide singleton the video/map paint paths report into (wired in 5.11 instrumentation).
export const latencyMeter = new LatencyMeter();
