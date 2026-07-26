"use client";

import { useState } from "react";
import { usePanelParams } from "@/hooks/use-panel-params";
import { useUnsavedGuard } from "@/hooks/use-unsaved-guard";
import { useDroneManager } from "@/stores/drone-manager";
import { useToast } from "@/components/ui/toast";
import { useFlashCommitToast } from "@/hooks/use-flash-commit-toast";
import { Button } from "@/components/ui/button";
import { Save, HardDrive } from "lucide-react";

const GPS_OFFSET_PARAMS = ["GPS_POS1_X", "GPS_POS1_Y", "GPS_POS1_Z"];
const GPS_GNSS_PARAMS = ["GPS_GNSS_MODE"];
const ALL_GPS_PARAMS = [...GPS_OFFSET_PARAMS, ...GPS_GNSS_PARAMS];

// GPS_GNSS_MODE is a bitmask
const GNSS_CONSTELLATIONS = [
  { bit: 0, label: "GPS", value: 1 },
  { bit: 1, label: "SBAS", value: 2 },
  { bit: 2, label: "Galileo", value: 4 },
  { bit: 3, label: "BeiDou", value: 8 },
  { bit: 4, label: "GLONASS", value: 16 },
] as const;

const GNSS_PRESETS = [
  { label: "Auto (all)", value: 0 },
  { label: "GPS + GLONASS", value: 17 },
  { label: "GPS + Galileo", value: 5 },
  { label: "GPS + BeiDou", value: 9 },
  { label: "GPS only", value: 1 },
] as const;

export function GpsConfigSection() {
  const getSelectedProtocol = useDroneManager((s) => s.getSelectedProtocol);
  const { toast } = useToast();
  const { showFlashResult } = useFlashCommitToast();
  const [saving, setSaving] = useState(false);

  const {
    params, loading, dirtyParams, hasRamWrites,
    hasLoaded, refresh, setLocalValue, saveAllToRam, commitToFlash,
  } = usePanelParams({ paramNames: ALL_GPS_PARAMS, panelId: "gps-config", autoLoad: false });
  useUnsavedGuard(dirtyParams.size > 0);

  const connected = !!getSelectedProtocol();
  const hasDirty = dirtyParams.size > 0;

  const gnssMode = params.get("GPS_GNSS_MODE") ?? 0;

  function toggleConstellation(bitValue: number) {
    if (gnssMode === 0) {
      // Auto mode: switching to manual with this constellation selected
      setLocalValue("GPS_GNSS_MODE", bitValue);
    } else {
      const newVal = gnssMode ^ bitValue;
      setLocalValue("GPS_GNSS_MODE", newVal === 0 ? 0 : newVal);
    }
  }

  function isConstellationEnabled(bitValue: number): boolean {
    if (gnssMode === 0) return true; // Auto = all enabled
    return (gnssMode & bitValue) !== 0;
  }

  async function handleSave() {
    setSaving(true);
    const ok = await saveAllToRam();
    setSaving(false);
    if (ok) toast("GPS config saved", "success");
    else toast("Some parameters failed to save", "warning");
  }

  async function handleFlash() {
    const ok = await commitToFlash();
    showFlashResult(ok, { successMessage: "Written to flash" });
  }

  return (
    <div className="border border-border-default bg-bg-secondary p-4 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-text-primary">GPS Configuration</h3>
          <p className="text-xs text-text-tertiary mt-0.5">
            Antenna position offsets and constellation selection
          </p>
        </div>
        {!hasLoaded && connected && (
          <Button variant="secondary" size="sm" onClick={refresh} loading={loading}>
            Read
          </Button>
        )}
      </div>

      {hasLoaded && (
        <>
          {/* GPS Antenna Offset */}
          <div>
            <h4 className="text-xs font-medium text-text-secondary mb-2">Antenna Position Offset (relative to IMU)</h4>
            <p className="text-[10px] text-text-tertiary mb-2">
              Coordinate system: X = forward (positive), Y = right (positive), Z = down (positive). Meters.
            </p>
            <div className="grid grid-cols-3 gap-3">
              {GPS_OFFSET_PARAMS.map((param) => {
                const axis = param.slice(-1); // X, Y, Z
                const axisLabel = axis === "X" ? "Forward (X)" : axis === "Y" ? "Right (Y)" : "Down (Z)";
                return (
                  <div key={param}>
                    <label className="text-[10px] text-text-tertiary block mb-1">{axisLabel}</label>
                    <input
                      type="number"
                      step="0.01"
                      value={params.get(param) ?? 0}
                      onChange={(e) => setLocalValue(param, Number(e.target.value) || 0)}
                      className="w-full h-7 px-2 bg-bg-tertiary border border-border-default text-xs font-mono text-text-primary focus:outline-none focus:border-accent-primary"
                    />
                    <span className="text-[9px] text-text-tertiary font-mono">{param}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* GPS Constellation Selection */}
          <div>
            <h4 className="text-xs font-medium text-text-secondary mb-2">GNSS Constellation</h4>
            <p className="text-[10px] text-text-tertiary mb-2">
              GPS_GNSS_MODE: 0 = auto (uses all available). Otherwise bitmask of enabled constellations.
            </p>

            {/* Presets */}
            <div className="flex flex-wrap gap-1.5 mb-2">
              {GNSS_PRESETS.map((preset) => (
                <button
                  key={preset.value}
                  onClick={() => setLocalValue("GPS_GNSS_MODE", preset.value)}
                  className={`px-2 py-1 text-[10px] border transition-colors ${
                    gnssMode === preset.value
                      ? "bg-accent-primary/20 border-accent-primary text-accent-primary"
                      : "bg-bg-tertiary border-border-default text-text-secondary hover:border-text-tertiary"
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>

            {/* Individual checkboxes */}
            <div className="flex flex-wrap gap-3">
              {GNSS_CONSTELLATIONS.map((c) => (
                <label key={c.bit} className="flex items-center gap-1.5 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={isConstellationEnabled(c.value)}
                    onChange={() => toggleConstellation(c.value)}
                    className="accent-accent-primary"
                  />
                  <span className="text-xs text-text-primary">{c.label}</span>
                </label>
              ))}
            </div>

            <p className="text-[10px] text-text-tertiary mt-1.5 font-mono">
              GPS_GNSS_MODE = {gnssMode}{gnssMode === 0 ? " (auto)" : ""}
            </p>
          </div>

          <div className="flex gap-2">
            <Button
              variant="primary"
              size="sm"
              icon={<Save size={12} />}
              onClick={handleSave}
              disabled={!hasDirty || saving}
              loading={saving}
            >
              Save
            </Button>
            {hasRamWrites && (
              <Button variant="secondary" size="sm" icon={<HardDrive size={12} />} onClick={handleFlash}>
                Write to Flash
              </Button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
