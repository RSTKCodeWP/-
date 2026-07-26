"use client";

import { cn } from "@/lib/utils";

interface DataValueProps {
  label: string;
  value: string | number;
  unit?: string;
  className?: string;
}

export function DataValue({ label, value, unit, className }: DataValueProps) {
  return (
    <div className={cn("flex flex-col gap-0.5", className)}>
      <span className="text-[11px] text-text-secondary leading-none">{label}</span>
      <div className="flex items-baseline gap-1">
        <span className="text-lg font-mono font-semibold text-text-primary leading-none tabular-nums">
          {value}
        </span>
        {unit && <span className="text-[10px] text-text-tertiary font-mono">{unit}</span>}
      </div>
    </div>
  );
}
