/**
 * @module RateDynamicsPanel
 * @description iNav rate dynamics editor.
 * Reads six rate-dynamics settings (sensitivity, correction, weight; each split
 * into center and end) and writes them back through the named settings system.
 * @license GPL-3.0-only
 */

"use client";

import { PanelHeader } from "../shared/PanelHeader";
import { Button } from "@/components/ui/button";
import { Activity, Upload } from "lucide-react";
import { useSettingsParams } from "@/hooks/use-settings-params";
import type { DroneProtocol } from "@/lib/protocol/types";
import { settingNumber } from "@/lib/protocol/types";

// ── Types ─────────────────────────────────────────────────────

interface RateDynamics {
  sensitivityCenter: number;
  sensitivityEnd: number;
  correctionCenter: number;
  correctionEnd: number;
  weightCenter: number;
  weightEnd: number;
}

const DEFAULTS: RateDynamics = {
  sensitivityCenter: 50,
  sensitivityEnd: 50,
  correctionCenter: 50,
  correctionEnd: 50,
  weightCenter: 50,
  weightEnd: 50,
};

const FIELDS: Array<{ key: keyof RateDynamics; label: string; hint: string; setting: string }> = [
  { key: "sensitivityCenter", label: "Sensitivity center", hint: "Mid-stick response",         setting: "rate_dynamics_center_sensitivity" },
  { key: "sensitivityEnd",    label: "Sensitivity end",    hint: "Full-stick response",        setting: "rate_dynamics_end_sensitivity" },
  { key: "correctionCenter",  label: "Correction center",  hint: "Mid-stick snap correction",  setting: "rate_dynamics_center_correction" },
  { key: "correctionEnd",     label: "Correction end",     hint: "Full-stick snap correction", setting: "rate_dynamics_end_correction" },
  { key: "weightCenter",      label: "Weight center",      hint: "Mid-stick weighting",        setting: "rate_dynamics_center_weight" },
  { key: "weightEnd",         label: "Weight end",         hint: "Full-stick weighting",       setting: "rate_dynamics_end_weight" },
];

// ── Helpers ───────────────────────────────────────────────────

const settingsSupported = (p: DroneProtocol): boolean => !!p.settings;

async function readRateDynamics(protocol: DroneProtocol): Promise<RateDynamics> {
  const settings = protocol.settings!;
  const next: RateDynamics = { ...DEFAULTS };
  for (const { key, setting } of FIELDS) {
    next[key] = settingNumber(await settings.getSetting(setting));
  }
  return next;
}

async function writeRateDynamics(protocol: DroneProtocol, values: RateDynamics): Promise<void> {
  const settings = protocol.settings!;
  for (const { key, setting } of FIELDS) {
    await settings.setSetting(setting, values[key] & 0xff);
  }
}

// ── Component ─────────────────────────────────────────────────

export function RateDynamicsPanel() {
  const {
    values, setValues, loading, error, hasLoaded, dirty,
    connected, isArmed, lockMessage, read, write,
  } = useSettingsParams<RateDynamics>({
    panelId: "inav-rate-dynamics",
    initial: DEFAULTS,
    read: readRateDynamics,
    write: writeRateDynamics,
    supported: settingsSupported,
    unsupportedMessage: "Settings not available on this firmware",
  });

  const handleChange = (key: keyof RateDynamics, value: number) => {
    setValues((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl space-y-4">
        <PanelHeader
          title="Rate Dynamics"
          subtitle="Stick-response curve shaping. Values 0:100."
          icon={<Activity size={16} />}
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
          <div className="border border-border-default rounded p-4 space-y-3">
            {dirty && (
              <p className="text-[10px] font-mono text-status-warning">
                Unsaved changes : use Write to FC to persist.
              </p>
            )}
            {FIELDS.map((f) => (
              <div key={f.key} className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-text-secondary">{f.label}</span>
                  <span className="text-[11px] font-mono text-text-primary">{values[f.key]}</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={values[f.key]}
                  onChange={(e) => handleChange(f.key, parseInt(e.target.value))}
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
