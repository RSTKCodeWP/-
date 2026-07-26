"use client";

/**
 * @module fc/firmware/agent-stages/TargetBoardCard
 * @description Top card of the ADOS Agent flash flow. Shows the board
 * picker (filtered to boards that ship the chosen stack), an offline
 * catalog pill when the manifest came from the embedded fallback,
 * and a per-board SoC + arch summary line.
 * @license GPL-3.0-only
 */

import { HardDrive, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { Select } from "@/components/ui/select";
import type { AdosAgentBoard } from "@/lib/protocol/firmware/ados-agent-manifest";

export interface TargetBoardCardProps {
  boards: AdosAgentBoard[];
  selectedBoardId: string;
  onSelectBoardId: (id: string) => void;
  loading: boolean;
  error: string;
  onRetry: () => void;
  agentVersion: string;
  manifestSource?: string;
  stackLabel: string;
}

export function TargetBoardCard({
  boards,
  selectedBoardId,
  onSelectBoardId,
  loading,
  error,
  onRetry,
  agentVersion,
  manifestSource,
  stackLabel,
}: TargetBoardCardProps) {
  const t = useTranslations("flashTool.ados");
  const selectedBoard = boards.find((b) => b.id === selectedBoardId) ?? null;
  return (
    <div className="bg-bg-secondary border border-border-default p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold text-text-primary flex items-center gap-2">
          <HardDrive size={14} />
          {t("targetBoard.title")}
          {manifestSource === "fallback" && (
            <span
              className="text-[10px] px-1.5 py-0.5 bg-status-warning/10 text-status-warning border border-status-warning/40"
              aria-label={t("targetBoard.offlineCatalogTooltip")}
              title={t("targetBoard.offlineCatalogTooltip")}
            >
              {t("targetBoard.offlineCatalog")}
            </span>
          )}
        </h2>
        <div className="flex items-center gap-3">
          {agentVersion && (
            <span className="text-[10px] text-text-tertiary">{t("targetBoard.version", { version: agentVersion })}</span>
          )}
          {loading && (
            <span className="text-[10px] text-text-tertiary flex items-center gap-1">
              <RefreshCw size={10} className="animate-spin" /> {t("targetBoard.loadingManifest")}
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="text-[10px] text-status-error flex items-center justify-between">
          <span>{error}</span>
          <button onClick={onRetry} className="underline cursor-pointer">{t("common.retry")}</button>
        </div>
      )}

      <Select
        value={selectedBoardId}
        onChange={onSelectBoardId}
        disabled={loading || boards.length === 0}
        placeholder={loading ? t("targetBoard.loadingBoards") : t("targetBoard.noBoards", { stack: stackLabel })}
        searchable
        options={boards.map((b) => ({
          value: b.id,
          label: b.label,
          description: b.soc,
        }))}
      />

      {selectedBoard && (
        <div className="text-[10px] text-text-tertiary space-y-0.5">
          <p><span className="text-text-secondary">{t("targetBoard.soc")}</span> {selectedBoard.soc} · <span className="text-text-secondary">{t("targetBoard.arch")}</span> {selectedBoard.arch}</p>
          {selectedBoard.description && <p>{selectedBoard.description}</p>}
        </div>
      )}
    </div>
  );
}
