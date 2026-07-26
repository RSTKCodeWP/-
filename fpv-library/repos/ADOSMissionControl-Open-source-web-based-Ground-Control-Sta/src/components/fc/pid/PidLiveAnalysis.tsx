"use client";

import { useState, useEffect, useMemo } from "react";
import { Activity, Waves, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTelemetryStore } from "@/stores/telemetry-store";

interface PidLiveAnalysisProps {
  connected: boolean;
}

function computeRms(values: number[]): number {
  if (values.length === 0) return 0;
  const sumSq = values.reduce((s, v) => s + v * v, 0);
  return Math.sqrt(sumSq / values.length);
}

function computeStdDev(values: number[]): number {
  if (values.length < 2) return 0;
  const mean = values.reduce((s, v) => s + v, 0) / values.length;
  const variance = values.reduce((s, v) => s + (v - mean) * (v - mean), 0) / (values.length - 1);
  return Math.sqrt(variance);
}

function vibeLevel(x: number, y: number, z: number): { label: string; color: string } {
  const max = Math.max(x, y, z);
  if (max < 15) return { label: "Good", color: "text-status-success" };
  if (max < 30) return { label: "Marginal", color: "text-status-warning" };
  return { label: "Bad", color: "text-status-error" };
}

export function PidLiveAnalysis({ connected }: PidLiveAnalysisProps) {
  const attitudeRing = useTelemetryStore((s) => s.attitude);
  const vibrationRing = useTelemetryStore((s) => s.vibration);
  const [tick, setTick] = useState(0);

  // Refresh at 2Hz
  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 500);
    return () => clearInterval(interval);
  }, []);

  const stats = useMemo(() => {
    // Last 5s window at ~10Hz = ~50 samples
    const recentAttitude = attitudeRing.last(50);
    const latestVibe = vibrationRing.latest();

    const rollRates = recentAttitude.map((a) => a.rollSpeed);
    const pitchRates = recentAttitude.map((a) => a.pitchSpeed);
    const yawRates = recentAttitude.map((a) => a.yawSpeed);

    return {
      rollRms: computeRms(rollRates),
      pitchRms: computeRms(pitchRates),
      yawRms: computeRms(yawRates),
      rollStdDev: computeStdDev(rollRates),
      pitchStdDev: computeStdDev(pitchRates),
      yawStdDev: computeStdDev(yawRates),
      vibeX: latestVibe?.vibrationX ?? 0,
      vibeY: latestVibe?.vibrationY ?? 0,
      vibeZ: latestVibe?.vibrationZ ?? 0,
      hasData: recentAttitude.length > 0,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, attitudeRing.length, vibrationRing.length]);

  const vibe = vibeLevel(stats.vibeX, stats.vibeY, stats.vibeZ);
  const OSCILLATION_THRESHOLD = 10; // deg/s stddev
  const hasOscillation =
    stats.rollStdDev > OSCILLATION_THRESHOLD ||
    stats.pitchStdDev > OSCILLATION_THRESHOLD ||
    stats.yawStdDev > OSCILLATION_THRESHOLD;

  if (!connected || !stats.hasData) {
    return (
      <div className="flex items-center gap-2 py-2 px-3 bg-bg-tertiary/30 border border-border-default">
        <Activity size={12} className="text-text-tertiary" />
        <span className="text-[10px] text-text-tertiary">
          {connected ? "Waiting for telemetry data..." : "No telemetry data"}
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 py-2 px-3 bg-bg-tertiary/30 border border-border-default overflow-x-auto">
      {/* Roll RMS */}
      <div className="flex items-center gap-1.5 shrink-0">
        <span className="text-[9px] text-text-tertiary">Roll</span>
        <span className="text-[10px] font-mono text-text-primary">
          {stats.rollRms.toFixed(1)}
        </span>
      </div>

      <div className="w-px h-4 bg-border-default shrink-0" />

      {/* Pitch RMS */}
      <div className="flex items-center gap-1.5 shrink-0">
        <span className="text-[9px] text-text-tertiary">Pitch</span>
        <span className="text-[10px] font-mono text-text-primary">
          {stats.pitchRms.toFixed(1)}
        </span>
      </div>

      <div className="w-px h-4 bg-border-default shrink-0" />

      {/* Yaw RMS */}
      <div className="flex items-center gap-1.5 shrink-0">
        <span className="text-[9px] text-text-tertiary">Yaw</span>
        <span className="text-[10px] font-mono text-text-primary">
          {stats.yawRms.toFixed(1)}
        </span>
      </div>

      <div className="w-px h-4 bg-border-default shrink-0" />

      {/* Vibration */}
      <div className="flex items-center gap-1.5 shrink-0">
        <Waves size={10} className="text-text-tertiary" />
        <span className={cn("text-[10px] font-mono", vibe.color)}>{vibe.label}</span>
      </div>

      {/* Oscillation indicator */}
      {hasOscillation && (
        <>
          <div className="w-px h-4 bg-border-default shrink-0" />
          <div className="flex items-center gap-1 shrink-0">
            <AlertTriangle size={10} className="text-status-warning" />
            <span className="text-[9px] text-status-warning">Oscillation</span>
          </div>
        </>
      )}
    </div>
  );
}
