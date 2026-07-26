"use client";

// Single-shot read of the four ring buffers feeding the HUD top bar.
// Ring-buffer references in telemetry-store are stable across pushes; only
// _version bumps on new data, so we depend on _version for the memo.

import { useMemo } from "react";
import { useTelemetryStore } from "@/stores/telemetry-store";
import type { RadioData, VfrData, BatteryData, GpsData } from "@/lib/types";

export interface HudTopBarData {
  radio: RadioData | undefined;
  vfr: VfrData | undefined;
  battery: BatteryData | undefined;
  gps: GpsData | undefined;
}

export function useHudTopBarData(): HudTopBarData {
  const version = useTelemetryStore((s) => s._version);
  const radioBuf = useTelemetryStore((s) => s.radio);
  const vfrBuf = useTelemetryStore((s) => s.vfr);
  const batteryBuf = useTelemetryStore((s) => s.battery);
  const gpsBuf = useTelemetryStore((s) => s.gps);

  return useMemo<HudTopBarData>(
    () => ({
      radio: radioBuf.latest(),
      vfr: vfrBuf.latest(),
      battery: batteryBuf.latest(),
      gps: gpsBuf.latest(),
    }),
    // version is the freshness signal; buffer refs are included to satisfy
    // exhaustive-deps and to recompute if a buffer is ever swapped.
    [version, radioBuf, vfrBuf, batteryBuf, gpsBuf],
  );
}
