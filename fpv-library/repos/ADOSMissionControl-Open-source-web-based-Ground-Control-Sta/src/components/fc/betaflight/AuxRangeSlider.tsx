"use client";

import { cn } from "@/lib/utils";

/** Convert step to PWM: PWM = 900 + step * 25 */
export function stepToPwm(step: number): number {
  return 900 + step * 25;
}

/** Convert PWM to step: step = (PWM - 900) / 25 */
export function pwmToStep(pwm: number): number {
  return Math.round((pwm - 900) / 25);
}

export function AuxRangeSlider({
  start,
  end,
  onChange,
  activePwm,
}: {
  start: number; // step value 0-48
  end: number;
  onChange: (start: number, end: number) => void;
  activePwm: number; // live channel PWM for indicator
}) {
  const totalSteps = 48; // 900-2100 in steps of 25
  const startPct = (start / totalSteps) * 100;
  const endPct = (end / totalSteps) * 100;
  const activePct =
    activePwm > 0 ? (pwmToStep(Math.min(2100, Math.max(900, activePwm))) / totalSteps) * 100 : -1;
  const isInRange =
    activePwm > 0 &&
    activePwm >= stepToPwm(start) &&
    activePwm <= stepToPwm(end);

  return (
    <div className="relative h-6 select-none">
      {/* Track background */}
      <div className="absolute top-2 left-0 right-0 h-2 bg-bg-tertiary rounded-full" />

      {/* Active range highlight */}
      <div
        className={`absolute top-2 h-2 rounded-full transition-colors ${
          isInRange ? "bg-status-success/60" : "bg-accent-primary/40"
        }`}
        style={{
          left: `${startPct}%`,
          width: `${endPct - startPct}%`,
        }}
      />

      {/* Live channel indicator */}
      {activePct >= 0 && (
        <div
          className={`absolute top-1 w-0.5 h-4 rounded-full ${
            isInRange ? "bg-status-success" : "bg-text-tertiary"
          }`}
          style={{ left: `${activePct}%` }}
        />
      )}

      {/* Start thumb */}
      <input
        type="range"
        min={0}
        max={totalSteps}
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
        max={totalSteps}
        value={end}
        onChange={(e) => {
          const v = Number(e.target.value);
          if (v > start) onChange(start, v);
        }}
        className="absolute inset-0 w-full opacity-0 cursor-pointer z-10"
        style={{ pointerEvents: "auto" }}
      />

      {/* PWM labels */}
      <div className="absolute -bottom-3 left-0 right-0 flex justify-between text-[8px] text-text-tertiary font-mono">
        <span>900</span>
        <span>1500</span>
        <span>2100</span>
      </div>
    </div>
  );
}

export function AuxCard({
  icon,
  title,
  description,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-border-default bg-bg-secondary p-4 space-y-3">
      <div className="flex items-center gap-2 mb-1">
        <span className={cn("text-accent-primary")}>{icon}</span>
        <div>
          <h2 className="text-sm font-medium text-text-primary">{title}</h2>
          <p className="text-[10px] text-text-tertiary">{description}</p>
        </div>
      </div>
      {children}
    </div>
  );
}
