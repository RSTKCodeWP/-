"use client";

import { cn } from "@/lib/utils";

interface BatteryBarProps {
  percentage: number;
  className?: string;
  showLabel?: boolean;
}

export function BatteryBar({ percentage, className, showLabel = true }: BatteryBarProps) {
  const clamped = Math.max(0, Math.min(100, percentage));
  const color =
    clamped > 50 ? "bg-status-success" : clamped > 25 ? "bg-status-warning" : "bg-status-error";

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="flex-1 h-2 bg-bg-tertiary border border-border-default">
        <div className={cn("h-full transition-all duration-500", color)} style={{ width: `${clamped}%` }} />
      </div>
      {showLabel && (
        <span className="text-[10px] font-mono text-text-secondary tabular-nums w-8 text-right">
          {Math.round(clamped)}%
        </span>
      )}
    </div>
  );
}
