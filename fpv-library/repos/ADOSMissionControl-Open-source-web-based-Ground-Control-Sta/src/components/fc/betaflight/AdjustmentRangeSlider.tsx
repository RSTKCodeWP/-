"use client";

import { cn } from "@/lib/utils";

/** Step-to-PWM conversion (Betaflight convention: PWM = 900 + step * 25) */
export function stepToPwm(step: number): number {
  return 900 + step * 25;
}

export function pwmToStep(pwm: number): number {
  return Math.round((pwm - 900) / 25);
}

export const TOTAL_STEPS = 48; // 900-2100 in steps of 25

export function AdjustmentRangeSlider({
  start,
  end,
  activePwm,
  onChange,
  dirty,
}: {
  start: number; // step value 0-48
  end: number;
  activePwm: number;
  onChange: (start: number, end: number) => void;
  dirty: boolean;
}) {
  const startPct = (start / TOTAL_STEPS) * 100;
  const endPct = (end / TOTAL_STEPS) * 100;
  const activePct =
    activePwm > 0
      ? (pwmToStep(Math.min(2100, Math.max(900, activePwm))) / TOTAL_STEPS) * 100
      : -1;
  const isInRange =
    activePwm > 0 &&
    activePwm >= stepToPwm(start) &&
    activePwm <= stepToPwm(end);

  return (
    <div className="relative h-8 select-none">
      {/* Track background */}
      <div className="absolute top-3 left-0 right-0 h-2 bg-bg-tertiary rounded-full" />

      {/* Active range highlight */}
      <div
        className={cn(
          "absolute top-3 h-2 rounded-full transition-colors",
          dirty
            ? "bg-status-warning/50"
            : isInRange
              ? "bg-status-success/60"
              : "bg-accent-primary/40",
        )}
        style={{
          left: `${startPct}%`,
          width: `${Math.max(0, endPct - startPct)}%`,
        }}
      />

      {/* Live channel indicator */}
      {activePct >= 0 && (
        <div
          className={cn(
            "absolute top-1.5 w-0.5 h-5 rounded-full",
            isInRange ? "bg-status-success" : "bg-text-tertiary",
          )}
          style={{ left: `${activePct}%` }}
        />
      )}

      {/* Start thumb */}
      <input
        type="range"
        min={0}
        max={TOTAL_STEPS}
        value={start}
        onChange={(e) => {
          const v = Number(e.target.value);
          if (v < end) onChange(v, end);
        }}
        className="absolute inset-0 w-full opacity-0 cursor-pointer z-10"
        style={{ pointerEvents: "auto" }}
      />

      {/* End thumb */}
      <input
        type="range"
        min={0}
        max={TOTAL_STEPS}
        value={end}
        onChange={(e) => {
          const v = Number(e.target.value);
          if (v > start) onChange(start, v);
        }}
        className="absolute inset-0 w-full opacity-0 cursor-pointer z-10"
        style={{ pointerEvents: "auto" }}
      />

      {/* PWM labels */}
      <div className="absolute -bottom-1 left-0 right-0 flex justify-between text-[8px] text-text-tertiary font-mono">
        <span>900</span>
        <span>1500</span>
        <span>2100</span>
      </div>
    </div>
  );
}
