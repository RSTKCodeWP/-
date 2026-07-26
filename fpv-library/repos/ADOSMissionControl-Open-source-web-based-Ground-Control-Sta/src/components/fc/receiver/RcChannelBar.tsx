"use client";

import { cn } from "@/lib/utils";

interface RcChannelBarProps {
  index: number;
  value: number;
  min: number;
  max: number;
  trim: number;
  dz: number;
}

export function RcChannelBar({ index, value, min, max, trim, dz }: RcChannelBarProps) {
  const range = max - min || 1;
  const pct = Math.max(0, Math.min(100, ((value - min) / range) * 100));
  const trimPct = ((trim - min) / range) * 100;
  const dzPct = (dz / range) * 100;
  const dzLeft = Math.max(0, trimPct - dzPct);
  const dzWidth = Math.min(100, dzPct * 2);

  return (
    <div className="flex items-center gap-2">
      <span className={cn(
        "text-[10px] font-mono w-6 text-right shrink-0",
        value === 0 ? "text-text-secondary" :
        Math.abs(value - trim) > dz ? "text-status-error" : "text-status-success"
      )}>
        CH{index + 1}
      </span>
      <div className="flex-1 h-4 bg-bg-tertiary border border-border-default relative overflow-hidden">
        {/* Deadzone band around trim */}
        {dz > 0 && (
          <div
            className="absolute top-0 bottom-0 bg-accent-primary/10 border-l border-r border-accent-primary/20"
            style={{ left: `${dzLeft}%`, width: `${dzWidth}%` }}
          />
        )}
        <div
          className="h-full bg-status-success/60 transition-all duration-75"
          style={{ width: `${pct}%` }}
        />
        {/* Trim mark */}
        <div
          className="absolute top-0 bottom-0 w-px bg-accent-primary/50"
          style={{ left: `${trimPct}%` }}
        />
      </div>
      <span className="text-[10px] font-mono text-text-primary tabular-nums w-10 text-right shrink-0">
        {value}
      </span>
    </div>
  );
}
