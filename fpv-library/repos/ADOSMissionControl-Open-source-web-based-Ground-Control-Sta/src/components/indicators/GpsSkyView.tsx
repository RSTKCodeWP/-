"use client";

import { useTelemetryStore } from "@/stores/telemetry-store";
import { cn } from "@/lib/utils";
import { Satellite } from "lucide-react";
import type { GpsData } from "@/lib/types";

const FIX_TYPES: Record<number, { label: string; color: string }> = {
  0: { label: "No GPS", color: "text-text-tertiary" },
  1: { label: "No Fix", color: "text-status-error" },
  2: { label: "2D Fix", color: "text-status-warning" },
  3: { label: "3D Fix", color: "text-status-success" },
  4: { label: "DGPS", color: "text-status-success" },
  5: { label: "RTK Float", color: "text-accent-primary" },
  6: { label: "RTK Fixed", color: "text-accent-primary" },
};

function GpsRow({ label, data }: { label: string; data: GpsData }) {
  const fix = FIX_TYPES[data.fixType] ?? FIX_TYPES[0];
  const hdopColor = data.hdop < 1.5 ? "text-status-success"
    : data.hdop < 3.0 ? "text-status-warning"
    : "text-status-error";

  return (
    <div className="flex items-center gap-2">
      <Satellite size={12} className={fix.color} />
      <span className="text-[10px] font-mono text-text-tertiary w-6">{label}</span>
      <span className={cn("text-[10px] font-mono font-medium", fix.color)}>
        {fix.label}
      </span>
      <span className="text-[10px] font-mono text-text-secondary">
        {data.satellites} sats
      </span>
      <span className={cn("text-[10px] font-mono", hdopColor)}>
        HDOP {data.hdop.toFixed(1)}
      </span>
    </div>
  );
}

/**
 * GPS status display: fix type, satellite count, HDOP.
 * Shows GPS2 alongside GPS1 when available.
 */
export function GpsSkyView({ className }: { className?: string }) {
  const gps = useTelemetryStore((s) => s.gps);
  const gps2 = useTelemetryStore((s) => s.gps2);
  const latest = gps.latest();
  const latest2 = gps2.latest();

  if (!latest) {
    return (
      <div className={cn("flex items-center gap-1 text-text-tertiary", className)}>
        <Satellite size={12} />
        <span className="text-[10px] font-mono">No GPS</span>
      </div>
    );
  }

  // Single GPS: show inline
  if (!latest2) {
    return (
      <div className={cn("space-y-0", className)}>
        <GpsRow label="GPS1" data={latest} />
      </div>
    );
  }

  // Dual GPS: stacked layout
  return (
    <div className={cn("space-y-0.5", className)}>
      <GpsRow label="GPS1" data={latest} />
      <GpsRow label="GPS2" data={latest2} />
    </div>
  );
}
