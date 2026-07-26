"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { Save, Crosshair } from "lucide-react";

const RC_CHANNEL_COUNT = 16;

interface ReceiverBindingUIProps {
  channels: number[];
  hasRcData: boolean;
  setLocalValue: (name: string, value: number) => void;
  getChannelTrim: (i: number) => number;
  getChannelDz: (i: number) => number;
  rollCh: number;
  pitchCh: number;
  yawCh: number;
  onSetParameter: (name: string, value: number) => Promise<void>;
}

export function ReceiverBindingUI({
  channels,
  hasRcData,
  setLocalValue,
  getChannelTrim,
  getChannelDz,
  rollCh,
  pitchCh,
  yawCh,
  onSetParameter,
}: ReceiverBindingUIProps) {
  const { toast } = useToast();

  // ── Calibration state ──────────────────────────────────────
  const [calibrating, setCalibrating] = useState(false);
  const [calStep, setCalStep] = useState<1 | 2>(1);
  const [showTrimPreview, setShowTrimPreview] = useState(false);
  const [settingTrims, setSettingTrims] = useState(false);
  const [calMins, setCalMins] = useState<number[]>(() => Array(RC_CHANNEL_COUNT).fill(2000));
  const [calMaxs, setCalMaxs] = useState<number[]>(() => Array(RC_CHANNEL_COUNT).fill(1000));

  // Update calibration extremes from live channel data
  useEffect(() => {
    if (!calibrating) return;
    setCalMins((prev) =>
      prev.map((v, i) => (channels[i] > 0 ? Math.min(v, channels[i]) : v)),
    );
    setCalMaxs((prev) =>
      prev.map((v, i) => (channels[i] > 0 ? Math.max(v, channels[i]) : v)),
    );
  }, [calibrating, channels]);

  const trimTargets = useMemo(() => [
    { role: "Roll", ch: rollCh },
    { role: "Pitch", ch: pitchCh },
    { role: "Yaw", ch: yawCh },
  ], [rollCh, pitchCh, yawCh]);

  async function handleSetTrims() {
    setSettingTrims(true);
    for (const { ch } of trimTargets) {
      const current = channels[ch - 1] ?? 0;
      if (current > 0) {
        await onSetParameter(`RC${ch}_TRIM`, current);
        setLocalValue(`RC${ch}_TRIM`, current);
      }
    }
    setSettingTrims(false);
    setShowTrimPreview(false);
    toast("Trims set to current stick positions", "success");
  }

  // ── Save calibration ──────────────────────────────────────

  const saveCalibration = useCallback(async () => {
    for (let i = 0; i < RC_CHANNEL_COUNT; i++) {
      const ch = i + 1;
      if (calMins[i] < 1500) {
        await onSetParameter(`RC${ch}_MIN`, calMins[i]);
        setLocalValue(`RC${ch}_MIN`, calMins[i]);
      }
      if (calMaxs[i] > 1500) {
        await onSetParameter(`RC${ch}_MAX`, calMaxs[i]);
        setLocalValue(`RC${ch}_MAX`, calMaxs[i]);
      }
      if (channels[i] > 0) {
        await onSetParameter(`RC${ch}_TRIM`, channels[i]);
        setLocalValue(`RC${ch}_TRIM`, channels[i]);
      }
    }
    setCalibrating(false);
    setCalStep(1);
    toast("Calibration saved to FC — trims set to current stick positions", "success");
  }, [calMins, calMaxs, channels, onSetParameter, setLocalValue, toast]);

  return (
    <Card title="Radio Calibration">
      <div className="space-y-3">
        {/* ── Set Trims to Current (standalone, outside calibration) ── */}
        {!calibrating && (
          <>
            {showTrimPreview ? (
              <div className="p-2 bg-bg-tertiary border border-border-default space-y-2">
                <p className="text-[10px] font-medium text-text-secondary">Trim Preview (Roll, Pitch, Yaw):</p>
                <div className="space-y-0.5">
                  {trimTargets.map(({ role, ch }) => {
                    const current = channels[ch - 1] ?? 0;
                    const oldTrim = getChannelTrim(ch - 1);
                    return (
                      <div key={ch} className="flex items-center gap-2 text-[10px] font-mono">
                        <span className="text-text-secondary w-10">{role}</span>
                        <span className="text-text-tertiary">RC{ch}_TRIM:</span>
                        <span className="text-text-tertiary">{oldTrim}</span>
                        <span className="text-text-secondary">→</span>
                        <span className="text-text-primary">{current || "—"}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    icon={<Crosshair size={12} />}
                    loading={settingTrims}
                    onClick={handleSetTrims}
                  >
                    Confirm
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setShowTrimPreview(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Crosshair size={12} />}
                  disabled={!hasRcData}
                  onClick={() => setShowTrimPreview(true)}
                >
                  Set Trims to Current
                </Button>
                <span className="text-[10px] text-text-tertiary">
                  Sets Roll/Pitch/Yaw trims to live stick positions
                </span>
              </div>
            )}
            <div className="border-t border-border-default" />
          </>
        )}

        {/* ── Calibration Flow (2-step) ── */}
        {!calibrating ? (
          <>
            <p className="text-[10px] text-text-tertiary">
              2-step calibration: (1) move sticks to extremes, (2) center sticks to set trims.
            </p>
            {!hasRcData && (
              <p className="text-[10px] text-status-warning">
                No RC data received — ensure transmitter is on and bound.
              </p>
            )}
            <Button
              variant="secondary"
              size="sm"
              disabled={!hasRcData}
              onClick={() => {
                setCalMins(Array(RC_CHANNEL_COUNT).fill(2000));
                setCalMaxs(Array(RC_CHANNEL_COUNT).fill(1000));
                setCalStep(1);
                setCalibrating(true);
              }}
            >
              Start Calibration
            </Button>
          </>
        ) : calStep === 1 ? (
          <>
            <div className="p-2 bg-status-warning/10 border border-status-warning/20">
              <p className="text-[10px] text-status-warning font-medium">
                Step 1/2 — Move all sticks and switches to their extreme positions now.
              </p>
            </div>

            <div className="space-y-1">
              {channels.slice(0, RC_CHANNEL_COUNT).map((val, i) => (
                <div key={i} className="flex items-center gap-2 text-[10px] font-mono">
                  <span className="text-text-secondary w-6 text-right">CH{i + 1}</span>
                  <span className="text-text-tertiary w-10 text-right">{calMins[i]}</span>
                  <div className="flex-1 h-3 bg-bg-tertiary border border-border-default relative overflow-hidden">
                    <div
                      className="h-full bg-accent-primary/40 transition-all duration-75"
                      style={{
                        left: `${((calMins[i] - 800) / 1200) * 100}%`,
                        width: `${((calMaxs[i] - calMins[i]) / 1200) * 100}%`,
                        position: "absolute",
                      }}
                    />
                  </div>
                  <span className="text-text-tertiary w-10">{calMaxs[i]}</span>
                  <span className="text-text-primary w-10 text-right">{val}</span>
                </div>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={() => setCalStep(2)}
              >
                Next: Set Center
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => { setCalibrating(false); setCalStep(1); }}
              >
                Cancel
              </Button>
            </div>
          </>
        ) : (
          <>
            <div className="p-2 bg-accent-primary/10 border border-accent-primary/20">
              <p className="text-[10px] text-accent-primary font-medium">
                Step 2/2 — Return all sticks to center (neutral) position, then click Save.
              </p>
            </div>

            <div className="space-y-0.5">
              {channels.slice(0, Math.min(8, RC_CHANNEL_COUNT)).map((val, i) => {
                const currentTrim = getChannelTrim(i);
                const offset = val > 0 ? Math.abs(val - currentTrim) : 0;
                return (
                  <div key={i} className="flex items-center gap-2 text-[10px] font-mono">
                    <span className="text-text-secondary w-6 text-right">CH{i + 1}</span>
                    <span className="text-text-primary w-10 text-right">{val}</span>
                    <span className="text-text-tertiary">offset:</span>
                    <span className={offset > (getChannelDz(i)) ? "text-status-warning" : "text-status-success"}>
                      {offset}
                    </span>
                  </div>
                );
              })}
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                icon={<Save size={12} />}
                onClick={saveCalibration}
              >
                Save Calibration
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setCalStep(1)}
              >
                Back
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => { setCalibrating(false); setCalStep(1); }}
              >
                Cancel
              </Button>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
