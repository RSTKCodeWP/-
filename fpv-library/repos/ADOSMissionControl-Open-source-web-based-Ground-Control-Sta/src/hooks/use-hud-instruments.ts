"use client";

/**
 * @module hooks/use-hud-instruments
 * @description Freshness-gated telemetry read for the glass-cockpit instruments
 * (attitude indicator, speed/alt tapes, flight-path marker, heading). Mirrors
 * the null-honest selection logic the canvas `OsdOverlay` used, but as a hook so
 * the new DOM/SVG instruments re-render on each telemetry push. A stale/absent
 * sample yields `null`, so an instrument shows "—" rather than a fabricated 0
 * (Rule 44). Re-renders are driven by the store's `_version` freshness signal;
 * ring-buffer refs are stable.
 * @license GPL-3.0-only
 */

import { useMemo } from "react";
import { useTelemetryStore } from "@/stores/telemetry-store";
import { isTimestampFresh } from "@/hooks/use-telemetry-freshness";
import { mpsToKph } from "@/lib/telemetry-utils";

export interface HudInstruments {
  /** Pitch, degrees (nose-up positive). Null when attitude is stale. */
  pitch: number | null;
  /** Roll, degrees (right-wing-down positive). Null when attitude is stale. */
  roll: number | null;
  /** Relative altitude, meters. */
  alt: number | null;
  /** Ground speed, m/s. */
  speedMps: number | null;
  /** Ground speed, km/h (derived). */
  speedKph: number | null;
  /** Heading, degrees. */
  heading: number | null;
  /** Vertical speed / climb, m/s. */
  climb: number | null;
}

export function useHudInstruments(): HudInstruments {
  const version = useTelemetryStore((s) => s._version);
  const attitudeBuf = useTelemetryStore((s) => s.attitude);
  const positionBuf = useTelemetryStore((s) => s.position);
  const vfrBuf = useTelemetryStore((s) => s.vfr);

  return useMemo<HudInstruments>(() => {
    const att = attitudeBuf.latest();
    const pos = positionBuf.latest();
    const vfr = vfrBuf.latest();

    const attFresh = isTimestampFresh(att?.timestamp);
    const posFresh = isTimestampFresh(pos?.timestamp);
    const vfrFresh = isTimestampFresh(vfr?.timestamp);

    const pitch = attFresh && typeof att?.pitch === "number" ? att.pitch : null;
    const roll = attFresh && typeof att?.roll === "number" ? att.roll : null;

    const alt =
      posFresh && typeof pos?.alt === "number"
        ? pos.alt
        : vfrFresh && typeof vfr?.alt === "number"
          ? vfr.alt
          : null;

    const speedMps =
      vfrFresh && typeof vfr?.groundspeed === "number"
        ? vfr.groundspeed
        : posFresh && typeof pos?.groundSpeed === "number"
          ? pos.groundSpeed
          : null;

    const heading =
      posFresh && typeof pos?.heading === "number"
        ? pos.heading
        : vfrFresh && typeof vfr?.heading === "number"
          ? vfr.heading
          : null;

    const climb =
      vfrFresh && typeof vfr?.climb === "number"
        ? vfr.climb
        : posFresh && typeof pos?.climbRate === "number"
          ? pos.climbRate
          : null;

    return {
      pitch,
      roll,
      alt,
      speedMps,
      speedKph: speedMps !== null ? mpsToKph(speedMps) : null,
      heading,
      climb,
    };
    // version is the freshness trigger; buffer refs are stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version, attitudeBuf, positionBuf, vfrBuf]);
}
