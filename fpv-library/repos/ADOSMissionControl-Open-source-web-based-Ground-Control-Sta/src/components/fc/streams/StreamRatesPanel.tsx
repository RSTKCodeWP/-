"use client";

import { useMemo, useState } from "react";
import { Gauge, Save, RotateCcw, HardDrive } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import type { SelectOption } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { useFlashCommitToast } from "@/hooks/use-flash-commit-toast";
import { useDroneManager } from "@/stores/drone-manager";
import { usePanelParams } from "@/hooks/use-panel-params";
import { useUnsavedGuard } from "@/hooks/use-unsaved-guard";
import { useParamLabel } from "@/hooks/use-param-label";
import { useParamMetadataMap } from "@/hooks/use-param-metadata";
import { usePanelScroll } from "@/hooks/use-panel-scroll";
import { cn } from "@/lib/utils";
import { PanelHeader } from "../shared/PanelHeader";
import { ArmedLockOverlay } from "@/components/indicators/ArmedLockOverlay";
import { ParamFieldLabel } from "../parameters/ParamFieldLabel";

/** MAVLink channels carrying telemetry. Current ArduPilot (4.6+) indexes stream
 *  rates per MAVLink channel as MAVn_* (MAV1..MAV32); the first few cover the
 *  usual USB + telemetry-radio links. */
const PORTS: SelectOption[] = [
  { value: "MAV1", label: "MAV1 — Channel 1" },
  { value: "MAV2", label: "MAV2 — Channel 2" },
  { value: "MAV3", label: "MAV3 — Channel 3" },
  { value: "MAV4", label: "MAV4 — Channel 4" },
  { value: "MAV5", label: "MAV5 — Channel 5" },
  { value: "MAV6", label: "MAV6 — Channel 6" },
];

/** The MAVLink stream groups, each an independent rate (Hz). */
const GROUPS: { suffix: string; label: string }[] = [
  { suffix: "RAW_SENS", label: "Raw Sensors (IMU, pressure)" },
  { suffix: "EXT_STAT", label: "Extended Status (sys, battery, GPS)" },
  { suffix: "RC_CHAN", label: "RC Channels & Servo Output" },
  { suffix: "RAW_CTRL", label: "Raw Controller" },
  { suffix: "POSITION", label: "Position" },
  { suffix: "EXTRA1", label: "Extra 1 (Attitude)" },
  { suffix: "EXTRA2", label: "Extra 2 (VFR HUD)" },
  { suffix: "EXTRA3", label: "Extra 3 (AHRS, wind, status)" },
  { suffix: "PARAMS", label: "Parameters" },
  { suffix: "ADSB", label: "ADS-B" },
];

export function StreamRatesPanel() {
  const getSelectedProtocol = useDroneManager((s) => s.getSelectedProtocol);
  const { toast } = useToast();
  const { showFlashResult } = useFlashCommitToast();
  const { paramName: pn } = useParamLabel();
  const paramMeta = useParamMetadataMap();
  const scrollRef = usePanelScroll("stream-rates");
  const [saving, setSaving] = useState(false);
  const [port, setPort] = useState("MAV1");

  const paramNames = useMemo(() => GROUPS.map((g) => `${port}_${g.suffix}`), [port]);
  // Every rate is optional: a board may not use a given MAVLink channel, and a
  // missing MAVn_* param should leave the panel usable rather than erroring.
  const {
    params, loading, error, dirtyParams, hasRamWrites,
    loadProgress, hasLoaded, refresh, setLocalValue, saveAllToRam, commitToFlash, revertAll,
  } = usePanelParams({ paramNames, optionalParams: paramNames, panelId: "stream-rates", autoLoad: true });
  useUnsavedGuard(dirtyParams.size > 0);

  const connected = !!getSelectedProtocol();
  const hasDirty = dirtyParams.size > 0;

  async function handleSave() {
    setSaving(true);
    const ok = await saveAllToRam();
    setSaving(false);
    toast(ok ? "Saved to flight controller" : "Some parameters failed to save", ok ? "success" : "warning");
  }
  async function handleFlash() { showFlashResult(await commitToFlash()); }
  function handleRevert() { revertAll(); toast("Reverted to FC values", "info"); }

  return (
    <ArmedLockOverlay>
    <div ref={scrollRef} className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl space-y-6">
        <PanelHeader title="Telemetry Stream Rates" subtitle="Per-port MAVLink message group rates (Hz)"
          icon={<Gauge size={16} />} loading={loading} loadProgress={loadProgress} hasLoaded={hasLoaded}
          onRead={refresh} connected={connected} error={error} />

        <div className="flex items-center gap-3">
          <span className="text-xs text-text-secondary">MAVLink channel</span>
          <div className="w-64"><Select options={PORTS} value={port} onChange={setPort} /></div>
        </div>

        <div className="border border-border-default bg-bg-secondary p-4">
          <p className="text-[10px] text-text-tertiary mb-3">
            Rate in Hz for each MAVLink message group on {port}. 0 disables the group.
            Lower rates conserve bandwidth on constrained radio links.
          </p>
          <div className="space-y-3">
            {GROUPS.map((g) => {
              const param = `${port}_${g.suffix}`;
              const value = params.get(param) ?? 0;
              const isDirty = dirtyParams.has(param);
              return (
                <div key={g.suffix} className="grid grid-cols-[240px_1fr_80px] items-center gap-3">
                  <ParamFieldLabel label={g.label} param={pn(param)} meta={paramMeta.get(param)} />
                  <div className="relative">
                    <input type="range" min={0} max={50} step={1} value={value}
                      onChange={(e) => setLocalValue(param, parseFloat(e.target.value))}
                      className="w-full h-1.5 bg-bg-tertiary appearance-none cursor-pointer accent-accent-primary [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-accent-primary [&::-webkit-slider-thumb]:cursor-pointer" />
                    <div className="flex justify-between text-[8px] text-text-tertiary font-mono mt-0.5"><span>0</span><span>50 Hz</span></div>
                  </div>
                  <input type="number" min={0} max={50} step={1} value={value}
                    onChange={(e) => setLocalValue(param, parseFloat(e.target.value) || 0)}
                    className={cn("w-full h-7 px-1.5 bg-bg-tertiary border text-xs font-mono text-text-primary text-right focus:outline-none focus:border-accent-primary transition-colors", isDirty ? "border-status-warning" : "border-border-default")} />
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-3 pt-2 pb-4">
          <Button variant="primary" size="lg" icon={<Save size={14} />} disabled={!hasDirty || !connected} loading={saving} onClick={handleSave}>Save to Flight Controller</Button>
          <Button variant="secondary" size="lg" icon={<RotateCcw size={14} />} disabled={!hasDirty} onClick={handleRevert}>Revert</Button>
          {hasRamWrites && <Button variant="secondary" size="lg" icon={<HardDrive size={14} />} onClick={handleFlash}>Write to Flash</Button>}
          {!connected && <span className="text-[10px] text-text-tertiary">Connect a drone to save parameters</span>}
          {hasDirty && connected && <span className="text-[10px] text-status-warning">Unsaved changes</span>}
        </div>
      </div>
    </div>
    </ArmedLockOverlay>
  );
}
