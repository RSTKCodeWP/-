/**
 * @module NavStatePill
 * @description Compact pill showing the iNav navigation state and active action.
 * Renders only when the selected drone firmware is iNav and nav state data is available.
 * @license GPL-3.0-only
 */
"use client";

import { useTelemetryStore } from "@/stores/telemetry-store";
import { useDroneManager } from "@/stores/drone-manager";
import { Tooltip } from "@/components/ui/tooltip";

// ── Nav state label map ──────────────────────────────────────

const NAV_STATE_LABELS: Record<number, string> = {
  0:  "IDLE",
  1:  "ALT_HOLD_INITIALIZE",
  2:  "ALT_HOLD_IN_PROGRESS",
  3:  "POSHOLD_3D_INITIALIZE",
  4:  "POSHOLD_3D_IN_PROGRESS",
  5:  "COURSE_HOLD_INITIALIZE",
  6:  "COURSE_HOLD_IN_PROGRESS",
  7:  "COURSE_HOLD_ADJUSTING",
  8:  "CRUISE_INITIALIZE",
  9:  "CRUISE_IN_PROGRESS",
  10: "CRUISE_ADJUSTING",
  11: "RTH_INITIALIZE",
  12: "RTH_CLIMB_TO_SAFE_ALT",
  13: "RTH_HEAD_HOME",
  14: "RTH_HOVER_PRIOR_TO_LANDING",
  15: "RTH_HOVER_ABOVE_HOME",
  16: "RTH_LANDING",
  17: "RTH_FINISHING",
  18: "RTH_FINISHED",
  19: "WAYPOINT_INITIALIZE",
  20: "WAYPOINT_PRE_ACTION",
  21: "WAYPOINT_IN_PROGRESS",
  22: "WAYPOINT_REACHED",
  23: "WAYPOINT_NEXT",
  24: "WAYPOINT_FINISHED",
  25: "WAYPOINT_RTH_LAND",
  26: "EMERGENCY_LANDING_INITIALIZE",
  27: "EMERGENCY_LANDING_IN_PROGRESS",
  28: "EMERGENCY_LANDING_FINISHED",
  29: "LAUNCH_INITIALIZE",
  30: "LAUNCH_WAIT",
  31: "LAUNCH_IN_PROGRESS",
  32: "LANDING_INITIALIZE",
  33: "LANDING_IN_PROGRESS",
  34: "LANDING_FINISHED",
};

const NAV_ACTION_LABELS: Record<number, string> = {
  0: "NONE",
  1: "WAYPOINT",
  2: "HOLD_POS",
  3: "HOLD_HEADING",
  4: "RTH",
  5: "WAYPOINT_NEXT",
  6: "CLIMB_ABOVE_HOME",
};

function navStateLabel(state: number): string {
  return NAV_STATE_LABELS[state] ?? `State ${state}`;
}

function navActionLabel(action: number): string {
  return NAV_ACTION_LABELS[action] ?? `Action ${action}`;
}

// ── Component ────────────────────────────────────────────────

export function NavStatePill() {
  const getProtocol = useDroneManager((s) => s.getSelectedProtocol);
  const protocol = getProtocol();
  const firmwareType = protocol?.getVehicleInfo()?.firmwareType;

  const navState = useTelemetryStore((s) => s.navState);
  const navAction = useTelemetryStore((s) => s.navAction);

  if (firmwareType !== "inav" || navState === null) return null;

  const isActive = navState > 0;
  const showAction = navAction !== null && navAction > 0;

  const stateLabel = navStateLabel(navState);
  const actionLabel = navAction !== null ? navActionLabel(navAction) : "";

  const tooltipText = showAction
    ? `Nav state: ${stateLabel}, Nav action: ${actionLabel}`
    : `Nav state: ${stateLabel}`;

  return (
    <Tooltip content={tooltipText}>
      <div
        role="status"
        aria-label={`iNav navigation state: ${tooltipText}`}
        className={
        "flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono border " +
        (isActive
          ? "bg-accent-primary/10 border-accent-primary/30 text-accent-primary"
          : "bg-bg-tertiary border-border-default text-text-secondary")
      }>
        <span>{stateLabel}</span>
        {showAction && (
          <>
            <span className="text-text-tertiary">/</span>
            <span>{actionLabel}</span>
          </>
        )}
      </div>
    </Tooltip>
  );
}
