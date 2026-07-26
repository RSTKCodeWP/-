/**
 * @module FwApproachPanel
 * @description iNav fixed-wing approach configuration editor.
 * Up to 4 approach slots define the landing trajectory for each
 * configured runway or approach path.
 * Only shown on fixed-wing platforms.
 * @license GPL-3.0-only
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import { useDroneManager } from "@/stores/drone-manager";
import { useArmedLock } from "@/hooks/use-armed-lock";
import { PanelHeader } from "../shared/PanelHeader";
import { Plane } from "lucide-react";
import type { INavFwApproach } from "@/lib/protocol/msp/msp-decoders-inav";

// platformType 0 = MULTIROTOR. FW Approach is only relevant for non-multirotor platforms.
const PLATFORM_MULTIROTOR = 0;

// ── Defaults ──────────────────────────────────────────────────

const SLOT_COUNT = 4;

function defaultSlot(number: number): INavFwApproach {
  return {
    number,
    approachAlt: 5000,
    landAlt: 0,
    approachDirection: 0,
    landHeading1: 0,
    landHeading2: 0,
    isSeaLevelRef: false,
  };
}

// ── Helpers ───────────────────────────────────────────────────

function asProtocol(protocol: unknown): {
  getFwApproach(): Promise<INavFwApproach[]>;
  setFwApproach(a: INavFwApproach): Promise<{ success: boolean; message: string }>;
} | null {
  const p = protocol as Record<string, unknown>;
  if (p && typeof p.getFwApproach === "function") {
    return protocol as { getFwApproach(): Promise<INavFwApproach[]>; setFwApproach(a: INavFwApproach): Promise<{ success: boolean; message: string }> };
  }
  return null;
}

// ── Component ─────────────────────────────────────────────────

export function FwApproachPanel() {
  const getSelectedProtocol = useDroneManager((s) => s.getSelectedProtocol);
  const connected = !!getSelectedProtocol();

  const [loading, setLoading] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savingIdx, setSavingIdx] = useState<number | null>(null);
  const [platformType, setPlatformType] = useState<number | null>(null);

  const { isArmed, lockMessage } = useArmedLock();
  const [slots, setSlots] = useState<INavFwApproach[]>(
    Array.from({ length: SLOT_COUNT }, (_, i) => defaultSlot(i)),
  );

  useEffect(() => {
    const protocol = getSelectedProtocol();
    if (!protocol?.getMixerConfig) return;
    protocol.getMixerConfig().then((m) => {
      setPlatformType(m.platformType);
    }).catch(() => {
      // Leave platformType null on unsupported firmware.
    });
  }, [getSelectedProtocol]);

  const handleRead = useCallback(async () => {
    const protocol = getSelectedProtocol();
    const adapter = asProtocol(protocol);
    if (!adapter) { setError("FW approach config not available on this firmware"); return; }
    setLoading(true); setError(null);
    try {
      const data = await adapter.getFwApproach();
      const filled = Array.from({ length: SLOT_COUNT }, (_, i) => data[i] ?? defaultSlot(i));
      setSlots(filled);
      setHasLoaded(true);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [getSelectedProtocol]);

  function updateSlot(idx: number, key: keyof INavFwApproach, value: unknown) {
    setSlots((prev) => prev.map((s, i) => (i === idx ? { ...s, [key]: value } : s)));
  }

  const handleSave = useCallback(async (idx: number) => {
    const protocol = getSelectedProtocol();
    const adapter = asProtocol(protocol);
    if (!adapter) { setError("FW approach write not available on this firmware"); return; }
    setSavingIdx(idx); setError(null);
    try {
      const result = await adapter.setFwApproach(slots[idx]);
      if (!result.success) setError(result.message);
    } catch (err) {
      setError(String(err));
    } finally {
      setSavingIdx(null);
    }
  }, [getSelectedProtocol, slots]);

  const isMultirotor = platformType === PLATFORM_MULTIROTOR;

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl space-y-4">
        {isMultirotor && (
          <p className="text-[11px] text-text-tertiary border border-border-default rounded px-3 py-2 bg-bg-secondary">
            This panel applies to fixed-wing and tricopter platforms. The connected flight controller is configured as a multirotor.
          </p>
        )}
        <PanelHeader
          title="FW Approach"
          subtitle="Fixed-wing landing approach configuration. Up to 4 approach slots."
          icon={<Plane size={16} />}
          loading={loading}
          loadProgress={null}
          hasLoaded={hasLoaded}
          onRead={handleRead}
          connected={connected}
          error={error}
        />

        {hasLoaded && !isMultirotor && (
          <div className="space-y-4">
            {slots.map((slot, idx) => (
              <div key={idx} className="border border-border-default rounded p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[12px] font-semibold text-text-primary">Approach {idx}</span>
                  <button
                    onClick={() => handleSave(idx)}
                    disabled={savingIdx === idx || isArmed}
                    title={isArmed ? lockMessage : undefined}
                    className="text-[11px] px-3 py-1 border border-accent-primary text-accent-primary rounded hover:bg-accent-primary/10 disabled:opacity-50"
                  >
                    {savingIdx === idx ? "Saving..." : "Save"}
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <NumInput label="Approach alt (cm)" value={slot.approachAlt} onChange={(v) => updateSlot(idx, "approachAlt", v)} />
                  <NumInput label="Land alt (cm)" value={slot.landAlt} onChange={(v) => updateSlot(idx, "landAlt", v)} />
                  <NumInput label="Approach direction" value={slot.approachDirection} min={0} max={359} onChange={(v) => updateSlot(idx, "approachDirection", v)} />
                  <NumInput label="Land heading 1" value={slot.landHeading1} min={-180} max={180} onChange={(v) => updateSlot(idx, "landHeading1", v)} />
                  <NumInput label="Land heading 2" value={slot.landHeading2} min={-180} max={180} onChange={(v) => updateSlot(idx, "landHeading2", v)} />
                  <div className="flex flex-col gap-1">
                    <span className="text-[11px] text-text-secondary">Sea-level ref</span>
                    <button
                      onClick={() => updateSlot(idx, "isSeaLevelRef", !slot.isSeaLevelRef)}
                      className={`text-[11px] px-3 py-1 rounded border ${
                        slot.isSeaLevelRef
                          ? "border-accent-primary bg-accent-primary/20 text-accent-primary"
                          : "border-border-default text-text-secondary"
                      }`}
                    >
                      {slot.isSeaLevelRef ? "Sea level" : "Relative"}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Inline numeric input ──────────────────────────────────────

function NumInput({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min?: number;
  max?: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] text-text-secondary">{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(parseInt(e.target.value, 10) || 0)}
        className="w-full bg-bg-tertiary border border-border-default rounded px-2 py-1 text-[11px] text-text-primary font-mono"
      />
    </div>
  );
}
