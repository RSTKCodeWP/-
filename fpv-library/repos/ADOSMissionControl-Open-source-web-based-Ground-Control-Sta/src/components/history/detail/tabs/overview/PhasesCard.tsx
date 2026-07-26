"use client";

/**
 * Flight phase timeline card — stacked bar + detail list of auto-detected
 * phases (takeoff, climb, cruise, hover, descent, land).
 *
 * @module components/history/detail/tabs/overview/PhasesCard
 */

import { Activity } from "lucide-react";
import type { FlightPhase } from "@/lib/types";

const PHASE_LABELS: Record<FlightPhase["type"], string> = {
  pre_arm: "Pre-arm",
  takeoff: "Takeoff",
  climb: "Climb",
  cruise: "Cruise",
  hover: "Hover",
  descent: "Descent",
  land: "Land",
  post_disarm: "Post-disarm",
};

const PHASE_COLORS: Record<FlightPhase["type"], string> = {
  pre_arm: "#6b6b7f",
  takeoff: "#dff140",
  climb: "#3a82ff",
  cruise: "#22c55e",
  hover: "#a855f7",
  descent: "#f59e0b",
  land: "#ef4444",
  post_disarm: "#6b6b7f",
};

function fmtPhaseDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return m > 0 ? `${m}m${s.toString().padStart(2, "0")}` : `${s}s`;
}

export function PhasesCard({ phases }: { phases: FlightPhase[] }) {
  const totalDurationMs = phases.reduce((acc, p) => acc + (p.endMs - p.startMs), 0) || 1;
  return (
    <div className="flex flex-col gap-2">
      {/* Stacked bar showing relative phase durations */}
      <div className="flex h-2 w-full overflow-hidden rounded">
        {phases.map((p, i) => {
          const w = ((p.endMs - p.startMs) / totalDurationMs) * 100;
          if (w < 0.5) return null;
          return (
            <div
              key={`bar-${i}`}
              style={{ width: `${w}%`, backgroundColor: PHASE_COLORS[p.type] }}
              title={`${PHASE_LABELS[p.type]} · ${fmtPhaseDuration(p.endMs - p.startMs)}`}
            />
          );
        })}
      </div>

      {/* Detailed list */}
      <ul className="flex flex-col gap-0.5">
        {phases.map((p, i) => (
          <li
            key={`row-${i}`}
            className="flex items-center justify-between gap-2 text-[11px]"
          >
            <span className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-2 w-2 rounded-sm"
                style={{ backgroundColor: PHASE_COLORS[p.type] }}
              />
              <Activity size={10} className="text-text-tertiary" />
              <span className="text-text-primary">{PHASE_LABELS[p.type]}</span>
            </span>
            <span className="font-mono text-text-secondary">
              {fmtPhaseDuration(p.endMs - p.startMs)}
              {p.maxAlt !== undefined && (
                <span className="text-text-tertiary"> · {p.maxAlt}m</span>
              )}
              {p.avgSpeed !== undefined && p.avgSpeed > 0 && (
                <span className="text-text-tertiary"> · {p.avgSpeed}m/s</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
