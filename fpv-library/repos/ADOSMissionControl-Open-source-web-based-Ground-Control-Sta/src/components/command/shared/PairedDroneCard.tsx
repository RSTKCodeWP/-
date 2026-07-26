"use client";

/**
 * @module PairedDroneCard
 * @description Shows which drone the ground station is currently paired to
 * (the WFB-ng radio peer). Reads from the link slice's `status.paired_drone`
 * which the agent populates from `/api/v1/ground-station/status`.
 * @license GPL-3.0-only
 */

import { useTranslations } from "next-intl";
import { useGroundStationStore } from "@/stores/ground-station-store";

export function PairedDroneCard() {
  const t = useTranslations("groundStationOverview.pairedDrone");
  const pairedDrone = useGroundStationStore((s) => s.status.paired_drone);

  return (
    <div className="rounded-lg border border-border-default bg-surface-secondary p-3 space-y-1">
      <h3 className="text-xs uppercase tracking-wide text-text-tertiary">
        {t("title")}
      </h3>
      {pairedDrone ? (
        <p className="text-sm font-mono text-text-primary truncate">
          {pairedDrone}
        </p>
      ) : (
        <p className="text-xs text-text-tertiary">{t("unpaired")}</p>
      )}
    </div>
  );
}
