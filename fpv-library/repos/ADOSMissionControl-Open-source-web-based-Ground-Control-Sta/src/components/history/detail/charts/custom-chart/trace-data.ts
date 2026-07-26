/**
 * @module history/detail/charts/custom-chart/trace-data
 * @description Builds the aligned (times, values) tuple uPlot expects
 * from a list of recorded telemetry frames. Pure function, no React,
 * no DOM — easy to unit test.
 * @license GPL-3.0-only
 */

import type { TelemetryFrame } from "@/lib/telemetry-recorder";
import { CHANNEL_REGISTRY } from "./channel-registry";
import type { TraceConfig } from "./types";

const MAX_PTS = 50_000;

export function extractTraceData(
  frames: TelemetryFrame[],
  traces: TraceConfig[],
): { times: number[]; values: (number | null)[][] } {
  // Group frames per trace; each trace gets its own sparse time→value map.
  const traceMaps: Map<number, number | null>[] = traces.map(() => new Map());

  for (const f of frames) {
    for (let i = 0; i < traces.length; i++) {
      const tr = traces[i];
      if (f.channel !== tr.channel) continue;
      const chanDef = CHANNEL_REGISTRY.find((c) => c.channel === tr.channel);
      const fieldDef = chanDef?.fields.find((fd) => fd.key === tr.field);
      if (!fieldDef) continue;
      const val = fieldDef.extract(f.data as Record<string, unknown>);
      const tSec = f.offsetMs / 1000;
      traceMaps[i].set(tSec, val ?? null);
    }
  }

  // Build a unified sorted time axis.
  const timeSet = new Set<number>();
  for (const m of traceMaps) {
    for (const t of m.keys()) timeSet.add(t);
  }
  const times = Array.from(timeSet).sort((a, b) => a - b);

  // Downsample when over 50k points to keep uPlot snappy.
  let sampledTimes = times;
  if (times.length > MAX_PTS) {
    const step = Math.ceil(times.length / MAX_PTS);
    sampledTimes = times.filter((_, i) => i % step === 0);
  }

  const values: (number | null)[][] = traces.map((_, i) =>
    sampledTimes.map((t) => traceMaps[i].get(t) ?? null),
  );

  return { times: sampledTimes, values };
}
