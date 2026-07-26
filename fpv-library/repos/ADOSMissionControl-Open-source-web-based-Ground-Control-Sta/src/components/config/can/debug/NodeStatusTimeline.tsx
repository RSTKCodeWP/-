"use client";

/**
 * @module NodeStatusTimeline
 * @description Per-node timeline of mode + health + uptime restart marks
 * over the last 60 NodeStatus samples. Horizontal lanes one per mode value,
 * filled segments where the node was in that mode. Below each mode lane:
 * health dots at each sample point. Above the lanes: small vertical tick
 * marks where `uptime_sec` decreased between samples (a restart event).
 *
 * Falls back to a "waiting for broadcasts" hint when no history exists yet.
 * When mounted with no `nodeId`, the panel renders a compact picker that
 * auto-selects the lowest-numbered online node.
 *
 * @license GPL-3.0-only
 */

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Select } from "@/components/ui/select";
import {
  useDroneCanNodeStore,
  type NodeEntry,
} from "@/stores/dronecan/node-store";
import type { NodeStatus } from "@/lib/dronecan/dsdl/node-status";

interface NodeStatusTimelineProps {
  nodeId?: number;
}

const MODES: Array<{ value: number; key: "operational" | "initialization" | "maintenance" | "software_update" | "offline" }> = [
  { value: 0, key: "operational" },
  { value: 1, key: "initialization" },
  { value: 2, key: "maintenance" },
  { value: 3, key: "software_update" },
  { value: 7, key: "offline" },
];

function healthColorClass(h: number): string {
  if (h === 0) return "bg-status-success";
  if (h === 1) return "bg-status-warning";
  return "bg-status-error";
}

function restartIndices(history: ReadonlyArray<NodeStatus>): number[] {
  const out: number[] = [];
  for (let i = 1; i < history.length; i++) {
    const prev = history[i - 1].uptime_sec;
    const cur = history[i].uptime_sec;
    if (cur < prev) out.push(i);
  }
  return out;
}

export function NodeStatusTimeline({ nodeId: explicitId }: NodeStatusTimelineProps = {}) {
  const t = useTranslations("canConfig.debug.nodeStatusTimeline");
  const tMode = useTranslations("canConfig.debug.nodeStatusTimeline.mode");

  const nodesMap = useDroneCanNodeStore((s) => s.nodes);
  const version = useDroneCanNodeStore((s) => s._version);

  const nodes = useMemo(() => {
    const list = Array.from(nodesMap.values());
    list.sort((a, b) => a.nodeId - b.nodeId);
    return list;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodesMap, version]);

  const [selected, setSelected] = useState<number | null>(explicitId ?? null);

  useEffect(() => {
    if (explicitId !== undefined) {
      setSelected(explicitId);
      return;
    }
    if (selected === null && nodes.length > 0) {
      setSelected(nodes[0].nodeId);
    }
  }, [explicitId, nodes, selected]);

  const node: NodeEntry | undefined =
    selected !== null ? nodesMap.get(selected) : undefined;
  const history = node?.statusHistory ?? [];
  const restarts = useMemo(() => restartIndices(history), [history]);
  const slots = 60;
  // Pad the rendered lane to a stable width: most recent samples to the
  // right, empty cells on the left when the history is short.
  const padding = Math.max(0, slots - history.length);

  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-between px-2 py-1.5 border-b border-border-default">
        <span className="text-[10px] uppercase tracking-wider font-semibold text-text-secondary">
          {t("title")}
        </span>
        {explicitId === undefined && nodes.length > 0 && (
          <Select
            value={selected !== null ? String(selected) : ""}
            options={nodes.map((n) => ({
              value: String(n.nodeId),
              label: `${n.nodeId} · ${n.nodeInfo?.name ?? "—"}`,
            }))}
            onChange={(v) => setSelected(Number(v))}
            className="w-44"
          />
        )}
      </div>

      <div className="px-2 py-2" data-testid="node-status-timeline-body">
        {history.length === 0 ? (
          <div className="text-center py-4 text-[11px] text-text-tertiary">
            {t("waiting")}
          </div>
        ) : (
          <>
            {/* Restart tick row */}
            <div
              className="grid gap-px h-2 mb-1"
              style={{ gridTemplateColumns: "repeat(60, minmax(0, 1fr))" }}
              data-testid="node-status-timeline-restart-row"
            >
              {Array.from({ length: padding }).map((_, i) => (
                <span key={`rp-${i}`} />
              ))}
              {history.map((_, i) => (
                <span
                  key={`r-${i}`}
                  className={
                    restarts.includes(i)
                      ? "bg-accent-primary h-2 w-px mx-auto"
                      : ""
                  }
                  data-restart={restarts.includes(i) ? "true" : "false"}
                />
              ))}
            </div>

            {/* Mode lanes */}
            {MODES.map((m) => (
              <div
                key={m.value}
                className="grid grid-cols-[110px_1fr] gap-2 mb-0.5"
              >
                <span className="text-[10px] font-mono text-text-tertiary truncate">
                  {tMode(m.key)}
                </span>
                <div
                  className="grid gap-px h-2"
                  style={{ gridTemplateColumns: "repeat(60, minmax(0, 1fr))" }}
                >
                  {Array.from({ length: padding }).map((_, i) => (
                    <span key={`p-${m.value}-${i}`} />
                  ))}
                  {history.map((status, i) => (
                    <span
                      key={`${m.value}-${i}`}
                      className={
                        status.mode === m.value ? "bg-accent-primary/40" : ""
                      }
                    />
                  ))}
                </div>
              </div>
            ))}

            {/* Health dots */}
            <div className="grid grid-cols-[110px_1fr] gap-2 mt-2">
              <span className="text-[10px] font-mono text-text-tertiary">health</span>
              <div className="grid grid-cols-60 gap-px h-2">
                {Array.from({ length: padding }).map((_, i) => (
                  <span key={`hp-${i}`} />
                ))}
                {history.map((status, i) => (
                  <span
                    key={`h-${i}`}
                    className={`${healthColorClass(status.health)} rounded-full w-1 h-1 mx-auto`}
                  />
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
