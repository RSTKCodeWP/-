"use client";

/**
 * A radial utilisation gauge (SVG ring) with status-token stroke, for GPU/NPU
 * utilisation and other 0..1 saturations. Accepts a 0..1 fraction or a 0..100
 * percent.
 *
 * @module Gauge
 * @license GPL-3.0-only
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { StatusLevel } from "@/components/ui/status-dot";

const levelStroke: Record<StatusLevel, string> = {
  good: "stroke-status-success",
  warning: "stroke-status-warning",
  serious: "stroke-status-serious",
  critical: "stroke-status-error",
  idle: "stroke-accent-primary",
  offline: "stroke-text-tertiary",
};

export function Gauge({
  value,
  label,
  caption,
  level = "good",
  size = 64,
  className,
}: {
  value: number;
  label?: ReactNode;
  caption?: ReactNode;
  level?: StatusLevel;
  size?: number;
  className?: string;
}) {
  const pct = Math.max(0, Math.min(1, value <= 1 ? value : value / 100));
  const r = size / 2 - 6;
  const c = 2 * Math.PI * r;
  return (
    <div className={cn("flex flex-col items-center gap-1", className)}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          className="fill-none stroke-bg-tertiary"
          strokeWidth={5}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          className={cn("fill-none transition-all", levelStroke[level])}
          strokeWidth={5}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
        />
      </svg>
      {(label || caption) && (
        <div className="text-center text-[10px] text-text-tertiary">
          {label}
          {caption && (
            <div className="font-mono text-xs text-text-primary">{caption}</div>
          )}
        </div>
      )}
    </div>
  );
}
