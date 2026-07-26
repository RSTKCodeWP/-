"use client";

/**
 * @module SoftwareUpdateCard
 * @description System-tab card for the agent's OTA self-update. Shows the
 * current → available version, a live phase checklist (Download → Verify →
 * Install → Restart) with a determinate download bar, and check / install
 * actions — mirroring the `ados update` CLI experience. Polls the locally
 * paired agent's `GET /api/ota`; hides itself when the agent has no OTA surface
 * (or in cloud mode). Local-first per the connection model.
 * @license GPL-3.0-only
 */

import { useEffect, type ReactNode } from "react";
import {
  Download,
  CheckCircle2,
  Loader2,
  Circle,
  RefreshCw,
  AlertTriangle,
} from "lucide-react";

import {
  useAgentOtaStore,
  OTA_ACTIVE_STATES,
} from "@/stores/agent-ota-store";
import { CollapsibleSection } from "./shared";

const PHASES: ReadonlyArray<{ key: string; label: string }> = [
  { key: "downloading", label: "Download" },
  { key: "verifying", label: "Verify" },
  { key: "installing", label: "Install" },
  { key: "restarting", label: "Restart" },
];

function formatSpeed(bps: number): string {
  if (bps <= 0) return "";
  if (bps < 1_000_000) return `${(bps / 1_000).toFixed(0)} kB/s`;
  return `${(bps / 1_000_000).toFixed(1)} MB/s`;
}

export function SoftwareUpdateCard() {
  const available = useAgentOtaStore((s) => s.available);
  const state = useAgentOtaStore((s) => s.state);
  const refresh = useAgentOtaStore((s) => s.refresh);

  const active = state != null && (OTA_ACTIVE_STATES as readonly string[]).includes(state);

  // Poll the agent: faster while an update is in flight, gently otherwise.
  useEffect(() => {
    void refresh();
    const id = setInterval(() => void refresh(), active ? 1200 : 5000);
    return () => clearInterval(id);
  }, [refresh, active]);

  if (available !== true) return null;

  return (
    <CollapsibleSection title="Software Update" icon={Download}>
      <OtaBody />
    </CollapsibleSection>
  );
}

function OtaBody() {
  const state = useAgentOtaStore((s) => s.state);
  const currentVersion = useAgentOtaStore((s) => s.currentVersion);
  const pendingVersion = useAgentOtaStore((s) => s.pendingVersion);
  const downloadPercent = useAgentOtaStore((s) => s.downloadPercent);
  const downloadSpeedBps = useAgentOtaStore((s) => s.downloadSpeedBps);
  const busy = useAgentOtaStore((s) => s.busy);
  const error = useAgentOtaStore((s) => s.error);
  const check = useAgentOtaStore((s) => s.check);
  const install = useAgentOtaStore((s) => s.install);

  const activeIdx = state
    ? (OTA_ACTIVE_STATES as readonly string[]).indexOf(state)
    : -1;
  const updating = activeIdx >= 0 || busy;

  return (
    <div className="space-y-3 px-4 py-3">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs text-text-tertiary">Installed</p>
          <p className="text-sm font-mono text-text-primary">
            {currentVersion || "unknown"}
          </p>
        </div>
        {pendingVersion && (
          <div className="text-right">
            <p className="text-xs text-text-tertiary">Available</p>
            <p className="text-sm font-mono text-accent-primary">
              {pendingVersion}
            </p>
          </div>
        )}
      </div>

      {updating ? (
        <div className="space-y-1.5">
          {PHASES.map((phase, i) => {
            const done = activeIdx > i;
            const isActive = activeIdx === i;
            return (
              <div key={phase.key} className="flex items-center gap-2">
                <span className="w-4 h-4 flex items-center justify-center">
                  {done ? (
                    <CheckCircle2 size={14} className="text-status-success" />
                  ) : isActive ? (
                    <Loader2 size={14} className="text-accent-primary animate-spin" />
                  ) : (
                    <Circle size={12} className="text-text-tertiary" />
                  )}
                </span>
                <span className="text-sm text-text-secondary">{phase.label}</span>
                {isActive && phase.key === "downloading" && (
                  <span className="ml-auto text-xs text-text-tertiary tabular-nums">
                    {downloadPercent}%
                    {formatSpeed(downloadSpeedBps) &&
                      ` · ${formatSpeed(downloadSpeedBps)}`}
                  </span>
                )}
              </div>
            );
          })}
          {activeIdx === 0 && (
            <div className="h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
              <div
                className="h-full bg-accent-primary transition-all"
                style={{ width: `${downloadPercent}%` }}
              />
            </div>
          )}
        </div>
      ) : (
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-text-secondary">
            {pendingVersion ? "Update available" : "Up to date"}
          </p>
          <div className="flex items-center gap-2">
            {pendingVersion ? (
              <ActionButton onClick={() => void install()} disabled={busy}>
                Install {pendingVersion}
              </ActionButton>
            ) : (
              <ActionButton onClick={() => void check()} disabled={busy}>
                <RefreshCw size={13} />
                Check for updates
              </ActionButton>
            )}
          </div>
        </div>
      )}

      {error && (
        <p className="flex items-center gap-1.5 text-xs text-status-error">
          <AlertTriangle size={13} />
          {error}
        </p>
      )}
    </div>
  );
}

function ActionButton({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border border-border-default bg-bg-tertiary text-text-primary transition-colors hover:bg-bg-primary/40 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {children}
    </button>
  );
}
