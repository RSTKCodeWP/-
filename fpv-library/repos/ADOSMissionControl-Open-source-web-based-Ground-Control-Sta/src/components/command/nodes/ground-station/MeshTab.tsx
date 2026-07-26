"use client";

/**
 * @module MeshTab
 * @description Command-tab home for batman-adv mesh health,
 * neighbours, gateways, and the log aggregator stub. Polls
 * /mesh/* at 3 s while visible. Pauses on document.hidden. Live
 * updates from /ws/mesh patch the slice without needing the poll,
 * so the cadence here is just a recovery from missed frames.
 * Lifted from the prior /hardware/mesh route.
 * @license GPL-3.0-only
 */

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { useGroundStationStore } from "@/stores/ground-station-store";
import { useAgentConnectionStore } from "@/stores/agent-connection-store";
import { groundStationApiFromAgent } from "@/lib/api/ground-station-api";
import { MeshHealthCard } from "@/components/hardware/MeshHealthCard";
import { MeshNeighborsTable } from "@/components/hardware/MeshNeighborsTable";
import { MeshGatewaysTable } from "@/components/hardware/MeshGatewaysTable";
import { RoleChangeCard } from "@/components/hardware/RoleChangeCard";
import { PageIntro } from "@/components/hardware/PageIntro";
import { HintChip } from "@/components/hardware/HintChip";
import { Button } from "@/components/ui/button";
import { CloudModeLimitedNotice } from "@/components/command/shared/CloudModeLimitedNotice";

const POLL_INTERVAL_MS = 3000;

export function MeshTab() {
  const t = useTranslations("hardware.mesh");
  const agentUrl = useAgentConnectionStore((s) => s.agentUrl);
  const apiKey = useAgentConnectionStore((s) => s.apiKey);
  const loadRole = useGroundStationStore((s) => s.loadRole);
  const loadMesh = useGroundStationStore((s) => s.loadMesh);
  const role = useGroundStationStore((s) => s.role.info?.current ?? "direct");
  const meshError = useGroundStationStore((s) => s.mesh.error);

  useEffect(() => {
    const api = groundStationApiFromAgent(agentUrl, apiKey);
    if (!api) return;
    let cancelled = false;
    const poll = async () => {
      if (cancelled || document.hidden) return;
      await loadRole(api);
      await loadMesh(api);
    };
    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [agentUrl, apiKey, loadRole, loadMesh]);

  if (role === "direct") {
    return (
      <div className="flex flex-col">
        <PageIntro
          title="Mesh"
          description="Self-healing wireless mesh between ground nodes. Watch neighbours, gateways, and route health."
          trailing={
            <HintChip>Gateway election picks the node with the best cloud uplink.</HintChip>
          }
        />
        <div className="flex flex-col gap-4">
          <div className="text-text-secondary">{t("emptyDirect")}</div>
          <RoleChangeCard variant="empty" />
        </div>
      </div>
    );
  }

  const retry = () => {
    const api = groundStationApiFromAgent(agentUrl, apiKey);
    if (api) void loadMesh(api);
  };

  const onCloudOnly = !agentUrl;

  return (
    <div className="flex flex-col">
      <PageIntro
        title="Mesh"
        description="Self-healing wireless mesh between ground nodes. Watch neighbours, gateways, and route health."
        trailing={
          <HintChip>Gateway election picks the node with the best cloud uplink.</HintChip>
        }
      />
      {onCloudOnly ? <CloudModeLimitedNotice feature="mesh" /> : null}
      <div className="flex flex-col gap-4">
      <MeshHealthCard />
      <MeshNeighborsTable />
      <MeshGatewaysTable />
      {meshError ? (
        <div
          className="flex items-center justify-between gap-3 rounded-sm border border-status-error bg-status-error/10 px-3 py-2 text-sm text-status-error"
          role="alert"
          aria-live="polite"
        >
          <span>{meshError}</span>
          <Button size="sm" variant="ghost" onClick={retry}>
            Retry
          </Button>
        </div>
      ) : null}
      </div>
    </div>
  );
}
