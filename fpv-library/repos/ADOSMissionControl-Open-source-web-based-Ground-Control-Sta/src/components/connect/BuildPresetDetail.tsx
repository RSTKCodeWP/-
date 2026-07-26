"use client";

import type { BuildPreset } from "@/lib/presets/types";
import { X } from "lucide-react";

const TYPE_LABELS: Record<string, string> = {
  frame: "Frame",
  compute: "Compute",
  fc: "Flight Controller",
  esc: "ESC",
  motor: "Motor",
  sensor: "Sensor",
  camera: "Camera",
  radio: "Radio",
  gps: "GPS",
  battery: "Battery",
  rangefinder: "Rangefinder",
  companion: "Companion",
};

export function BuildPresetDetail({
  preset,
  onClose,
}: {
  preset: BuildPreset;
  onClose: () => void;
}) {
  return (
    <div className="border border-border-default bg-bg-secondary p-4 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h4 className="text-sm font-semibold text-text-primary font-display">
            {preset.name}
          </h4>
          <p className="text-[11px] text-text-tertiary mt-0.5">
            {preset.description}
          </p>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-text-tertiary hover:text-text-primary cursor-pointer"
        >
          <X size={14} />
        </button>
      </div>

      {/* Specs summary */}
      <div className="grid grid-cols-4 gap-2 text-[10px]">
        <SpecItem label="Props" value={preset.specs.propSize} />
        <SpecItem label="Motors" value={`${preset.specs.motorSize} ${preset.specs.motorKv}KV`} />
        <SpecItem label="Battery" value={`${preset.specs.cells}S ${preset.specs.batteryMah}mAh`} />
        <SpecItem label="AUW" value={`${preset.specs.auwGrams}g`} />
        <SpecItem label="Flight Time" value={`${preset.specs.flightTimeMin} min`} />
        <SpecItem label="GPS" value={preset.specs.hasGps ? "Yes" : "No"} />
        <SpecItem label="Compass" value={preset.specs.hasCompass ? "Yes" : "No"} />
        <SpecItem label="Rangefinder" value={preset.specs.hasRangefinder ? "Yes" : "No"} />
      </div>

      {/* Component list */}
      <div>
        <h5 className="text-[10px] font-mono text-text-tertiary uppercase tracking-wider mb-1.5">
          Components
        </h5>
        <div className="space-y-0.5">
          {preset.components.map((comp, i) => (
            <div
              key={`${comp.type}-${comp.name}-${i}`}
              className="flex items-center justify-between text-[10px] py-0.5 px-1.5 bg-bg-primary/50"
            >
              <div className="flex items-center gap-2">
                <span className="text-text-tertiary font-mono w-16 shrink-0">
                  {TYPE_LABELS[comp.type] ?? comp.type}
                </span>
                <span className="text-text-secondary">
                  {comp.count > 1 ? `${comp.count}× ` : ""}
                  {comp.name}
                </span>
              </div>
              {comp.details && (
                <span className="text-text-tertiary font-mono text-[9px]">
                  {Object.values(comp.details).slice(0, 2).join(" · ")}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SpecItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-text-tertiary font-mono text-[9px]">{label}</div>
      <div className="text-text-secondary">{value}</div>
    </div>
  );
}
