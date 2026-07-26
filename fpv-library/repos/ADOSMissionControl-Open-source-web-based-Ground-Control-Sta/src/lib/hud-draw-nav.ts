/**
 * @module hud-draw-nav
 * @description Navigation drawing (speed tape, altitude tape, heading compass).
 * @license GPL-3.0-only
 */

import { normalizeHeading } from "@/lib/telemetry-utils";
import { HUD_INK, SHADOW, FONT, setHudStyle, clearShadow } from "./hud-draw";

export function drawSpeedTape(
  ctx: CanvasRenderingContext2D,
  x: number, cy: number,
  speedKph: number | null, h: number
) {
  // Absent / stale speed: draw just the readout box with "—" (no moving scale)
  // instead of a fabricated 0 that reads as a live standstill.
  if (speedKph === null) {
    const boxW = 50, boxH = 20;
    ctx.fillStyle = "rgba(0,0,0,0.7)";
    ctx.fillRect(x - boxW - 4, cy - boxH / 2, boxW, boxH);
    ctx.strokeStyle = HUD_INK;
    ctx.lineWidth = 1;
    ctx.strokeRect(x - boxW - 4, cy - boxH / 2, boxW, boxH);
    setHudStyle(ctx, HUD_INK, 12, "center", "middle");
    ctx.fillText("—", x - boxW / 2 - 4, cy);
    clearShadow(ctx);
    return;
  }

  const tapeH = h * 0.4;
  const tapeW = 50;
  const pxPerUnit = tapeH / 60;
  const top = cy - tapeH / 2;

  ctx.save();
  ctx.beginPath();
  ctx.rect(x - tapeW, top, tapeW + 10, tapeH);
  ctx.clip();

  ctx.lineWidth = 1;
  ctx.strokeStyle = HUD_INK;
  ctx.fillStyle = HUD_INK;
  ctx.shadowColor = SHADOW;
  ctx.shadowBlur = 1;
  ctx.shadowOffsetX = 1;
  ctx.shadowOffsetY = 1;

  ctx.beginPath();
  ctx.moveTo(x, top); ctx.lineTo(x, top + tapeH);
  ctx.stroke();

  ctx.font = `10px ${FONT}`;
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";

  const startVal = Math.floor(speedKph / 5) * 5 - 30;
  const endVal = startVal + 60;

  for (let val = startVal; val <= endVal; val += 5) {
    if (val < 0) continue;
    const yPos = cy - (val - speedKph) * pxPerUnit;
    const tickLen = val % 10 === 0 ? 12 : 6;
    ctx.beginPath();
    ctx.moveTo(x, yPos); ctx.lineTo(x - tickLen, yPos);
    ctx.stroke();
    if (val % 10 === 0) ctx.fillText(String(val), x - tickLen - 4, yPos);
  }

  clearShadow(ctx);
  ctx.restore();

  const boxW = 50;
  const boxH = 20;
  ctx.fillStyle = "rgba(0,0,0,0.7)";
  ctx.fillRect(x - boxW - 4, cy - boxH / 2, boxW, boxH);
  ctx.strokeStyle = HUD_INK;
  ctx.lineWidth = 1;
  ctx.strokeRect(x - boxW - 4, cy - boxH / 2, boxW, boxH);
  setHudStyle(ctx, HUD_INK, 12, "center", "middle");
  ctx.fillText(String(Math.round(speedKph)), x - boxW / 2 - 4, cy);
  clearShadow(ctx);
}

export function drawAltTape(
  ctx: CanvasRenderingContext2D,
  x: number, cy: number,
  alt: number | null, h: number
) {
  // Absent / stale altitude: draw just the readout box with "—" (no moving
  // scale) instead of a fabricated 0.0 that reads as a live ground level.
  if (alt === null) {
    const boxW = 50, boxH = 20;
    ctx.fillStyle = "rgba(0,0,0,0.7)";
    ctx.fillRect(x + 4, cy - boxH / 2, boxW, boxH);
    ctx.strokeStyle = HUD_INK;
    ctx.lineWidth = 1;
    ctx.strokeRect(x + 4, cy - boxH / 2, boxW, boxH);
    setHudStyle(ctx, HUD_INK, 12, "center", "middle");
    ctx.fillText("—", x + boxW / 2 + 4, cy);
    clearShadow(ctx);
    return;
  }

  const tapeH = h * 0.4;
  const tapeW = 50;
  const pxPerUnit = tapeH / 100;
  const top = cy - tapeH / 2;

  ctx.save();
  ctx.beginPath();
  ctx.rect(x - 10, top, tapeW + 10, tapeH);
  ctx.clip();

  ctx.lineWidth = 1;
  ctx.strokeStyle = HUD_INK;
  ctx.fillStyle = HUD_INK;
  ctx.shadowColor = SHADOW;
  ctx.shadowBlur = 1;
  ctx.shadowOffsetX = 1;
  ctx.shadowOffsetY = 1;

  ctx.beginPath();
  ctx.moveTo(x, top); ctx.lineTo(x, top + tapeH);
  ctx.stroke();

  ctx.font = `10px ${FONT}`;
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";

  const startVal = Math.floor(alt / 10) * 10 - 50;
  const endVal = startVal + 100;

  for (let val = startVal; val <= endVal; val += 5) {
    if (val < 0) continue;
    const yPos = cy - (val - alt) * pxPerUnit;
    const tickLen = val % 10 === 0 ? 12 : 6;
    ctx.beginPath();
    ctx.moveTo(x, yPos); ctx.lineTo(x + tickLen, yPos);
    ctx.stroke();
    if (val % 10 === 0) ctx.fillText(String(val), x + tickLen + 4, yPos);
  }

  clearShadow(ctx);
  ctx.restore();

  const boxW = 50;
  const boxH = 20;
  ctx.fillStyle = "rgba(0,0,0,0.7)";
  ctx.fillRect(x + 4, cy - boxH / 2, boxW, boxH);
  ctx.strokeStyle = HUD_INK;
  ctx.lineWidth = 1;
  ctx.strokeRect(x + 4, cy - boxH / 2, boxW, boxH);
  setHudStyle(ctx, HUD_INK, 12, "center", "middle");
  ctx.fillText(alt.toFixed(1), x + boxW / 2 + 4, cy);
  clearShadow(ctx);
}

