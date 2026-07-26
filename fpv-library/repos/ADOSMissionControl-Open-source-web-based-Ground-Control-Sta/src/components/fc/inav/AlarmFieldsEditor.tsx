/**
 * @module AlarmFieldsEditor
 * @description Numeric inputs for the iNav OSD alarms struct.
 * Sub-component of INavOsdPanel; renders a fixed list of alarm fields with
 * label, unit, optional min/max bounds.
 * @license GPL-3.0-only
 */

"use client";

import type { INavOsdAlarms } from "@/lib/protocol/msp/msp-decoders-inav";

const ALARM_FIELDS: Array<{
  key: keyof INavOsdAlarms;
  label: string;
  unit: string;
  min?: number;
  max?: number;
}> = [
  { key: "rssi", label: "RSSI threshold", unit: "%", min: 0, max: 100 },
  { key: "flyMinutes", label: "Fly time", unit: "min", min: 0, max: 9999 },
  { key: "maxAltitude", label: "Max altitude", unit: "m", min: 0, max: 99999 },
  { key: "distance", label: "Distance", unit: "m", min: 0, max: 99999 },
  { key: "maxNegAltitude", label: "Max negative altitude", unit: "m", min: 0, max: 99999 },
  { key: "gforce", label: "G-force", unit: "g x100", min: 0, max: 9999 },
  { key: "gforceAxisMin", label: "G-force axis min", unit: "g x100" },
  { key: "gforceAxisMax", label: "G-force axis max", unit: "g x100" },
  { key: "current", label: "Current", unit: "A", min: 0, max: 255 },
  { key: "imuTempMin", label: "IMU temp min", unit: "deci-C" },
  { key: "imuTempMax", label: "IMU temp max", unit: "deci-C" },
  { key: "baroTempMin", label: "Baro temp min", unit: "deci-C" },
  { key: "baroTempMax", label: "Baro temp max", unit: "deci-C" },
  { key: "adsbDistanceWarning", label: "ADS-B distance warning", unit: "m" },
  { key: "adsbDistanceAlert", label: "ADS-B distance alert", unit: "m" },
];

interface AlarmFieldsEditorProps {
  alarms: INavOsdAlarms | null;
  onUpdate: <K extends keyof INavOsdAlarms>(key: K, value: INavOsdAlarms[K]) => void;
}

export function AlarmFieldsEditor({ alarms, onUpdate }: AlarmFieldsEditorProps) {
  if (!alarms) {
    return <p className="text-[11px] text-text-tertiary">No alarm data returned by FC.</p>;
  }
  return (
    <div className="space-y-2">
      {ALARM_FIELDS.map((f) => (
        <div key={f.key} className="flex items-center justify-between gap-3">
          <span className="text-[11px] text-text-secondary shrink-0 w-44">
            {f.label} ({f.unit})
          </span>
          <input
            type="number"
            min={f.min}
            max={f.max}
            value={alarms[f.key] as number}
            onChange={(e) => onUpdate(f.key, parseInt(e.target.value, 10) || 0)}
            className="w-28 bg-bg-tertiary border border-border-default rounded px-2 py-1 text-[11px] font-mono text-text-primary text-right"
          />
        </div>
      ))}
    </div>
  );
}
