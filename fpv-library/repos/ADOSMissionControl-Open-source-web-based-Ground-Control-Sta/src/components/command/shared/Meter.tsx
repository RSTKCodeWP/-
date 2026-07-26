"use client";

/**
 * A labelled progress meter with status-token fill. Consolidates the several
 * hand-rolled bars (resource bars, battery bar, data-cap) onto one primitive
 * that speaks the shared status vocabulary. Accepts a 0..1 fraction or a
 * 0..100 percent.
 *
 * @module Meter
 * @license GPL-3.0-only
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { StatusLevel } from "@/components/ui/status-dot";

const levelBar: Record<StatusLevel, string> = {
  good: "bg-status-success",
  warning: "bg-status-warning",
  serious: "bg-status-serious",
  critical: "bg-status-error",
  idle: "bg-accent-primary",
  offline: "bg-text-tertiary",
};

export function Meter({
  label,
  value,
  level = "good",
  caption,
  className,
}: {
  label?: ReactNode;
  value: number;
  level?: StatusLevel;
  caption?: ReactNode;
  className?: string;
}) {
  const pct = Math.max(0, Math.min(100, value <= 1 ? value * 100 : value));
  return (
    <div className={cn("space-y-1", className)}>
      {(label || caption) && (
        <div className="flex items-center justify-between text-[11px] text-text-secondary">
          <span className="truncate">{label}</span>
          <span className="font-mono tabular-nums">{caption}</span>
        </div>
      )}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg-tertiary">
        <div
          className={cn("h-full rounded-full transition-all", levelBar[level])}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
