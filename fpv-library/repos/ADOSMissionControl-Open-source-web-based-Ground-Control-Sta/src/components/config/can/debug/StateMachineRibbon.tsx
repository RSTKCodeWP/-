"use client";

/**
 * @module StateMachineRibbon
 * @description Horizontal pill chain rendering the OTA state machine for
 * DroneCAN firmware update. Each pill shows the canonical step name and the
 * elapsed time spent inside that state (or current percent for the active
 * pill). The active pill pulses. Failed and aborted states render red with
 * an inline reason. When the orchestrator is idle the ribbon collapses to a
 * single sentence.
 *
 * @license GPL-3.0-only
 */

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import {
  useDroneCanFlashStore,
  type OtaState,
  type OtaTransition,
} from "@/stores/dronecan";

/** Pill ordering, left to right. */
const STEPS = ["arm", "begin", "transfer", "reboot", "verify", "done"] as const;
type StepKey = (typeof STEPS)[number];

/** Map an OTA state to a step key (or null when the state has no pill). */
function stateToStep(state: OtaState): StepKey | null {
  switch (state) {
    case "ARMING":
      return "arm";
    case "BEGIN_SENT":
      return "begin";
    case "TRANSFERRING":
      return "transfer";
    case "REBOOTING":
      return "reboot";
    case "VERIFYING":
      return "verify";
    case "DONE":
      return "done";
    case "IDLE":
    case "ABORTED":
    case "FAILED":
      return null;
  }
}

/** Compute milliseconds spent in each step from the transition log. */
function elapsedByStep(
  transitions: ReadonlyArray<OtaTransition>,
  current: OtaState,
  now: number,
): Map<StepKey, number> {
  const out = new Map<StepKey, number>();
  for (let i = 0; i < transitions.length; i++) {
    const t = transitions[i];
    const step = stateToStep(t.to);
    if (!step) continue;
    const end = i + 1 < transitions.length ? transitions[i + 1].t : now;
    out.set(step, (out.get(step) ?? 0) + Math.max(0, end - t.t));
  }
  // If we're sitting in a state but never logged a transition (e.g. the first
  // tick lands during ARMING before any prior state recorded a row), make sure
  // the active step still has a baseline of 0 ms so the pill renders.
  const cur = stateToStep(current);
  if (cur && !out.has(cur)) out.set(cur, 0);
  return out;
}

function fmtMs(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const rem = Math.round(s - m * 60);
  return `${m}m${String(rem).padStart(2, "0")}s`;
}

/** Estimate seconds remaining over the last 5 chunks. */
function computeEtaSeconds(
  transitions: ReadonlyArray<OtaTransition>,
  bytesSent: number,
  bytesTotal: number,
): number | null {
  if (bytesTotal <= 0 || bytesSent <= 0 || bytesSent >= bytesTotal) return null;
  // Use elapsed since transfer started as a smoothing window. Last 5 chunks
  // are not separately tracked in the snapshot, so use the broader window.
  const transferStart = [...transitions]
    .reverse()
    .find((t) => t.to === "TRANSFERRING");
  if (!transferStart) return null;
  const elapsedMs = Date.now() - transferStart.t;
  if (elapsedMs <= 0) return null;
  const bytesPerMs = bytesSent / elapsedMs;
  if (bytesPerMs <= 0) return null;
  const remaining = bytesTotal - bytesSent;
  return remaining / bytesPerMs / 1000;
}

function fmtEta(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds - m * 60);
  return `${m}m${String(s).padStart(2, "0")}s`;
}

export function StateMachineRibbon() {
  const t = useTranslations("canConfig.debug.stateRibbon");
  const tDebug = useTranslations("canConfig.debug");
  const state = useDroneCanFlashStore((s) => s.state);
  const percent = useDroneCanFlashStore((s) => s.percent);
  const bytesSent = useDroneCanFlashStore((s) => s.bytesSent);
  const bytesTotal = useDroneCanFlashStore((s) => s.bytesTotal);
  const errorMessage = useDroneCanFlashStore((s) => s.errorMessage);
  const transitions = useDroneCanFlashStore((s) => s.transitionLog);
  const version = useDroneCanFlashStore((s) => s._version);

  const elapsed = useMemo(
    () => elapsedByStep(transitions, state, Date.now()),
    // version forces recompute on each snapshot push
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [transitions, state, version],
  );

  const activeStep = stateToStep(state);
  const failed = state === "FAILED" || state === "ABORTED";

  if (state === "IDLE") {
    return (
      <div className="text-xs text-text-tertiary px-2 py-1.5">
        {tDebug("noFlash")}
      </div>
    );
  }

  const eta = computeEtaSeconds(transitions, bytesSent, bytesTotal);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1 overflow-x-auto">
        {STEPS.map((step, i) => {
          const isActive = activeStep === step;
          const hasReached = elapsed.has(step) || isActive;
          const isFailedHere = failed && activeStep === null && i === STEPS.length - 1;
          const ms = elapsed.get(step) ?? 0;
          return (
            <div key={step} className="flex items-center">
              <div
                className={cn(
                  "px-2 py-1 rounded font-mono text-[10px] uppercase tracking-wider border whitespace-nowrap",
                  isActive && !failed && "border-accent-primary text-accent-primary bg-accent-primary/10 animate-pulse",
                  !isActive && hasReached && !failed && "border-status-success/40 text-status-success",
                  !hasReached && "border-border-default text-text-tertiary",
                  isFailedHere && "border-status-error text-status-error",
                  failed && hasReached && "border-status-error/60 text-status-error",
                )}
                title={ms > 0 ? fmtMs(ms) : undefined}
                data-step={step}
                data-active={isActive ? "true" : "false"}
              >
                <span className="font-semibold">{t(step)}</span>
                {isActive && !failed && (
                  <span className="ml-1.5 text-[10px] text-text-secondary">
                    {Math.round(percent)}%
                  </span>
                )}
                {!isActive && hasReached && ms > 0 && (
                  <span className="ml-1.5 text-[10px] text-text-tertiary">
                    {fmtMs(ms)}
                  </span>
                )}
              </div>
              {i < STEPS.length - 1 && (
                <span
                  className={cn(
                    "mx-0.5 w-2 h-px",
                    hasReached ? "bg-status-success/40" : "bg-border-default",
                    failed && hasReached && "bg-status-error/40",
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

      {failed && errorMessage && (
        <div className="text-[11px] text-status-error font-mono px-2">
          {state === "ABORTED" ? t("aborted") : t("failed")}: {errorMessage}
        </div>
      )}

      <div className="flex items-center justify-between text-[11px] font-mono px-2 text-text-tertiary">
        <span>
          {Math.round(percent)}% · {bytesSent.toLocaleString()}/{bytesTotal.toLocaleString()}
        </span>
        <span>ETA {fmtEta(eta)}</span>
      </div>
    </div>
  );
}
