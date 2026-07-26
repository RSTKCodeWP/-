"use client";

import { SlidersHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";
import { ParamStar } from "../parameters/ParamStar";
import type { AxisConfig } from "./pid-constants";

export function PidAxisRow({
  axis,
  params,
  dirtyParams,
  setLocalValue,
  mapParamName = (s) => s,
}: {
  axis: AxisConfig;
  params: Map<string, number>;
  dirtyParams: Set<string>;
  setLocalValue: (name: string, value: number) => void;
  mapParamName?: (s: string) => string;
}) {
  return (
    <div className="border border-border-default bg-bg-secondary p-4">
      <div className="flex items-center gap-2 mb-3">
        <SlidersHorizontal size={14} className="text-accent-primary" />
        <h2 className="text-sm font-medium text-text-primary">{axis.axis}</h2>
      </div>

      <div className="space-y-3">
        {axis.params.map((pidP) => {
          const value = params.get(pidP.param) ?? 0;
          const isDirty = dirtyParams.has(pidP.param);
          return (
            <div key={pidP.param} className="grid grid-cols-[100px_1fr_80px_auto] items-center gap-3">
              <div>
                <span className="text-xs font-mono text-text-secondary">{pidP.label}</span>
                <span className="text-[9px] text-text-tertiary block">{mapParamName(pidP.param)}</span>
              </div>

              {/* Slider */}
              <div className="relative">
                <input
                  type="range"
                  min={pidP.min}
                  max={pidP.max}
                  step={pidP.step}
                  value={value}
                  onChange={(e) => setLocalValue(pidP.param, parseFloat(e.target.value))}
                  className="w-full h-1.5 bg-bg-tertiary appearance-none cursor-pointer accent-accent-primary [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-accent-primary [&::-webkit-slider-thumb]:cursor-pointer"
                />
                {/* Marks */}
                <div className="flex justify-between text-[8px] text-text-tertiary font-mono mt-0.5">
                  <span>{pidP.min}</span>
                  <span>{pidP.max}</span>
                </div>
              </div>

              {/* Numeric input */}
              <input
                type="number"
                min={pidP.min}
                max={pidP.max}
                step={pidP.step}
                value={value}
                onChange={(e) => setLocalValue(pidP.param, parseFloat(e.target.value) || 0)}
                className={cn(
                  "w-full h-7 px-1.5 bg-bg-tertiary border text-xs font-mono text-text-primary text-right",
                  "focus:outline-none focus:border-accent-primary transition-colors",
                  isDirty ? "border-status-warning" : "border-border-default",
                )}
              />
              <ParamStar name={pidP.param} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
