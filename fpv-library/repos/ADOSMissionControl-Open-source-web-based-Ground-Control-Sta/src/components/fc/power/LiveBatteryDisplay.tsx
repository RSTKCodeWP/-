"use client";

import { useMemo, useRef } from "react";
import { useTelemetryStore } from "@/stores/telemetry-store";
import { Battery, Thermometer, Clock, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

function cellVoltageColor(v: number): string {
  if (v >= 3.7) return "text-status-success";
  if (v >= 3.5) return "text-status-warning";
  return "text-status-error";
}

function cellVoltageBg(v: number): string {
  if (v >= 3.7) return "bg-status-success";
  if (v >= 3.5) return "bg-status-warning";
  return "bg-status-error";
}

function LiveStat({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div>
      <span className="text-[10px] text-text-tertiary block">{label}</span>
      <span className="text-sm font-mono text-text-primary">
        {value}
        <span className="text-[10px] text-text-tertiary ml-0.5">{unit}</span>
      </span>
    </div>
  );
}

export function LiveBatteryDisplay({ batteryCapacity }: { batteryCapacity: number }) {
  const batteryBuffer = useTelemetryStore((s) => s.battery);
  const latestBattery = batteryBuffer.latest();
  const voltage = latestBattery?.voltage ?? 0;
  const current = latestBattery?.current ?? 0;
  const remaining = latestBattery?.remaining ?? 0;
  const consumed = latestBattery?.consumed ?? 0;
  const temperature = latestBattery?.temperature;
  const cellVoltages = latestBattery?.cellVoltages;

  const connectTimeRef = useRef<number | null>(null);
  if (voltage > 0 && connectTimeRef.current === null) {
    connectTimeRef.current = Date.now();
  } else if (voltage === 0) {
    connectTimeRef.current = null;
  }

  const cellCount = useMemo(() => {
    if (cellVoltages && cellVoltages.length > 0) return cellVoltages.length;
    if (voltage <= 0) return 0;
    return Math.round(voltage / 4.2);
  }, [voltage, cellVoltages]);

  const displayCellVoltages = useMemo(() => {
    if (cellVoltages && cellVoltages.length > 0) return cellVoltages;
    if (cellCount <= 0) return [];
    const avg = voltage / cellCount;
    return Array.from({ length: cellCount }, () => avg);
  }, [voltage, cellCount, cellVoltages]);

  const cellImbalance = useMemo(() => {
    if (displayCellVoltages.length < 2) return null;
    const min = Math.min(...displayCellVoltages);
    const max = Math.max(...displayCellVoltages);
    const delta = max - min;
    if (delta < 0.05) return null;
    return { delta, severity: delta > 0.3 ? "error" as const : "warning" as const };
  }, [displayCellVoltages]);

  const estimatedMinutes = useMemo(() => {
    if (!connectTimeRef.current || consumed <= 0 || remaining <= 0) return null;
    const elapsedMs = Date.now() - connectTimeRef.current;
    if (elapsedMs < 30_000) return null;
    const ratePerMs = consumed / elapsedMs;
    if (ratePerMs <= 0) return null;
    const remainingMah = batteryCapacity > 0
      ? batteryCapacity - consumed
      : (consumed / (1 - remaining / 100)) * (remaining / 100);
    if (remainingMah <= 0) return null;
    return remainingMah / ratePerMs / 60_000;
  }, [consumed, remaining, batteryCapacity]);

  return (
    <div className="border border-border-default bg-bg-secondary p-4">
      <div className="flex items-center gap-2 mb-3">
        <Battery size={14} className="text-accent-primary" />
        <h2 className="text-sm font-medium text-text-primary">Live Battery</h2>
        {voltage > 0 && (
          <span className="text-[10px] font-mono text-text-tertiary ml-auto">
            {cellCount}S detected
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <LiveStat label="Voltage" value={voltage.toFixed(2)} unit="V" />
        <LiveStat label="Current" value={current.toFixed(1)} unit="A" />
        <LiveStat label="Remaining" value={`${Math.round(remaining)}`} unit="%" />
        <LiveStat label="Consumed" value={Math.round(consumed).toString()} unit="mAh" />
      </div>

      {voltage > 0 && (
        <div className="flex items-center gap-4 mb-3">
          {estimatedMinutes !== null && (
            <div className="flex items-center gap-1">
              <Clock size={10} className="text-text-tertiary" />
              <span className={cn(
                "text-[10px] font-mono",
                estimatedMinutes < 3 ? "text-status-error" : estimatedMinutes < 8 ? "text-status-warning" : "text-text-secondary"
              )}>
                ~{Math.round(estimatedMinutes)} min remaining
              </span>
            </div>
          )}
          {temperature !== undefined && (
            <div className="flex items-center gap-1">
              <Thermometer size={10} className="text-text-tertiary" />
              <span className={cn(
                "text-[10px] font-mono",
                temperature > 60 ? "text-status-error" : temperature > 45 ? "text-status-warning" : "text-text-secondary"
              )}>
                {temperature.toFixed(1)}&deg;C
              </span>
            </div>
          )}
        </div>
      )}

      {displayCellVoltages.length > 0 && (
        <div>
          <span className="text-[10px] text-text-tertiary mb-1.5 block">
            {cellVoltages ? "Cell Voltages" : "Cell Voltage Estimate"}
          </span>
          <div className="flex gap-1.5">
            {displayCellVoltages.map((cv, i) => (
              <div key={i} className="flex-1">
                <div className="h-8 bg-bg-tertiary relative overflow-hidden">
                  <div
                    className={cn("absolute bottom-0 left-0 right-0 transition-all", cellVoltageBg(cv))}
                    style={{ height: `${Math.min(100, Math.max(0, ((cv - 3.0) / 1.2) * 100))}%`, opacity: 0.3 }}
                  />
                  <span className={cn("absolute inset-0 flex items-center justify-center text-[10px] font-mono", cellVoltageColor(cv))}>
                    {cv.toFixed(2)}
                  </span>
                </div>
                <span className="text-[9px] text-text-tertiary block text-center mt-0.5">C{i + 1}</span>
              </div>
            ))}
          </div>
          {cellImbalance && (
            <div className={cn(
              "flex items-center gap-1 mt-2 text-[10px]",
              cellImbalance.severity === "error" ? "text-status-error" : "text-status-warning"
            )}>
              <AlertTriangle size={10} />
              <span>Cell imbalance: {"\u0394"}{Math.round(cellImbalance.delta * 1000)}mV</span>
            </div>
          )}
        </div>
      )}

      {voltage === 0 && (
        <p className="text-[10px] text-text-tertiary">No battery data — connect a drone to view live telemetry</p>
      )}
    </div>
  );
}
