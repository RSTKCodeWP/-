/**
 * @module EzTunePanel
 * @description iNav EZ Tune configuration editor.
 * Reads and writes the EZ Tune block via the iNav MSP2 extension.
 * EZ Tune provides simplified single-slider tuning that internally
 * scales PID, filter, and rate parameters.
 * @license GPL-3.0-only
 */

"use client";

import { PanelHeader } from "../shared/PanelHeader";
import { Button } from "@/components/ui/button";
import { Sliders, Upload } from "lucide-react";
import { useSettingsParams } from "@/hooks/use-settings-params";
import type { DroneProtocol } from "@/lib/protocol/types";
import type { INavEzTune } from "@/lib/protocol/msp/msp-decoders-inav";

// ── Defaults ──────────────────────────────────────────────────

const DEFAULTS: INavEzTune = {
  enabled: false,
  filterHz: 110,
  axisRatio: 100,
  response: 50,
  damping: 50,
  stability: 50,
  aggressiveness: 50,
  rate: 50,
  expo: 50,
  snappiness: 50,
};

// ── Slider fields ─────────────────────────────────────────────

type SliderKey = Exclude<keyof INavEzTune, "enabled">;

const SLIDER_FIELDS: Array<{ key: SliderKey; label: string; min: number; max: number; hint: string }> = [
  { key: "filterHz", label: "Filter cutoff", min: 10, max: 200, hint: "Gyro low-pass filter cutoff in Hz" },
  { key: "axisRatio", label: "Axis ratio", min: 0, max: 150, hint: "Roll-to-pitch rate ratio" },
  { key: "response", label: "Response", min: 0, max: 150, hint: "Overall stick response" },
  { key: "damping", label: "Damping", min: 0, max: 150, hint: "Oscillation suppression" },
  { key: "stability", label: "Stability", min: 0, max: 150, hint: "Position-hold authority" },
  { key: "aggressiveness", label: "Aggressiveness", min: 0, max: 150, hint: "Flip and roll authority" },
  { key: "rate", label: "Rate", min: 0, max: 100, hint: "Maximum rotation rate" },
  { key: "expo", label: "Expo", min: 0, max: 100, hint: "Stick expo curve" },
  { key: "snappiness", label: "Snappiness", min: 0, max: 100, hint: "Quick-stop precision" },
];

// ── Helpers ───────────────────────────────────────────────────

const ezTuneSupported = (p: DroneProtocol): boolean => typeof p.getEzTune === "function";

async function readEzTune(protocol: DroneProtocol): Promise<INavEzTune> {
  return protocol.getEzTune!();
}

async function writeEzTune(protocol: DroneProtocol, values: INavEzTune): Promise<void> {
  const result = await protocol.setEzTune!(values);
  if (!result.success) throw new Error(result.message);
}

// ── Component ─────────────────────────────────────────────────

export function EzTunePanel() {
  const {
    values, setValues, loading, error, hasLoaded, dirty,
    connected, isArmed, lockMessage, read, write,
  } = useSettingsParams<INavEzTune>({
    panelId: "inav-ez-tune",
    initial: DEFAULTS,
    read: readEzTune,
    write: writeEzTune,
    supported: ezTuneSupported,
    unsupportedMessage: "EZ Tune not available on this firmware",
  });

  function handleSlider(key: SliderKey, raw: string) {
    setValues((prev) => ({ ...prev, [key]: parseInt(raw, 10) }));
  }

  function handleToggle() {
    setValues((prev) => ({ ...prev, enabled: !prev.enabled }));
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl space-y-4">
        <PanelHeader
          title="EZ Tune"
          subtitle="Simplified PID and filter tuning via unified sliders."
          icon={<Sliders size={16} />}
          loading={loading}
          loadProgress={null}
          hasLoaded={hasLoaded}
          onRead={read}
          connected={connected}
          error={error}
        >
          {hasLoaded && (
            <Button
              variant="primary"
              size="sm"
              icon={<Upload size={12} />}
              loading={loading}
              disabled={!connected || loading || isArmed}
              title={isArmed ? lockMessage : undefined}
              onClick={write}
            >
              Write to FC
            </Button>
          )}
        </PanelHeader>

        {hasLoaded && (
          <div className="border border-border-default rounded p-4 space-y-4">
            {dirty && (
              <p className="text-[10px] font-mono text-status-warning">
                Unsaved changes : use Write to FC to persist.
              </p>
            )}
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-text-secondary">Enable EZ Tune</span>
              <button
                onClick={handleToggle}
                className={`text-[11px] px-3 py-1 rounded border ${
                  values.enabled
                    ? "border-accent-primary bg-accent-primary/20 text-accent-primary"
                    : "border-border-default text-text-secondary"
                }`}
              >
                {values.enabled ? "Enabled" : "Disabled"}
              </button>
            </div>

            {SLIDER_FIELDS.map((f) => (
              <div key={f.key} className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-text-secondary">{f.label}</span>
                  <span className="text-[11px] font-mono text-text-primary">{values[f.key]}</span>
                </div>
                <input
                  type="range"
                  min={f.min}
                  max={f.max}
                  value={values[f.key] as number}
                  onChange={(e) => handleSlider(f.key, e.target.value)}
                  className="w-full"
                />
                <span className="text-[10px] text-text-tertiary">{f.hint}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
