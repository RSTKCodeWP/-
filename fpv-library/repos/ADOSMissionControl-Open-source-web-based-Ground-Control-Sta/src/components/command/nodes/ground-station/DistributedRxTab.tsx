"use client";

/**
 * @module DistributedRxTab
 * @description Command-tab home for the distributed receive role.
 * Polls /role and the role-specific WFB endpoints at 2 Hz while the
 * tab is visible. Pauses on document.hidden. Lifted from the prior
 * /hardware/distributed-rx route.
 * @license GPL-3.0-only
 */

import { useEffect } from "react";
import { useGroundStationStore } from "@/stores/ground-station-store";
import { useAgentConnectionStore } from "@/stores/agent-connection-store";
import { groundStationApiFromAgent } from "@/lib/api/ground-station-api";
import { DistributedRxPanel } from "@/components/hardware/DistributedRxPanel";
import { PageIntro } from "@/components/hardware/PageIntro";
import { HintChip } from "@/components/hardware/HintChip";
import { CloudModeLimitedNotice } from "@/components/command/shared/CloudModeLimitedNotice";

const POLL_INTERVAL_MS = 2000;

export function DistributedRxTab() {
  const agentUrl = useAgentConnectionStore((s) => s.agentUrl);
  const apiKey = useAgentConnectionStore((s) => s.apiKey);
  const loadRole = useGroundStationStore((s) => s.loadRole);
  const loadDistributedRx = useGroundStationStore((s) => s.loadDistributedRx);

  useEffect(() => {
    const api = groundStationApiFromAgent(agentUrl, apiKey);
    if (!api) return;
    let cancelled = false;
    const poll = async () => {
      if (cancelled || document.hidden) return;
      await loadRole(api);
      await loadDistributedRx(api);
    };
    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [agentUrl, apiKey, loadRole, loadDistributedRx]);

  const onCloudOnly = !agentUrl;

  return (
    <div className="flex flex-col">
      <PageIntro
        title="Distributed RX"
        description="Combine multiple ground nodes into one radio receive surface. Set this node's role and watch streams merge."
        trailing={
          <HintChip>Direct = solo. Relay forwards. Receiver combines.</HintChip>
        }
      />
      {onCloudOnly ? <CloudModeLimitedNotice feature="distributedRx" /> : null}
      <DistributedRxPanel />
    </div>
  );
}
