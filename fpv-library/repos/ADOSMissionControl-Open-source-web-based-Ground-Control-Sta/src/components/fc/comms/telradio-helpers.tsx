import React from "react";

export const TELRADIO_PARAMS = [
  "SERIAL1_PROTOCOL", "SERIAL1_BAUD",
  "SERIAL2_PROTOCOL", "SERIAL2_BAUD",
  "SYSID_THISMAV", "SYSID_MYGCS",
];

export const OPTIONAL_TELRADIO_PARAMS = [
  "SERIAL1_OPTIONS", "SERIAL2_OPTIONS",
];

export const SERIAL_PROTOCOL_OPTIONS = [
  { value: "-1", label: "-1 — None" },
  { value: "1", label: "1 — MAVLink1" },
  { value: "2", label: "2 — MAVLink2" },
  { value: "3", label: "3 — Frsky D" },
  { value: "4", label: "4 — Frsky SPort" },
  { value: "5", label: "5 — GPS" },
  { value: "10", label: "10 — FrSky Passthrough" },
  { value: "12", label: "12 — Lidar360" },
  { value: "13", label: "13 — Beacon" },
  { value: "14", label: "14 — Volz Servo" },
  { value: "19", label: "19 — SBUS Out" },
  { value: "22", label: "22 — LTM" },
  { value: "23", label: "23 — DroneCAN" },
  { value: "28", label: "28 — MSP" },
  { value: "29", label: "29 — DJI FPV" },
];

export const SERIAL_BAUD_OPTIONS = [
  { value: "1", label: "1200" },
  { value: "2", label: "2400" },
  { value: "4", label: "4800" },
  { value: "9", label: "9600" },
  { value: "19", label: "19200" },
  { value: "38", label: "38400" },
  { value: "57", label: "57600" },
  { value: "111", label: "111100" },
  { value: "115", label: "115200" },
  { value: "230", label: "230400" },
  { value: "460", label: "460800" },
  { value: "500", label: "500000" },
  { value: "921", label: "921600" },
];

export function rssiPercent(rssi: number): number {
  return Math.min(100, Math.max(0, (rssi / 255) * 100));
}

export function rssiColor(pct: number): string {
  if (pct >= 60) return "bg-status-success";
  if (pct >= 30) return "bg-status-warning";
  return "bg-status-error";
}

export function Card({
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
        <span className="text-accent-primary">{icon}</span>
        <div>
          <h2 className="text-sm font-medium text-text-primary">{title}</h2>
          <p className="text-[10px] text-text-tertiary">{description}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

export function RssiBar({ label, value, pct }: { label: string; value: number; pct: number }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-text-secondary">{label}</span>
        <span className="text-xs font-mono text-text-tertiary">{value}/255</span>
      </div>
      <div className="h-2 bg-bg-tertiary rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${rssiColor(pct)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function LiveStat({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div>
      <span className="text-[10px] text-text-tertiary block">{label}</span>
      <span className="text-sm font-mono text-text-primary">
        {value}
        {unit && <span className="text-[10px] text-text-tertiary ml-0.5">{unit}</span>}
      </span>
    </div>
  );
}
