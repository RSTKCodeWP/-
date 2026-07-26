/**
 * @module FenceBreachIndicator
 * @description Displays current geofence breach type with color-coded icons.
 * Reads breach status from the geofence store (fed by FENCE_STATUS MAVLink #162).
 * Shows: no breach (green), min altitude (yellow), max altitude (orange),
 * boundary (red), or combined (red pulsing).
 * @license GPL-3.0-only
 */

"use client";

import { useGeofenceStore } from "@/stores/geofence-store";
import { Shield, AlertTriangle, ArrowDown, ArrowUp, Square } from "lucide-react";

/**
 * FENCE_BREACH enum from MAVLink:
 * 0 = FENCE_BREACH_NONE
 * 1 = FENCE_BREACH_MINALT
 * 2 = FENCE_BREACH_MAXALT
 * 3 = FENCE_BREACH_BOUNDARY
 */
const BREACH_CONFIG: Record<number, { label: string; color: string; bgColor: string; Icon: typeof Shield }> = {
  0: { label: "No Breach", color: "text-status-success", bgColor: "bg-status-success/10", Icon: Shield },
  1: { label: "Min Altitude", color: "text-status-warning", bgColor: "bg-status-warning/10", Icon: ArrowDown },
  2: { label: "Max Altitude", color: "text-status-error", bgColor: "bg-status-error/10", Icon: ArrowUp },
  3: { label: "Boundary", color: "text-status-error", bgColor: "bg-status-error/10", Icon: Square },
};

export function FenceBreachIndicator() {
  const breachStatus = useGeofenceStore((s) => s.breachStatus);
  const breachType = useGeofenceStore((s) => s.breachType);
  const breachCount = useGeofenceStore((s) => s.breachCount);

  // No fence data or no breach
  if (breachStatus === 0) {
    return (
      <div className="flex items-center gap-2 px-2 py-1 bg-status-success/5 border border-border-default">
        <Shield size={12} className="text-status-success" />
        <span className="text-[10px] font-mono text-status-success">FENCE OK</span>
      </div>
    );
  }

  const config = BREACH_CONFIG[breachType] ?? BREACH_CONFIG[3];
  const { label, color, bgColor, Icon } = config;
  const isPulsing = breachStatus > 0;

  return (
    <div className={`flex items-center gap-2 px-2 py-1.5 border border-border-default ${bgColor}`}>
      <span className={`flex items-center gap-1.5 ${isPulsing ? "animate-pulse" : ""}`}>
        <AlertTriangle size={12} className={color} />
        <Icon size={10} className={color} />
      </span>
      <div className="flex flex-col">
        <span className={`text-[10px] font-mono font-semibold ${color}`}>
          BREACH: {label.toUpperCase()}
        </span>
        <span className="text-[9px] font-mono text-text-tertiary">
          Count: {breachCount}
        </span>
      </div>
    </div>
  );
}
