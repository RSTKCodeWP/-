"use client";

/**
 * @module ConfigErrorPanel
 * @description Red banner on the Health surface listing services whose config
 * file failed to parse on the agent (the service kept running on built-in
 * defaults). Renders nothing when every config loaded cleanly, so a healthy
 * node shows no banner.
 * @license GPL-3.0-only
 */

import { AlertTriangle } from "lucide-react";
import { useAgentSystemStore } from "@/stores/agent-system-store";

export function ConfigErrorPanel() {
  const configErrors = useAgentSystemStore((s) => s.configErrors);

  if (configErrors.length === 0) return null;

  return (
    <div className="border border-status-error/40 rounded-lg bg-status-error/10 p-4">
      <div className="flex items-center gap-2 mb-3">
        <AlertTriangle size={16} className="text-status-error shrink-0" />
        <h3 className="text-xs font-semibold uppercase tracking-wider text-status-error flex-1">
          Configuration {configErrors.length === 1 ? "error" : "errors"}
        </h3>
        <span className="text-[10px] text-status-error bg-status-error/10 px-1.5 py-0.5 rounded">
          {configErrors.length}
        </span>
      </div>
      <p className="text-[11px] text-text-tertiary mb-3">
        A service could not parse its config file and is running on built-in
        defaults. Fix the config on the agent and restart the service.
      </p>
      <div className="space-y-2">
        {configErrors.map((entry) => (
          <div
            key={entry.service}
            className="rounded bg-bg-primary/60 border border-status-error/20 px-3 py-2"
          >
            <p className="text-xs font-mono font-semibold text-status-error">
              {entry.service}
            </p>
            <p className="text-[11px] text-text-secondary font-mono break-all mt-0.5">
              {entry.error}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
