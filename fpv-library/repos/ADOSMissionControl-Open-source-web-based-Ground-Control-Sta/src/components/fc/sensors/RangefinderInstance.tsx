"use client";

/**
 * @module fc/sensors/RangefinderInstance
 * @description One additional ArduPilot rangefinder instance (RNGFND2..A) in
 * the Sensors panel. Reuses the RNGFND1 field shape — type, analog pin, min/max
 * range, orientation — without the live-distance readout (that telemetry maps
 * to the primary instance). Instance 1 is rendered inline in SensorsPanel.
 * @license GPL-3.0-only
 */

import type { ReactNode } from "react";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { RNGFND_TYPE_OPTIONS, RNGFND_ORIENT_OPTIONS } from "./sensor-constants";

interface RangefinderInstanceProps {
  /** Instance suffix: "2".."9" or "A". */
  instance: string;
  p: (name: string, fallback?: string) => string;
  set: (name: string, v: string) => void;
  lbl: (raw: string) => ReactNode;
}

export function RangefinderInstance({ instance, p, set, lbl }: RangefinderInstanceProps) {
  const key = (field: string) => `RNGFND${instance}_${field}`;
  const type = p(key("TYPE"));

  return (
    <div className="border-t border-border-default pt-3 mt-1 space-y-3">
      <div className="text-[11px] font-medium text-text-secondary">
        Rangefinder {instance}
      </div>
      <Select
        label={lbl(`${key("TYPE")} — Sensor Type`)}
        options={RNGFND_TYPE_OPTIONS}
        value={type}
        onChange={(v) => set(key("TYPE"), v)}
      />
      {type !== "0" && (
        <>
          <Input
            label={lbl(`${key("PIN")} — Analog Pin`)}
            type="number"
            step="1"
            min="-1"
            value={p(key("PIN"), "-1")}
            onChange={(e) => set(key("PIN"), e.target.value)}
          />
          <Input
            label={lbl(`${key("MIN_CM")} — Min Distance`)}
            type="number"
            step="1"
            min="0"
            unit="cm"
            value={p(key("MIN_CM"), "20")}
            onChange={(e) => set(key("MIN_CM"), e.target.value)}
          />
          <Input
            label={lbl(`${key("MAX_CM")} — Max Distance`)}
            type="number"
            step="1"
            min="0"
            unit="cm"
            value={p(key("MAX_CM"), "700")}
            onChange={(e) => set(key("MAX_CM"), e.target.value)}
          />
          <Select
            label={lbl(`${key("ORIENT")} — Orientation`)}
            options={RNGFND_ORIENT_OPTIONS}
            value={p(key("ORIENT"), "25")}
            onChange={(v) => set(key("ORIENT"), v)}
          />
        </>
      )}
    </div>
  );
}