export function drawHeadingCompass(
  ctx: CanvasRenderingContext2D,
  cx: number, y: number,
  heading: number | null, w: number
) {
  const stripH = 20;

  // Absent / stale heading: draw just the readout box with "—" (no strip)
  // instead of a fabricated 000° that reads as a live north lock.
  if (heading === null) {
    const boxW = 44, boxH = 18;
    ctx.fillStyle = "rgba(0,0,0,0.7)";
    ctx.fillRect(cx - boxW / 2, y + stripH + 2, boxW, boxH);
    ctx.strokeStyle = HUD_INK;
    ctx.lineWidth = 1;
    ctx.strokeRect(cx - boxW / 2, y + stripH + 2, boxW, boxH);
    setHudStyle(ctx, HUD_INK, 11, "center", "middle");
    ctx.fillText("—", cx, y + stripH + 2 + boxH / 2);
    clearShadow(ctx);
    return;
  }

  const stripW = Math.min(w * 0.4, 300);
  const left = cx - stripW / 2;
  const pxPerDeg = stripW / 60;
  const cardinals: Record<number, string> = { 0: "N", 90: "E", 180: "S", 270: "W" };

  ctx.save();
  ctx.beginPath();
  ctx.rect(left, y, stripW, stripH + 4);
  ctx.clip();

  ctx.lineWidth = 1;
  ctx.strokeStyle = HUD_INK;
  ctx.fillStyle = HUD_INK;
  ctx.shadowColor = SHADOW;
  ctx.shadowBlur = 1;
  ctx.shadowOffsetX = 1;
  ctx.shadowOffsetY = 1;

  ctx.beginPath();
  ctx.moveTo(left, y + stripH); ctx.lineTo(left + stripW, y + stripH);
  ctx.stroke();

  ctx.font = `10px ${FONT}`;
  ctx.textAlign = "center";
  ctx.textBaseline = "bottom";

  for (let offset = -35; offset <= 35; offset++) {
    const deg = normalizeHeading(heading + offset);
    const xPos = cx + offset * pxPerDeg;
    if (deg % 10 === 0) {
      const tickLen = deg % 30 === 0 ? 10 : 5;
      ctx.beginPath();
      ctx.moveTo(xPos, y + stripH); ctx.lineTo(xPos, y + stripH - tickLen);
      ctx.stroke();
    }
    const cardinal = cardinals[deg];
    if (cardinal) {
      ctx.font = `bold 11px ${FONT}`;
      ctx.fillText(cardinal, xPos, y + stripH - 10);
      ctx.font = `10px ${FONT}`;
    } else if (deg % 30 === 0) {
      ctx.fillText(String(deg), xPos, y + stripH - 10);
    }
  }

  clearShadow(ctx);
  ctx.restore();

  const boxW = 44;
  const boxH = 18;
  ctx.fillStyle = "rgba(0,0,0,0.7)";
  ctx.fillRect(cx - boxW / 2, y + stripH + 2, boxW, boxH);
  ctx.strokeStyle = HUD_INK;
  ctx.lineWidth = 1;
  ctx.strokeRect(cx - boxW / 2, y + stripH + 2, boxW, boxH);
  setHudStyle(ctx, HUD_INK, 11, "center", "middle");
  ctx.fillText(
    String(Math.round(normalizeHeading(heading))).padStart(3, "0") + "\u00B0",
    cx, y + stripH + 2 + boxH / 2
  );
  clearShadow(ctx);

  ctx.fillStyle = HUD_INK;
  ctx.shadowColor = SHADOW;
  ctx.shadowBlur = 1;
  ctx.beginPath();
  ctx.moveTo(cx, y + stripH);
  ctx.lineTo(cx - 4, y + stripH + 3);
  ctx.lineTo(cx + 4, y + stripH + 3);
  ctx.closePath();
  ctx.fill();
  clearShadow(ctx);
}
