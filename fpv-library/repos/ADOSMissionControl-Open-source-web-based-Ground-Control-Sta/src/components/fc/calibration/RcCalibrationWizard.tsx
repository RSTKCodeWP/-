"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { useToast } from "@/components/ui/toast";
import { useDroneManager } from "@/stores/drone-manager";
import { useTelemetryStore } from "@/stores/telemetry-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { RC_CAL_STEPS } from "./calibration-types";
import { RcChannelBar, RcCalSummaryTable } from "./RcChannelBar";

const RC_CHANNEL_COUNT = 8;
const RC_CHANNEL_LABELS = ["Roll", "Pitch", "Throttle", "Yaw", "Aux 1", "Aux 2", "Aux 3", "Aux 4"];
const RC_PWM_MIN = 800;
const RC_PWM_MAX = 2200;
const RC_CENTER_TOLERANCE = 100;
const RC_CENTER_VALUE = 1500;

type RcCalStep = "idle" | "center" | "move" | "confirm" | "saving" | "done" | "error";

interface RcChannelCapture { min: number; max: number; trim: number; }
function defaultCapture(): RcChannelCapture { return { min: RC_PWM_MAX, max: RC_PWM_MIN, trim: RC_CENTER_VALUE }; }

export function RcCalibrationWizard({ connected }: { connected: boolean }) {
  const getSelectedProtocol = useDroneManager((s) => s.getSelectedProtocol);
  const rcBuffer = useTelemetryStore((s) => s.rc);
  const telVersion = useTelemetryStore((s) => s._version);
  const { toast } = useToast();

  const [step, setStep] = useState<RcCalStep>("idle");
  const [captures, setCaptures] = useState<RcChannelCapture[]>(() => Array.from({ length: RC_CHANNEL_COUNT }, defaultCapture));
  const [errorMsg, setErrorMsg] = useState("");
  const [showTrimReset, setShowTrimReset] = useState(false);
  const [trimResetting, setTrimResetting] = useState(false);
  const capturesRef = useRef(captures);
  capturesRef.current = captures;

  const latestRc = useMemo(() => {
    const latest = rcBuffer.latest();
    return latest?.channels ?? Array(16).fill(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rcBuffer, telVersion]);

  useEffect(() => {
    if (step !== "move") return;
    setCaptures((prev) => {
      const next = [...prev];
      let changed = false;
      for (let i = 0; i < RC_CHANNEL_COUNT; i++) {
        const val = latestRc[i] ?? 0;
        if (val === 0) continue;
        const ch = { ...next[i] };
        if (val < ch.min) { ch.min = val; changed = true; }
        if (val > ch.max) { ch.max = val; changed = true; }
        next[i] = ch;
      }
      return changed ? next : prev;
    });
  }, [step, latestRc]);

  const handleStart = useCallback(() => { setStep("center"); setCaptures(Array.from({ length: RC_CHANNEL_COUNT }, defaultCapture)); setErrorMsg(""); }, []);

  const handleCenterConfirm = useCallback(() => {
    const offCenter: number[] = [];
    for (let i = 0; i < RC_CHANNEL_COUNT; i++) {
      const val = latestRc[i] ?? 0;
      if (val === 0) continue;
      if (Math.abs(val - RC_CENTER_VALUE) > RC_CENTER_TOLERANCE) offCenter.push(i + 1);
    }
    if (offCenter.length > 0 && latestRc[0] !== 0) { toast(`Channels ${offCenter.join(", ")} not centered. Center all sticks and try again.`, "error"); return; }
    setCaptures((prev) => {
      const next = [...prev];
      for (let i = 0; i < RC_CHANNEL_COUNT; i++) { const val = latestRc[i] ?? RC_CENTER_VALUE; if (val === 0) continue; next[i] = { ...next[i], trim: val }; }
      return next;
    });
    setStep("move");
  }, [latestRc, toast]);

  const handleMoveComplete = useCallback(() => {
    const caps = capturesRef.current;
    const narrow: number[] = [];
    for (let i = 0; i < 4; i++) { if (caps[i].max - caps[i].min < 200) narrow.push(i + 1); }
    if (narrow.length > 0) { toast(`Channels ${narrow.join(", ")} have narrow range (<200). Move sticks to full extent.`, "error"); return; }
    setStep("confirm");
  }, [toast]);

  const handleSave = useCallback(async () => {
    const protocol = getSelectedProtocol();
    if (!protocol) return;
    setStep("saving");
    try {
      for (let i = 0; i < RC_CHANNEL_COUNT; i++) {
        const ch = capturesRef.current[i]; const idx = i + 1;
        await protocol.setParameter(`RC${idx}_MIN`, ch.min);
        await protocol.setParameter(`RC${idx}_MAX`, ch.max);
        await protocol.setParameter(`RC${idx}_TRIM`, ch.trim);
      }
      await protocol.commitParamsToFlash();
      setStep("done"); toast("RC calibration saved to flash", "success");
    } catch { setStep("error"); setErrorMsg("Failed to write RC parameters"); toast("Failed to write RC parameters", "error"); }
  }, [getSelectedProtocol, toast]);

  const handleCancel = useCallback(() => { setStep("idle"); setCaptures(Array.from({ length: RC_CHANNEL_COUNT }, defaultCapture)); setErrorMsg(""); }, []);

  const handleResetTrims = useCallback(async () => {
    const protocol = getSelectedProtocol();
    if (!protocol) return;
    setTrimResetting(true);
    try {
      for (let i = 1; i <= RC_CHANNEL_COUNT; i++) await protocol.setParameter(`RC${i}_TRIM`, RC_CENTER_VALUE);
      await protocol.commitParamsToFlash();
      toast("RC trims reset to 1500 and saved to flash", "success");
    } catch { toast("Failed to reset RC trims", "error"); }
    finally { setTrimResetting(false); setShowTrimReset(false); }
  }, [getSelectedProtocol, toast]);

  const statusBadge = {
    idle: { label: "Ready", className: "bg-bg-tertiary text-text-tertiary" },
    center: { label: "Step 1/3", className: "bg-accent-primary/20 text-accent-primary" },
    move: { label: "Step 2/3", className: "bg-accent-primary/20 text-accent-primary" },
    confirm: { label: "Step 3/3", className: "bg-status-warning/20 text-status-warning" },
    saving: { label: "Saving", className: "bg-accent-primary/20 text-accent-primary" },
    done: { label: "Complete", className: "bg-status-success/20 text-status-success" },
    error: { label: "Failed", className: "bg-status-error/20 text-status-error" },
  } as const;

  const badge = statusBadge[step];
  const showCaptures = step === "move" || step === "confirm" || step === "done";

  return (
    <div className="border border-border-default bg-bg-secondary p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h3 className="text-sm font-medium text-text-primary">Radio Calibration</h3>
          <p className="text-xs text-text-tertiary mt-0.5">Calibrate RC transmitter stick endpoints and trims. Move all sticks and switches to full extent.</p>
        </div>
        <span className={cn("text-[10px] font-mono px-2 py-0.5 shrink-0", badge.className)}>{badge.label}</span>
      </div>

      {step === "idle" && (
        <div className="mb-4 bg-bg-tertiary/50 px-3 py-2.5">
          <p className="text-[10px] font-medium text-text-secondary mb-1.5">Before you start</p>
          <ol className="space-y-1">
            <li className="text-[10px] text-text-tertiary flex gap-1.5"><span className="text-text-secondary shrink-0">1.</span>Turn on RC transmitter and verify binding before starting</li>
            <li className="text-[10px] text-text-tertiary flex gap-1.5"><span className="text-text-secondary shrink-0">2.</span>Ensure all trims on transmitter are centered (no sub-trim)</li>
            <li className="text-[10px] text-text-tertiary flex gap-1.5"><span className="text-text-secondary shrink-0">3.</span>You will need to move ALL sticks and switches to their extremes</li>
          </ol>
        </div>
      )}

      {step === "center" && (
        <div className="mb-3 border border-accent-primary/20 bg-accent-primary/5 px-3 py-2.5">
          <p className="text-[10px] font-medium text-accent-primary">Step 1/3: {RC_CAL_STEPS[0].label}</p>
          <p className="text-[10px] text-text-tertiary mt-0.5">{RC_CAL_STEPS[0].description}</p>
        </div>
      )}
      {step === "move" && (
        <div className="mb-3 border border-accent-primary/20 bg-accent-primary/5 px-3 py-2.5">
          <p className="text-[10px] font-medium text-accent-primary">Step 2/3: {RC_CAL_STEPS[1].label}</p>
          <p className="text-[10px] text-text-tertiary mt-0.5">{RC_CAL_STEPS[1].description}</p>
        </div>
      )}
      {step === "confirm" && (
        <div className="mb-3 border border-status-warning/20 bg-status-warning/5 px-3 py-2.5">
          <p className="text-[10px] font-medium text-status-warning">Step 3/3: {RC_CAL_STEPS[2].label}</p>
          <p className="text-[10px] text-text-tertiary mt-0.5">{RC_CAL_STEPS[2].description} Click Save to write RC parameters.</p>
        </div>
      )}

      {step !== "idle" && (
        <div className="mb-4 space-y-1.5">
          {Array.from({ length: RC_CHANNEL_COUNT }, (_, i) => (
            <RcChannelBar key={i} label={RC_CHANNEL_LABELS[i]} channel={i + 1} value={latestRc[i] ?? 0}
              capturedMin={captures[i].min} capturedMax={captures[i].max} capturedTrim={captures[i].trim} showCaptures={showCaptures} />
          ))}
        </div>
      )}

      {(step === "confirm" || step === "done") && <RcCalSummaryTable captures={captures} channelLabels={RC_CHANNEL_LABELS} />}

      {step === "done" && <p className="text-[10px] font-mono text-status-success mb-3">RC calibration complete. Parameters saved to flash.</p>}
      {step === "error" && <p className="text-[10px] font-mono text-status-error mb-3">{errorMsg}</p>}
      {step === "saving" && <p className="text-[10px] font-mono text-text-tertiary mb-3">Writing RC parameters to flight controller...</p>}

      {showTrimReset && (
        <div className="mb-3 border border-status-warning/30 bg-status-warning/5 px-3 py-2.5">
          <p className="text-[10px] font-medium text-status-warning mb-1.5">Confirm Trim Reset</p>
          <p className="text-[10px] text-text-tertiary mb-2">This will set RC1_TRIM through RC8_TRIM to 1500 (center). This affects flight behavior and should only be done if trims are incorrect.</p>
          <div className="flex gap-2">
            <Button variant="danger" size="sm" onClick={handleResetTrims} loading={trimResetting} disabled={trimResetting}>Reset All Trims</Button>
            <Button variant="secondary" size="sm" onClick={() => setShowTrimReset(false)} disabled={trimResetting}>Cancel</Button>
          </div>
        </div>
      )}

      <div className="flex gap-2">
        {step === "idle" && (<><Button variant="primary" size="sm" onClick={handleStart} disabled={!connected}>Start</Button>
          <Button variant="secondary" size="sm" onClick={() => setShowTrimReset(true)} disabled={!connected || showTrimReset}>Reset Trims</Button></>)}
        {step === "center" && (<><Button variant="primary" size="sm" onClick={handleCenterConfirm}>Next</Button>
          <Button variant="danger" size="sm" onClick={handleCancel}>Cancel</Button></>)}
        {step === "move" && (<><Button variant="primary" size="sm" onClick={handleMoveComplete}>Next</Button>
          <Button variant="danger" size="sm" onClick={handleCancel}>Cancel</Button></>)}
        {step === "confirm" && (<><Button variant="primary" size="sm" onClick={handleSave}>Save</Button>
          <Button variant="danger" size="sm" onClick={handleCancel}>Cancel</Button></>)}
        {step === "saving" && <Button variant="secondary" size="sm" loading disabled>Saving...</Button>}
        {(step === "done" || step === "error") && <Button variant="primary" size="sm" onClick={handleStart}>{step === "done" ? "Re-calibrate" : "Retry"}</Button>}
      </div>
    </div>
  );
}
