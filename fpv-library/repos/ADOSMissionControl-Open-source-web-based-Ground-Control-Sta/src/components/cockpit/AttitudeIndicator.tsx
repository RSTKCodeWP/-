"use client";

/**
 * @module fly/cockpit/AttitudeIndicator
 * @description The cockpit HUD — a faithful port of the reference artifact's
 * `.hud` SVG (bank arc + sky pointer + pitch marks + boresight crosshair) with
 * the exact strokes and the artifact's blue glow (from `.ados-cockpit .hud svg`
 * in globals.css). The boresight + bank arc are the fixed reticle (always
 * shown); the pitch marks track live attitude (rotate by roll, translate by
 * pitch) and only render when the attitude sample is fresh (Rule 44 — no
 * fabricated level indication when there is no attitude).
 * @license GPL-3.0-only
 */

import { useHudInstruments } from "@/hooks/use-hud-instruments";

const CX = 600;
const CY = 355;
const PX_PER_DEG = 6;

export function AttitudeIndicator() {
  const { pitch, roll } = useHudInstruments();
  const hasAtt = pitch !== null && roll !== null;
  const p = pitch ?? 0;
  const r = roll ?? 0;

  return (
    <div className="hud" aria-hidden="true">
      <svg viewBox="0 0 1200 700" preserveAspectRatio="xMidYMid slice">
        {/* bank arc + sky pointer (fixed roll scale) */}
        <g stroke="var(--hud)" strokeWidth={1.4} fill="none" opacity={0.85}>
          <path d="M600 250 A170 170 0 0 1 770 420" opacity={0.5} />
          <path d="M600 250 A170 170 0 0 0 430 420" opacity={0.5} />
          <polyline points="600,80 592,96 608,96" fill="var(--hud)" stroke="none" />
        </g>

        {/* pitch marks — earth-referenced, only when attitude is live */}
        {hasAtt && (
          <g transform={`rotate(${-r} ${CX} ${CY}) translate(0 ${p * PX_PER_DEG})`}>
            <g stroke="var(--hud)" strokeWidth={1.3} opacity={0.75}>
              <line x1="520" y1="300" x2="560" y2="300" />
              <line x1="640" y1="300" x2="680" y2="300" />
              <line x1="530" y1="410" x2="565" y2="410" />
              <line x1="635" y1="410" x2="670" y2="410" />
            </g>
            <g fill="var(--hud)" fontSize={12} opacity={0.7}>
              <text x="492" y="304">
                10
              </text>
              <text x="500" y="414">
                -10
              </text>
            </g>
          </g>
        )}

        {/* boresight / waterline (fixed) */}
        <g stroke="var(--hud)" strokeWidth={2} fill="none">
          <circle cx={CX} cy={CY} r={5} fill="var(--hud)" stroke="none" />
          <line x1="560" y1={CY} x2="586" y2={CY} />
          <line x1="614" y1={CY} x2="640" y2={CY} />
          <line x1={CX} y1="325" x2={CX} y2="341" />
        </g>
      </svg>
    </div>
  );
}
