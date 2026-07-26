/**
 * PollProvider — generic HTTP-polling traffic source.
 *
 * Local readsb/tar1090, the hosted ADS-B APIs, and OpenSky all reduce to "build
 * a URL (+headers) for the current viewport, fetch JSON, run a parser". This
 * class owns the timer, abort-on-overlap, and error swallowing; concrete sources
 * are just a PollSpec.
 */

import type { TrafficContact, TrafficSource, ViewportBbox } from '../../shared/traffic-types.js';
import type { ProviderContext, TrafficProvider } from './provider.js';

export interface PollRequest {
  url: string;
  headers?: Record<string, string>;
}

export interface PollSpec {
  id: string;
  source: TrafficSource;
  pollMs: number;
  /** Build the request for a viewport, or null to skip this tick. */
  buildRequest(v: ViewportBbox): PollRequest | null;
  parse(json: unknown, nowMs: number): TrafficContact[];
}

const FETCH_TIMEOUT_MS = 8000;

export class PollProvider implements TrafficProvider {
  readonly source: TrafficSource;
  readonly id: string;
  private spec: PollSpec;
  private ctx: ProviderContext | null = null;
  private viewport: ViewportBbox | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private inFlight: AbortController | null = null;

  constructor(spec: PollSpec) {
    this.spec = spec;
    this.id = spec.id;
    this.source = spec.source;
  }

  start(ctx: ProviderContext): void {
    this.ctx = ctx;
    if (this.timer) return;
    this.timer = setInterval(() => void this.poll(), this.spec.pollMs);
    void this.poll();
  }

  setViewport(v: ViewportBbox): void {
    const hadNone = this.viewport === null;
    this.viewport = v;
    // Fetch right away on the first viewport rather than waiting a whole interval.
    if (hadNone && this.ctx) void this.poll();
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.inFlight?.abort();
    this.inFlight = null;
    this.ctx = null;
  }

  private async poll(): Promise<void> {
    if (!this.ctx || !this.viewport) return;
    const req = this.spec.buildRequest(this.viewport);
    if (!req) return;
    // Drop the previous request if it's still running (slow endpoint, fast tick).
    this.inFlight?.abort();
    const ac = new AbortController();
    this.inFlight = ac;
    const timeout = setTimeout(() => ac.abort(), FETCH_TIMEOUT_MS);
    try {
      const res = await fetch(req.url, { headers: req.headers, signal: ac.signal });
      if (!res.ok) {
        this.ctx?.log(`${this.id} HTTP ${res.status}`);
        return;
      }
      const json = await res.json();
      const parsed = this.spec.parse(json, Date.now());
      this.ctx?.emit(parsed);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        this.ctx?.log(`${this.id} fetch failed: ${(err as Error).message}`);
      }
    } finally {
      clearTimeout(timeout);
      if (this.inFlight === ac) this.inFlight = null;
    }
  }
}
