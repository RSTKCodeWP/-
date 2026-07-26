"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { Cpu } from "lucide-react";
import {
  useDroneCanNodeStore,
  type NodeEntry,
} from "@/stores/dronecan/node-store";
import {
  HEALTH_OK,
  HEALTH_WARNING,
  HEALTH_ERROR,
  HEALTH_CRITICAL,
  MODE_OPERATIONAL,
  MODE_INITIALIZATION,
  MODE_MAINTENANCE,
  MODE_SOFTWARE_UPDATE,
  MODE_OFFLINE,
} from "@/lib/dronecan/dsdl/node-status";
import { isDemoMode } from "@/lib/utils";

interface Props {
  selectedNodeId: number | null;
  onSelect: (nodeId: number) => void;
  slcanActive: boolean;
}

const DEMO_NODES: ReadonlyArray<{
  nodeId: number;
  name: string;
  swVersion: string;
  mode: number;
  health: number;
}> = [
  { nodeId: 124, name: "MatekL431-GPS", swVersion: "1.7.0", mode: MODE_OPERATIONAL, health: HEALTH_OK },
  { nodeId: 125, name: "MatekL431-Airspeed", swVersion: "1.6.2", mode: MODE_OPERATIONAL, health: HEALTH_OK },
  { nodeId: 127, name: "f303-MatekGPS", swVersion: "1.5.1", mode: MODE_MAINTENANCE, health: HEALTH_WARNING },
];

function modeLabelKey(mode: number): string {
  switch (mode) {
    case MODE_OPERATIONAL: return "state.operational";
    case MODE_INITIALIZATION: return "state.initialization";
    case MODE_MAINTENANCE: return "state.maintenance";
    case MODE_SOFTWARE_UPDATE: return "state.softwareUpdate";
    case MODE_OFFLINE: return "state.offline";
    default: return "state.operational";
  }
}

function healthSymbol(health: number): { glyph: string; cls: string; key: string } {
  switch (health) {
    case HEALTH_OK: return { glyph: "●", cls: "text-status-success", key: "health.ok" };
    case HEALTH_WARNING: return { glyph: "◐", cls: "text-status-warning", key: "health.warning" };
    case HEALTH_ERROR: return { glyph: "◑", cls: "text-status-error", key: "health.error" };
    case HEALTH_CRITICAL: return { glyph: "✖", cls: "text-status-error", key: "health.critical" };
    default: return { glyph: "●", cls: "text-text-tertiary", key: "health.ok" };
  }
}

interface Row {
  nodeId: number;
  name: string;
  swVersion: string;
  mode: number;
  health: number;
}

function rowFromEntry(entry: NodeEntry): Row {
  const ni = entry.nodeInfo;
  const sv = ni?.software_version;
  return {
    nodeId: entry.nodeId,
    name: ni?.name || `node ${entry.nodeId}`,
    swVersion: sv ? `${sv.major}.${sv.minor}` : "—",
    mode: entry.lastStatus?.mode ?? MODE_OPERATIONAL,
    health: entry.lastStatus?.health ?? HEALTH_OK,
  };
}

export function FirmwareApPeriphNodeTable({ selectedNodeId, onSelect, slcanActive }: Props) {
  const t = useTranslations("flashTool.apPeriph");
  const nodesMap = useDroneCanNodeStore((s) => s.nodes);

  const rows = useMemo<Row[]>(() => {
    if (isDemoMode()) {
      return DEMO_NODES.map((n) => ({ ...n }));
    }
    return Array.from(nodesMap.values())
      .sort((a, b) => a.nodeId - b.nodeId)
      .map(rowFromEntry);
  }, [nodesMap]);

  return (
    <div className="bg-bg-secondary border border-border-default p-4 space-y-3">
      <h2 className="text-xs font-semibold text-text-primary flex items-center gap-2">
        <Cpu size={14} />
        {t("target.title")}
      </h2>

      {rows.length === 0 ? (
        <p className="text-[10px] text-text-tertiary">
          {slcanActive ? t("target.noNodesActive") : t("target.noNodes")}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[10px] text-text-secondary">
            <thead className="text-text-tertiary uppercase">
              <tr>
                <th className="text-left py-1.5 pr-2 font-normal w-8"></th>
                <th className="text-left py-1.5 pr-2 font-normal">{t("target.column.id")}</th>
                <th className="text-left py-1.5 pr-2 font-normal">{t("target.column.name")}</th>
                <th className="text-left py-1.5 pr-2 font-normal">{t("target.column.version")}</th>
                <th className="text-left py-1.5 pr-2 font-normal">{t("target.column.state")}</th>
                <th className="text-left py-1.5 font-normal">{t("target.column.health")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const h = healthSymbol(row.health);
                const isSelected = selectedNodeId === row.nodeId;
                return (
                  <tr
                    key={row.nodeId}
                    onClick={() => onSelect(row.nodeId)}
                    className={`cursor-pointer border-t border-border-default hover:bg-bg-tertiary ${
                      isSelected ? "bg-accent-primary/10" : ""
                    }`}
                  >
                    <td className="py-1.5 pr-2 align-middle">
                      <input
                        type="radio"
                        checked={isSelected}
                        onChange={() => onSelect(row.nodeId)}
                        className="accent-accent-primary"
                        aria-label={t("target.selectAria", { nodeId: row.nodeId })}
                      />
                    </td>
                    <td className="py-1.5 pr-2 font-mono">{row.nodeId}</td>
                    <td className="py-1.5 pr-2">{row.name}</td>
                    <td className="py-1.5 pr-2 font-mono">{row.swVersion}</td>
                    <td className="py-1.5 pr-2">{t(modeLabelKey(row.mode))}</td>
                    <td className={`py-1.5 ${h.cls}`}>
                      <span className="mr-1">{h.glyph}</span>
                      {t(h.key)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
