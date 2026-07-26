"use client";

import { useRef, useEffect, useCallback, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useTelemetryStore } from "@/stores/telemetry-store";
import { useDroneStore } from "@/stores/drone-store";
import { useMissionStore } from "@/stores/mission-store";
import { mpsToKph } from "@/lib/telemetry-utils";
import { isTimestampFresh } from "@/hooks/use-telemetry-freshness";
import {
  drawSkyGround,
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

/**
 * Artificial horizon HUD with sky/ground gradient background.
 * Used on the Overview tab — full glass cockpit experience.
 */
export function OverviewHud() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const popupRef = useRef<Window | null>(null);
  const [isDetached, setIsDetached] = useState(false);
  const [popupContainer, setPopupContainer] = useState<HTMLDivElement | null>(null);

  const reattach = useCallback(() => {
    setIsDetached(false);
    setPopupContainer(null);

    const popup = popupRef.current;
    if (popup && !popup.closed) popup.close();
    popupRef.current = null;
  }, []);

  const detach = useCallback(() => {
    const existing = popupRef.current;
    if (existing && !existing.closed) {
      existing.focus();
      return;
    }

    const popup = window.open(
      "",
      "overview-hud-detached",
      "width=980,height=640,resizable=yes,scrollbars=no"
    );
    if (!popup) return;

    popup.document.title = "HUD";
    popup.document.body.innerHTML = "";
    popup.document.body.style.margin = "0";
    popup.document.body.style.background = "#0a1428";
    popup.document.body.style.overflow = "hidden";

    // Mirror stylesheets so utility classes render in the detached window.
    const styleNodes = Array.from(document.querySelectorAll("style, link[rel='stylesheet']"));
    for (const node of styleNodes) {
      popup.document.head.appendChild(node.cloneNode(true));
    }

    const container = popup.document.createElement("div");
    container.style.width = "100vw";
    container.style.height = "100vh";
    popup.document.body.appendChild(container);

    popup.addEventListener("beforeunload", () => {
      setIsDetached(false);
      setPopupContainer(null);
      popupRef.current = null;
    });

    popupRef.current = popup;
    setPopupContainer(container);
    setIsDetached(true);
    popup.focus();
  }, []);

  const handleToggleDetach = useCallback(() => {
    if (isDetached) {
      reattach();
      return;
    }
    detach();
  }, [detach, isDetached, reattach]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

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

    // Sky/ground gradient FIRST (background)
    drawSkyGround(ctx, w, h, pitch, roll);

    // Instruments on top
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
  }, []);

  useEffect(() => {
    rafRef.current = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(rafRef.current);
      const popup = popupRef.current;
      if (popup && !popup.closed) popup.close();
      popupRef.current = null;
    };
  }, [draw]);

  const hudContent = useMemo(() => (
    <div
      className="relative w-full h-full border border-border-default overflow-hidden bg-[#0a1428]"
      onDoubleClick={handleToggleDetach}
      title={isDetached ? "Double-click to reattach" : "Double-click to detach into a new window"}
    >
      <span className="absolute top-2 left-2 z-10 text-[9px] font-mono text-text-tertiary">
        Attitude
      </span>
      <span className="absolute top-2 right-2 z-10 text-[9px] font-mono text-text-tertiary">
        {isDetached ? "Detached" : "Double-click to detach"}
      </span>
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />
    </div>
  ), [handleToggleDetach, isDetached]);

  if (isDetached && popupContainer) {
    return (
      <>
        <div className="relative w-full h-full border border-border-default overflow-hidden bg-bg-secondary">
          <div className="absolute inset-0 flex items-center justify-center text-xs text-text-tertiary font-mono">
            HUD detached to separate window. Double-click HUD there or close that window to reattach.
          </div>
        </div>
        {createPortal(hudContent, popupContainer)}
      </>
    );
  }

  return hudContent;
}
