"use client";

import { useMemo } from "react";

export function calcBetaflightRate(
  rcRate: number,
  expo: number,
  superRate: number,
  rcCommand: number,
): number {
  const rcRate_ = rcRate / 100;
  const expo_ = expo / 100;
  const superRate_ = superRate / 100;

  const absRc = Math.abs(rcCommand);
  const expoPower = absRc * absRc * absRc * expo_ + absRc * (1 - expo_);
  let angleRate = 200.0 * rcRate_ * expoPower;

  if (superRate_ > 0) {
    const rcFactor = 1.0 / (1.0 - absRc * superRate_);
    angleRate *= rcFactor;
  }

  return angleRate * Math.sign(rcCommand);
}

const CURVE_W = 280;
const CURVE_H = 160;
const CURVE_PAD = 28;

export interface CurveData {
  label: string;
  color: string;
  rcRate: number;
  expo: number;
  superRate: number;
}

export function RateCurvePreview({ curves }: { curves: CurveData[] }) {
  const maxRate = useMemo(() => {
    let max = 0;
    for (const c of curves) {
      const r = Math.abs(calcBetaflightRate(c.rcRate, c.expo, c.superRate, 1.0));
      if (r > max) max = r;
    }
    return Math.max(max, 100);
  }, [curves]);

  const plotW = CURVE_W - CURVE_PAD * 2;
  const plotH = CURVE_H - CURVE_PAD * 2;

  return (
    <div className="border border-border-default bg-bg-tertiary/30 p-2">
      <svg width={CURVE_W} height={CURVE_H} className="block">
        <line x1={CURVE_PAD} y1={CURVE_H - CURVE_PAD} x2={CURVE_W - CURVE_PAD} y2={CURVE_H - CURVE_PAD} stroke="var(--color-border-default)" strokeWidth={1} />
        <line x1={CURVE_PAD} y1={CURVE_PAD} x2={CURVE_PAD} y2={CURVE_H - CURVE_PAD} stroke="var(--color-border-default)" strokeWidth={1} />
        <text x={CURVE_W / 2} y={CURVE_H - 4} textAnchor="middle" className="text-[8px] fill-text-tertiary">Stick %</text>
        <text x={8} y={CURVE_H / 2} textAnchor="middle" className="text-[8px] fill-text-tertiary" transform={`rotate(-90, 8, ${CURVE_H / 2})`}>deg/s</text>
        {[0.25, 0.5, 0.75].map((frac) => (
          <line key={`h-${frac}`} x1={CURVE_PAD} y1={CURVE_H - CURVE_PAD - plotH * frac} x2={CURVE_W - CURVE_PAD} y2={CURVE_H - CURVE_PAD - plotH * frac} stroke="var(--color-border-default)" strokeWidth={0.5} strokeDasharray="2,3" />
        ))}
        {[0.25, 0.5, 0.75].map((frac) => (
          <line key={`v-${frac}`} x1={CURVE_PAD + plotW * frac} y1={CURVE_PAD} x2={CURVE_PAD + plotW * frac} y2={CURVE_H - CURVE_PAD} stroke="var(--color-border-default)" strokeWidth={0.5} strokeDasharray="2,3" />
        ))}
        {[0, 0.5, 1].map((frac) => (
          <text key={`yt-${frac}`} x={CURVE_PAD - 3} y={CURVE_H - CURVE_PAD - plotH * frac + 3} textAnchor="end" className="text-[7px] fill-text-tertiary font-mono">{Math.round(maxRate * frac)}</text>
        ))}
        {[0, 50, 100].map((pct) => (
          <text key={`xt-${pct}`} x={CURVE_PAD + plotW * (pct / 100)} y={CURVE_H - CURVE_PAD + 12} textAnchor="middle" className="text-[7px] fill-text-tertiary font-mono">{pct}</text>
        ))}
        {curves.map((c) => {
          const points: string[] = [];
          const steps = 50;
          for (let i = 0; i <= steps; i++) {
            const rc = i / steps;
            const rate = Math.abs(calcBetaflightRate(c.rcRate, c.expo, c.superRate, rc));
            const x = CURVE_PAD + (rc * plotW);
            const y = CURVE_H - CURVE_PAD - (rate / maxRate) * plotH;
            points.push(`${x},${y}`);
          }
          return <polyline key={c.label} points={points.join(" ")} fill="none" stroke={c.color} strokeWidth={1.5} />;
        })}
      </svg>
      <div className="flex gap-3 mt-1 px-1">
        {curves.map((c) => {
          const maxDeg = Math.abs(calcBetaflightRate(c.rcRate, c.expo, c.superRate, 1.0));
          return (
            <div key={c.label} className="flex items-center gap-1">
              <div className="w-2 h-0.5" style={{ backgroundColor: c.color }} />
              <span className="text-[9px] text-text-secondary">{c.label}: {Math.round(maxDeg)} deg/s</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
