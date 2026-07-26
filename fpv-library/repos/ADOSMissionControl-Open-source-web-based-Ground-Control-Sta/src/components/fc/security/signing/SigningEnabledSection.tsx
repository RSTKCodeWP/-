"use client";

/**
 * @module components/fc/security/signing/SigningEnabledSection
 * @description Rendered when this browser holds a signing key. Shows status,
 * key fingerprint, cloud sync row, action buttons, and the history + debug
 * sub-sections.
 */

import { Lock, Shield, RotateCw, Trash2, AlertTriangle, KeyRound, Cloud, CloudOff } from "lucide-react";
import type { DroneSigningState } from "@/stores/signing-store";
import { KeyAgeNudge } from "../KeyAgeNudge";
import { SigningHistorySection } from "../SigningHistorySection";
import { SigningDebugSection } from "../SigningDebugSection";
import { isCloudSigningKeySyncEnabled } from "@/lib/api/signing-cloud-sync";

export interface SigningEnabledSectionProps {
  droneId: string;
  state: DroneSigningState;
  busy: boolean;
  error: string | null;
  cloudSyncIntent: boolean;
  cloudRowPresent: boolean;
  cloudSyncBusy: boolean;
  cloudSyncError: string | null;
  isAuthenticated: boolean;
  authLoading: boolean;
  onRotate: () => void;
  onRequireToggle: () => void;
  onDisable: () => void;
  onExport: () => void;
  onCloudSyncToggle: () => void;
}

export function SigningEnabledSection({
  droneId,
  state,
  busy,
  error,
  cloudSyncIntent,
  cloudRowPresent,
  cloudSyncBusy,
  cloudSyncError,
  isAuthenticated,
  authLoading,
  onRotate,
  onRequireToggle,
  onDisable,
  onExport,
  onCloudSyncToggle,
}: SigningEnabledSectionProps) {
  const enrolled = state.enrollmentState === "enrolled";
  const required = state.requireOnFc === true;
  const cloudSyncAvailable = isCloudSigningKeySyncEnabled();

  return (
    <div
      className={`border p-4 space-y-3 ${required ? "border-status-error/40 bg-status-error/5" : "border-border-default bg-bg-secondary"}`}
    >
      {required && (
        <div
          role="note"
          className="flex items-center gap-2 text-xs font-medium text-status-error border border-status-error/40 bg-status-error/10 px-3 py-2"
        >
          <Shield size={12} aria-hidden="true" />
          Enforcing signature verification. Unsigned commands will be rejected by the flight controller.
        </div>
      )}
      <KeyAgeNudge
        droneId={droneId}
        enrolledAt={state.enrolledAt}
        onRotate={onRotate}
        busy={busy}
      />
      <div className="flex items-center gap-2 text-text-primary">
        <Lock size={16} aria-hidden="true" className={required ? "text-status-error" : "text-status-success"} />
        <span className="font-medium">
          {required ? "Signing enabled, require mode on" : "Signing enabled"}
        </span>
      </div>
      <dl className="text-sm grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-text-secondary">
        <dt className="text-text-tertiary">Key fingerprint</dt>
        <dd className="font-mono">{state.keyId ?? "(unknown)"}</dd>
        <dt className="text-text-tertiary">Enrolled</dt>
        <dd>{state.enrolledAt ?? "(unknown)"}</dd>
        <dt className="text-text-tertiary">FC status</dt>
        <dd>
          {enrolled
            ? (required ? "Rejecting unsigned commands" : "Accepting signed and unsigned")
            : state.enrollmentState}
        </dd>
      </dl>
      {/* Cloud sync row. Disabled when user is signed out. */}
      <div className="border-t border-border-default pt-3 space-y-2">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2">
            {cloudSyncIntent && cloudRowPresent ? (
              <Cloud size={14} aria-hidden="true" className="text-accent-primary mt-0.5" />
            ) : (
              <CloudOff size={14} aria-hidden="true" className="text-text-tertiary mt-0.5" />
            )}
            <div>
              <p className="text-sm font-medium text-text-primary">Sync to cloud</p>
              <p className="text-xs text-text-tertiary">
                {!isAuthenticated
                  ? "Sign in to enable cloud key sync across devices."
                  : !cloudSyncAvailable
                    ? "Cloud key sync is disabled until encrypted storage is available."
                  : cloudSyncIntent && !cloudRowPresent
                    ? "Will sync on next rotation. Click Rotate key to upload the current key now."
                    : "Share this key with your other signed-in browsers."}
              </p>
            </div>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={cloudSyncIntent}
            aria-label={cloudSyncIntent ? "Turn cloud sync off" : "Turn cloud sync on"}
            disabled={
              !isAuthenticated ||
              authLoading ||
              cloudSyncBusy ||
              (!cloudSyncIntent && !cloudSyncAvailable)
            }
            onClick={onCloudSyncToggle}
            className={`relative inline-flex h-5 w-9 shrink-0 items-center border transition-colors disabled:opacity-40 ${cloudSyncIntent ? "bg-accent-primary border-accent-primary" : "bg-bg-primary border-border-default"}`}
          >
            <span
              className={`inline-block h-3 w-3 transform bg-white transition-transform ${cloudSyncIntent ? "translate-x-5" : "translate-x-1"}`}
            />
          </button>
        </div>
        {cloudSyncError && (
          <p role="alert" className="text-xs text-status-error">
            {cloudSyncError}
          </p>
        )}
      </div>
      {error && (
        <div
          className="flex items-start gap-2 text-sm text-status-error"
          role="alert"
        >
          <AlertTriangle size={14} className="mt-0.5" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}
      <div className="flex gap-2 flex-wrap">
        <button
          type="button"
          className="px-3 py-1.5 text-sm border border-border-default hover:bg-bg-tertiary disabled:opacity-50 inline-flex items-center gap-1.5"
          onClick={onRequireToggle}
          disabled={busy}
        >
          <Shield size={14} aria-hidden="true" />
          {required ? "Allow unsigned commands" : "Require signed commands"}
        </button>
        <button
          type="button"
          className="px-3 py-1.5 text-sm border border-border-default hover:bg-bg-tertiary disabled:opacity-50 inline-flex items-center gap-1.5"
          onClick={onRotate}
          disabled={busy}
        >
          <RotateCw size={14} aria-hidden="true" />
          Rotate key
        </button>
        <button
          type="button"
          className="px-3 py-1.5 text-sm border border-border-default hover:bg-bg-tertiary disabled:opacity-50 inline-flex items-center gap-1.5"
          onClick={onExport}
          disabled={busy}
        >
          <KeyRound size={14} aria-hidden="true" />
          Export key
        </button>
        <button
          type="button"
          className="px-3 py-1.5 text-sm border border-status-error/40 text-status-error hover:bg-status-error/10 disabled:opacity-50 inline-flex items-center gap-1.5"
          onClick={onDisable}
          disabled={busy}
        >
          <Trash2 size={14} aria-hidden="true" />
          Disable signing
        </button>
      </div>
      <SigningHistorySection droneId={droneId} />
      <SigningDebugSection droneId={droneId} />
    </div>
  );
}
