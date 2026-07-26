/**
 * @module BasemapSwitcher
 * @description Shared segmented basemap/imagery selector used by both the Plan
 * (Leaflet) and Simulate (Cesium) map views so the control reads the same in
 * both tabs. Presentational only — the caller owns the option set and the
 * persisted value, since the two engines expose different basemap catalogs.
 * @license GPL-3.0-only
 */
"use client";

import { cn } from "@/lib/utils";

export interface BasemapOption {
  value: string;
  label: string;
}

interface BasemapSwitcherProps {
  options: BasemapOption[];
  value: string;
  onChange: (value: string) => void;
  /** Stretch each segment to equal width to fill the container. */
  stretch?: boolean;
  className?: string;
}

export function BasemapSwitcher({
  options,
  value,
  onChange,
  stretch,
  className,
}: BasemapSwitcherProps) {
  return (
    <div className={cn("flex gap-1", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          aria-pressed={o.value === value}
          className={cn(
            "h-7 px-2 rounded text-[10px] font-mono font-bold transition-colors cursor-pointer",
            stretch && "flex-1",
            o.value === value
              ? "bg-accent-primary text-bg-primary"
              : "text-text-secondary hover:text-text-primary border border-border-default",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
