"use client";

import { useRef, useEffect, useCallback } from "react";
import { useTelemetryStore } from "@/stores/telemetry-store";
import { useDroneStore } from "@/stores/drone-store";
import { useMissionStore } from "@/stores/mission-store";
import { mpsToKph } from "@/lib/telemetry-utils";
import { isTimestampFresh } from "@/hooks/use-telemetry-freshness";
import {
  drawPitchLadder,
  drawRollArc,
  drawCrosshair,
  drawSpeedTape,
  drawAltTape,
  drawHeadingCompass,
  drawBatteryHud,
  drawGpsAndMode,
  drawArmedStatus,
  drawSignalBars,
  drawFlightTimer,
} from "@/lib/hud-draw";

// ── Main component ──────────────────────────────────────────────

export function OsdOverlay() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  const draw = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Match canvas to parent size
    const parent = canvas.parentElement;
    if (!parent) return;
    const rect = parent.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;

    if (
      canvas.width !== Math.floor(rect.width * dpr) ||
      canvas.height !== Math.floor(rect.height * dpr)
    ) {
      canvas.width = Math.floor(rect.width * dpr);
      canvas.height = Math.floor(rect.height * dpr);
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const w = rect.width;
    const h = rect.height;
    const cx = w / 2;
    const cy = h / 2;

    ctx.clearRect(0, 0, w, h);

    // Read telemetry state directly (no hooks — avoids re-renders)
    const tState = useTelemetryStore.getState();
    const dState = useDroneStore.getState();
    const mState = useMissionStore.getState();

    const att = tState.attitude.latest();
    const pos = tState.position.latest();
    const bat = tState.battery.latest();
    const gps = tState.gps.latest();
    const vfr = tState.vfr.latest();

    const pitch = att?.pitch ?? 0;
    const roll = att?.roll ?? 0;
    // Gate each readout on the freshness of its source sample: a stale/absent
    // value renders "—" (via the null-aware draw fns) rather than a fabricated
    // 0 that reads as a live standstill / dead battery / north lock. An MSP or
    // not-yet-connected FC produces no fresh samples, so the HUD stays honest
    // instead of showing 0.0V / 0 sats / level readouts as if live (Rule 44).
    const attFresh = isTimestampFresh(att?.timestamp);
    const posFresh = isTimestampFresh(pos?.timestamp);
    const batFresh = isTimestampFresh(bat?.timestamp);
    const gpsFresh = isTimestampFresh(gps?.timestamp);
    const vfrFresh = isTimestampFresh(vfr?.timestamp);
    const heading =
      posFresh && typeof pos?.heading === "number"
        ? pos.heading
        : vfrFresh && typeof vfr?.heading === "number"
          ? vfr.heading
          : null;
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
    const speedKph = speedMps !== null ? mpsToKph(speedMps) : null;
    const batteryPct =
      batFresh && typeof bat?.remaining === "number" && bat.remaining >= 0
        ? bat.remaining
        : null;
    const satellites =
      gpsFresh && typeof gps?.satellites === "number" ? gps.satellites : null;
    const armed = attFresh ? dState.armState === "armed" : null;
    const mode = dState.flightMode;
    const startedAt = mState.activeMission?.startedAt;

    // Draw OSD elements
    drawPitchLadder(ctx, cx, cy, pitch, roll, h);
    drawRollArc(ctx, cx, cy, roll, h);
    drawCrosshair(ctx, cx, cy);
    drawSpeedTape(ctx, cx - w * 0.25, cy, speedKph, h);
    drawAltTape(ctx, cx + w * 0.25, cy, alt, h);
    drawHeadingCompass(ctx, cx, 30, heading, w);
    drawBatteryHud(ctx, cx, h - 45, batteryPct);
    drawGpsAndMode(ctx, 16, h - 20, satellites, mode);
    drawArmedStatus(ctx, cx, cy + 34, armed);
    drawSignalBars(ctx, w - 80, h - 20, 4);
    drawFlightTimer(ctx, w - 16, h - 20, startedAt);

    rafRef.current = requestAnimationFrame(draw);
  };

  useEffect(() => {
    rafRef.current = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none"
      style={{ zIndex: 5 }}
    />
  );
}
