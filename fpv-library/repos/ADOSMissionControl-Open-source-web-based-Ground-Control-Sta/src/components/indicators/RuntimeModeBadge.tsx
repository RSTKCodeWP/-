/**
 * @module RuntimeModeBadge
 * @description Compact pill showing how the selected agent's systems
 * services are running: "native" (compiled binary), "hybrid" (mixed
 * native + interpreted fallback), or "packaged" (distributed package
 * build). Renders only when the agent reports a known runtime mode;
 * stays hidden otherwise (legacy heartbeats, agents that don't report
 * the field, or an unrecognized value).
 * @license GPL-3.0-only
 */
"use client";

import { useAgentCapabilitiesStore } from "@/stores/agent-capabilities-store";
import { Tooltip } from "@/components/ui/tooltip";

const RUNTIME_MODE_LABELS: Record<"native" | "hybrid" | "packaged", string> = {
  native: "NATIVE",
  hybrid: "HYBRID",
  packaged: "PACKAGED",
};

const RUNTIME_MODE_TOOLTIPS: Record<
  "native" | "hybrid" | "packaged",
  string
> = {
  native: "Agent systems services running as the native binary",
  hybrid: "Agent systems services running a mix of native and fallback",
  packaged: "Agent systems services running the packaged build",
};

export function RuntimeModeBadge() {
  const runtimeMode = useAgentCapabilitiesStore((s) => s.runtimeMode);

  if (runtimeMode === undefined) return null;

  const isNative = runtimeMode === "native";

  return (
    <Tooltip content={RUNTIME_MODE_TOOLTIPS[runtimeMode]}>
      <div
        role="status"
        aria-label={`Agent runtime mode: ${RUNTIME_MODE_TOOLTIPS[runtimeMode]}`}
        className={
          "flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono border " +
          (isNative
            ? "bg-status-success/10 border-status-success/30 text-status-success"
            : "bg-bg-tertiary border-border-default text-text-secondary")
        }
      >
        <span>{RUNTIME_MODE_LABELS[runtimeMode]}</span>
      </div>
    </Tooltip>
  );
}
