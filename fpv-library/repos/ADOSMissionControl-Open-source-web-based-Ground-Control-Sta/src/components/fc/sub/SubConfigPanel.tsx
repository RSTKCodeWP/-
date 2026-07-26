"use client";

import { useMemo, useState } from "react";
import { Waves, Save, RotateCcw, HardDrive, Gamepad2, ShieldAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
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
import { EnumSelect } from "../parameters/EnumSelect";
import { ParamFieldLabel } from "../parameters/ParamFieldLabel";

interface Field {
  param: string;
  label: string;
  kind: "enum" | "number";
  min?: number;
  max?: number;
  step?: number;
}

const DEPTH: Field[] = [
  { param: "PSC_POSZ_P", label: "Position Z P", kind: "number", min: 1, max: 3, step: 0.05 },
  { param: "PSC_VELZ_P", label: "Velocity Z P", kind: "number", min: 1, max: 8, step: 0.1 },
  { param: "PSC_VELZ_I", label: "Velocity Z I", kind: "number", min: 0.02, max: 1, step: 0.01 },
  { param: "PSC_ACCZ_P", label: "Accel Z P", kind: "number", min: 0.2, max: 1.5, step: 0.05 },
  { param: "PSC_ACCZ_I", label: "Accel Z I", kind: "number", min: 0, max: 3, step: 0.05 },
  { param: "PSC_ACCZ_D", label: "Accel Z D", kind: "number", min: 0, max: 0.4, step: 0.01 },
  { param: "SURFACE_DEPTH", label: "Surface Depth (cm)", kind: "number", min: -100, max: 0, step: 1 },
];

const HORIZ: Field[] = [
  { param: "PSC_POSXY_P", label: "Position XY P", kind: "number", min: 0.5, max: 2, step: 0.05 },
  { param: "PSC_VELXY_P", label: "Velocity XY P", kind: "number", min: 0.1, max: 6, step: 0.1 },
  { param: "PSC_VELXY_I", label: "Velocity XY I", kind: "number", min: 0.02, max: 1, step: 0.01 },
  { param: "PSC_VELXY_D", label: "Velocity XY D", kind: "number", min: 0, max: 1, step: 0.01 },
];

const FAILSAFE: Field[] = [
  { param: "FS_LEAK_ENABLE", label: "Leak Failsafe", kind: "enum" },
  { param: "FS_PRESS_ENABLE", label: "Depth (Pressure) Failsafe", kind: "enum" },
  { param: "FS_PRESS_MAX", label: "Max Depth Pressure (Pa)", kind: "number", min: 0, max: 6000000, step: 1000 },
  { param: "FS_TEMP_ENABLE", label: "Temperature Failsafe", kind: "enum" },
  { param: "FS_TEMP_MAX", label: "Max Temp (°C)", kind: "number", min: 0, max: 150, step: 1 },
];

// ArduSub supports 16 joystick buttons, each with a primary + shifted function.
const BUTTONS: Field[] = Array.from({ length: 16 }, (_, i) => ({
  param: `BTN${i}_FUNCTION`,
  label: `Button ${i}`,
  kind: "enum" as const,
}));
const SHIFT_BUTTONS: Field[] = Array.from({ length: 16 }, (_, i) => ({
  param: `BTN${i}_SFUNCTION`,
  label: `Button ${i} (shifted)`,
  kind: "enum" as const,
}));

const ALL_FIELDS = [...DEPTH, ...HORIZ, ...FAILSAFE, ...BUTTONS, ...SHIFT_BUTTONS];

export function SubConfigPanel() {
  const getSelectedProtocol = useDroneManager((s) => s.getSelectedProtocol);
  const { toast } = useToast();
  const { showFlashResult } = useFlashCommitToast();
  const { paramName: pn } = useParamLabel();
  const paramMeta = useParamMetadataMap();
  const scrollRef = usePanelScroll("sub-config");
  const [saving, setSaving] = useState(false);
  const [showButtons, setShowButtons] = useState(false);

  const paramNames = useMemo(() => ALL_FIELDS.map((f) => f.param), []);
  // Buttons + failsafe params can vary by build; keep them optional so a partial
  // set never errors the panel.
  const {
    params, loading, error, dirtyParams, hasRamWrites,
    loadProgress, hasLoaded, refresh, setLocalValue, saveAllToRam, commitToFlash, revertAll,
  } = usePanelParams({ paramNames, optionalParams: paramNames, panelId: "sub-config", autoLoad: true });
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

  const renderField = (f: Field) => {
    const value = params.get(f.param) ?? 0;
    const isDirty = dirtyParams.has(f.param);
    const meta = paramMeta.get(f.param);
    return (
      <div key={f.param} className="grid grid-cols-[200px_1fr] items-center gap-3">
        <ParamFieldLabel label={f.label} param={pn(f.param)} meta={meta} />
        {f.kind === "enum" && meta?.values && meta.values.size > 0 ? (
          <EnumSelect values={meta.values} value={value} onChange={(v) => setLocalValue(f.param, v)} />
        ) : (
          <input type="number" min={f.min} max={f.max} step={f.step} value={value}
            onChange={(e) => setLocalValue(f.param, parseFloat(e.target.value) || 0)}
            className={cn("w-full h-7 px-1.5 bg-bg-tertiary border text-xs font-mono text-text-primary text-right focus:outline-none focus:border-accent-primary transition-colors", isDirty ? "border-status-warning" : "border-border-default")} />
        )}
      </div>
    );
  };

  const section = (title: string, icon: React.ReactNode, fields: Field[]) => (
    <div className="border border-border-default bg-bg-secondary p-4">
      <div className="flex items-center gap-2 mb-3">{icon}<h2 className="text-sm font-medium text-text-primary">{title}</h2></div>
      <div className="space-y-3">{fields.map(renderField)}</div>
    </div>
  );

  return (
    <ArmedLockOverlay>
    <div ref={scrollRef} className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl space-y-6">
        <PanelHeader title="Sub Configuration" subtitle="Depth hold, position control, failsafes, and joystick buttons"
          icon={<Waves size={16} />} loading={loading} loadProgress={loadProgress} hasLoaded={hasLoaded}
          onRead={refresh} connected={connected} error={error} />

        {section("Depth Hold", <Waves size={14} className="text-accent-primary" />, DEPTH)}
        {section("Horizontal Position", <Waves size={14} className="text-accent-primary" />, HORIZ)}
        {section("Failsafes", <ShieldAlert size={14} className="text-accent-primary" />, FAILSAFE)}

        <div className="border border-border-default bg-bg-secondary">
          <button onClick={() => setShowButtons((v) => !v)} className="flex items-center gap-2 w-full px-4 py-3 text-left cursor-pointer hover:bg-bg-tertiary/50">
            <Gamepad2 size={14} className="text-accent-primary" />
            <h2 className="text-sm font-medium text-text-primary">Joystick Buttons</h2>
            <span className="text-[10px] text-text-tertiary ml-auto">{showButtons ? "▾" : "▸"}</span>
          </button>
          {showButtons && (
            <div className="px-4 pb-4 space-y-6">
              <div className="space-y-3 pt-2">{BUTTONS.map(renderField)}</div>
              <div>
                <p className="text-[10px] text-text-tertiary mb-3">Shifted functions (held while the shift button is active).</p>
                <div className="space-y-3">{SHIFT_BUTTONS.map(renderField)}</div>
              </div>
            </div>
          )}
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
