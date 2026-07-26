"use client";

import { useState, useCallback, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { useFlashCommitToast } from "@/hooks/use-flash-commit-toast";
import { useDroneManager } from "@/stores/drone-manager";
import { useTelemetryStore } from "@/stores/telemetry-store";
import { usePanelParams } from "@/hooks/use-panel-params";
import { useUnsavedGuard } from "@/hooks/use-unsaved-guard";
import { PanelHeader } from "../shared/PanelHeader";
import { ArmedLockOverlay } from "@/components/indicators/ArmedLockOverlay";
import { SlidersHorizontal, Save, RotateCcw, HardDrive, Radio } from "lucide-react";
import { cn } from "@/lib/utils";
import { usePanelScroll } from "@/hooks/use-panel-scroll";
import { AdjustmentRangeSlider, stepToPwm, pwmToStep, TOTAL_STEPS } from "./AdjustmentRangeSlider";
import { ADJUSTMENT_FUNCTIONS, AUX_CHANNELS, ADJUSTMENT_SLOT_COUNT, buildAdjustmentParamNames } from "./adjustment-constants";

const paramNames = buildAdjustmentParamNames();

export function AdjustmentsPanel() {
  const getSelectedProtocol = useDroneManager((s) => s.getSelectedProtocol);
  const { toast } = useToast();
  const { showFlashResult } = useFlashCommitToast();
  const [saving, setSaving] = useState(false);
  const scrollRef = usePanelScroll("adjustments");

  const {
    params, loading, error, dirtyParams, hasRamWrites,
    loadProgress, hasLoaded,
    refresh, setLocalValue, saveAllToRam, commitToFlash, revertAll,
  } = usePanelParams({ paramNames, panelId: "adjustments", autoLoad: true });
  useUnsavedGuard(dirtyParams.size > 0);

  const connected = !!getSelectedProtocol();
  const hasDirty = dirtyParams.size > 0;

  const rcBuffer = useTelemetryStore((s) => s.rc);
  const latestRc = rcBuffer.latest();

  const p = (name: string, fallback = 0) => String(params.get(name) ?? fallback);
  const pNum = (name: string, fallback = 0) => Number(params.get(name) ?? fallback);

  const handleEnableToggle = useCallback((slotIndex: number, currentlyEnabled: boolean) => {
    if (currentlyEnabled) {
      setLocalValue(`BF_ADJ${slotIndex}_ENABLE`, 0);
      setLocalValue(`BF_ADJ${slotIndex}_RANGE_LOW`, 900);
      setLocalValue(`BF_ADJ${slotIndex}_RANGE_HIGH`, 900);
    } else {
      setLocalValue(`BF_ADJ${slotIndex}_ENABLE`, 1);
      const low = pNum(`BF_ADJ${slotIndex}_RANGE_LOW`);
      const high = pNum(`BF_ADJ${slotIndex}_RANGE_HIGH`);
      if (low === high) {
        setLocalValue(`BF_ADJ${slotIndex}_RANGE_LOW`, 1300);
        setLocalValue(`BF_ADJ${slotIndex}_RANGE_HIGH`, 1700);
      }
    }
  }, [setLocalValue, pNum]);

  async function handleSave() {
    setSaving(true);
    const ok = await saveAllToRam();
    setSaving(false);
    if (ok) toast("Saved to flight controller", "success");
    else toast("Some parameters failed to save", "warning");
  }

  async function handleFlash() {
    const ok = await commitToFlash();
    showFlashResult(ok);
  }

  function handleRevert() {
    revertAll();
    toast("Reverted to FC values", "info");
  }

  const getAuxPwm = useCallback((auxChannelIndex: number): number => {
    if (!latestRc) return 0;
    return latestRc.channels[auxChannelIndex + 4] ?? 0;
  }, [latestRc]);

  const sortedFunctions = useMemo(() => {
    const copy = [...ADJUSTMENT_FUNCTIONS];
    copy.sort((a, b) => a.label.localeCompare(b.label));
    return copy;
  }, []);

  return (
    <ArmedLockOverlay>
    <div ref={scrollRef} className="flex-1 overflow-y-auto p-6">
      <div className="max-w-3xl space-y-6">
        <PanelHeader
          title="Adjustments"
          subtitle="In-flight parameter adjustment via RC channels"
          icon={<SlidersHorizontal size={16} />}
          loading={loading}
          loadProgress={loadProgress}
          hasLoaded={hasLoaded}
          onRead={refresh}
          connected={connected}
          error={error}
        />

        <p className="text-xs text-text-tertiary">
          Assign RC channel ranges to adjust PID, rate, and other parameters in flight.
          Each slot maps a switch channel (enable range) and an adjustment channel (value).
        </p>

        {/* Live RC channel preview */}
        {hasLoaded && latestRc && (
          <div className="border border-border-default bg-bg-secondary p-4 space-y-3">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-accent-primary"><Radio size={14} /></span>
              <div>
                <h2 className="text-sm font-medium text-text-primary">Live RC Channels</h2>
                <p className="text-[10px] text-text-tertiary">Current AUX channel PWM values</p>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {Array.from({ length: 8 }, (_, i) => {
                const pwm = getAuxPwm(i);
                const pct = pwm > 0 ? ((pwm - 900) / 1200) * 100 : 0;
                return (
                  <div key={i} className="space-y-1">
                    <div className="flex justify-between text-[10px]">
                      <span className="text-text-secondary">AUX {i + 1}</span>
                      <span className="font-mono text-accent-primary tabular-nums">
                        {pwm > 0 ? pwm : "\u2014"}
                      </span>
                    </div>
                    <div className="h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent-primary rounded-full transition-all"
                        style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Adjustment slots */}
        {hasLoaded && (
          <div className="space-y-3">
            {Array.from({ length: ADJUSTMENT_SLOT_COUNT }, (_, i) => {
              const enabled = pNum(`BF_ADJ${i}_ENABLE`) === 1;
              const rangeLow = pNum(`BF_ADJ${i}_RANGE_LOW`, 900);
              const rangeHigh = pNum(`BF_ADJ${i}_RANGE_HIGH`, 2100);
              const auxChannel = pNum(`BF_ADJ${i}_CHANNEL`);
              const activePwm = getAuxPwm(auxChannel);

              return (
                <div
                  key={i}
                  className={cn(
                    "border border-border-default bg-bg-secondary p-4 space-y-3 transition-opacity",
                    !enabled && "opacity-50",
                  )}
                >
                  <div className="flex items-center gap-3">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={enabled}
                        onChange={() => handleEnableToggle(i, enabled)}
                        className="accent-accent-primary w-4 h-4"
                      />
                      <span className="text-xs font-medium text-text-primary">Slot {i}</span>
                    </label>
                    {enabled && (
                      <span className="text-[10px] text-text-tertiary">
                        {ADJUSTMENT_FUNCTIONS.find(f => f.value === p(`BF_ADJ${i}_FUNCTION`))?.label ?? "Unknown"}
                      </span>
                    )}
                  </div>

                  {enabled && (
                    <>
                      <div className="grid grid-cols-[1fr_1fr_1fr] gap-3">
                        <div>
                          <label className="text-[10px] text-text-tertiary block mb-1">When Channel</label>
                          <Select
                            options={AUX_CHANNELS}
                            value={p(`BF_ADJ${i}_CHANNEL`)}
                            onChange={(v) => setLocalValue(`BF_ADJ${i}_CHANNEL`, Number(v))}
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-text-tertiary block mb-1">Apply Function</label>
                          <Select
                            options={sortedFunctions}
                            value={p(`BF_ADJ${i}_FUNCTION`)}
                            onChange={(v) => setLocalValue(`BF_ADJ${i}_FUNCTION`, Number(v))}
                            searchable
                            searchPlaceholder="Search functions..."
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-text-tertiary block mb-1">Via Channel</label>
                          <Select
                            options={AUX_CHANNELS}
                            value={p(`BF_ADJ${i}_VIA_CHANNEL`)}
                            onChange={(v) => setLocalValue(`BF_ADJ${i}_VIA_CHANNEL`, Number(v))}
                          />
                        </div>
                      </div>

                      <div className="space-y-1">
                        <div className="flex justify-between text-[10px] text-text-secondary">
                          <span>{rangeLow} \u00B5s</span>
                          <span className="text-text-tertiary">Activation Range</span>
                          <span>{rangeHigh} \u00B5s</span>
                        </div>
                        <AdjustmentRangeSlider
                          start={pwmToStep(Math.max(900, Math.min(2100, rangeLow)))}
                          end={pwmToStep(Math.max(900, Math.min(2100, rangeHigh)))}
                          activePwm={activePwm}
                          onChange={(startStep, endStep) => {
                            setLocalValue(`BF_ADJ${i}_RANGE_LOW`, stepToPwm(startStep));
                            setLocalValue(`BF_ADJ${i}_RANGE_HIGH`, stepToPwm(endStep));
                          }}
                          dirty={
                            dirtyParams.has(`BF_ADJ${i}_RANGE_LOW`) ||
                            dirtyParams.has(`BF_ADJ${i}_RANGE_HIGH`)
                          }
                        />
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Available functions reference */}
        <div className="border border-border-default bg-bg-secondary p-4">
          <h3 className="text-xs font-medium text-text-primary mb-2">Available Functions</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-0.5">
            {ADJUSTMENT_FUNCTIONS.map((f) => (
              <span key={f.value} className="text-[10px] text-text-tertiary font-mono">
                {f.value.padStart(2, "\u2007")}: {f.label}
              </span>
            ))}
          </div>
        </div>

        {/* Save / Revert */}
        <div className="flex items-center gap-3 pt-2 pb-4">
          <Button variant="primary" size="lg" icon={<Save size={14} />} disabled={!hasDirty || !connected} loading={saving} onClick={handleSave}>
            Save to Flight Controller
          </Button>
          <Button variant="secondary" size="lg" icon={<RotateCcw size={14} />} disabled={!hasDirty} onClick={handleRevert}>
            Revert
          </Button>
          {hasRamWrites && (
            <Button variant="secondary" size="lg" icon={<HardDrive size={14} />} onClick={handleFlash}>
              Write to Flash
            </Button>
          )}
          {!connected && <span className="text-[10px] text-text-tertiary">Connect a drone to save parameters</span>}
          {hasDirty && connected && <span className="text-[10px] text-status-warning">Unsaved changes</span>}
        </div>
      </div>
    </div>
    </ArmedLockOverlay>
  );
}
