"use client";

import { cn } from "@/lib/utils";

interface TelemetryBlockProps {
  label: string;
  value: string | number;
  unit?: string;
  warning?: boolean;
  critical?: boolean;
  className?: string;
}

export function TelemetryBlock({ label, value, unit, warning, critical, className }: TelemetryBlockProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-0.5 px-2 py-1.5 border-l-2",
        critical
          ? "border-l-status-error bg-status-error/5"
          : warning
            ? "border-l-status-warning bg-status-warning/5"
            : "border-l-border-default",
        className
      )}
    >
      <span className="text-[10px] uppercase tracking-wider text-text-tertiary">{label}</span>
      <div className="flex items-baseline gap-0.5">
        <span
          className={cn(
            "text-base font-mono font-semibold tabular-nums",
            critical ? "text-status-error" : warning ? "text-status-warning" : "text-text-primary"
          )}
        >
          {value}
        </span>
        {unit && <span className="text-[10px] text-text-tertiary font-mono">{unit}</span>}
      </div>
    </div>
  );
}
