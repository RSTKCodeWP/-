/**
 * @module command/shared/agent-gate-fallback
 * @description Shared mapping from a surface-gate result to the right fallback
 * for an agent action surface (System, Scripts, Plugins, Peripherals). Returns
 * the full pair page when there is no agent at all, the offline placeholder
 * (with Reconnect) when a paired agent dropped, the loading state while the
 * first heartbeat is pending, and null for ok/stale so the caller keeps showing
 * last-known content (stale beats a blank screen).
 * @license GPL-3.0-only
 */

import type { ReactNode } from "react";
import type { GateResult } from "@/hooks/use-surface-gate";
import { LinkUpPlaceholder } from "@/components/shared/link-up/LinkUpPlaceholder";
import { AgentDisconnectedPage } from "../AgentDisconnectedPage";

export function agentGateFallback(gate: GateResult): ReactNode | null {
  switch (gate.mode) {
    case "locked":
      return <AgentDisconnectedPage />;
    case "loading":
      return <LinkUpPlaceholder variant="loading" />;
    case "offline":
      return (
        <LinkUpPlaceholder
          variant="agent-offline"
          lastSeenLabel={gate.lastSeenLabel}
        />
      );
    default:
      // ok + stale: render content; stale data stays readable with overlays.
      return null;
  }
}
