"use client";

/**
 * @module GroundStationMeshCard
 * @description Compact mesh-state card for the GroundStationOverview.
 * Shows role + mesh health (peer count, partition state, mesh id).
 * @license GPL-3.0-only
 */

import { useTranslations } from "next-intl";
import { useGroundStationStore } from "@/stores/ground-station-store";

const roleAccent: Record<string, string> = {
  direct: "text-text-secondary",
  relay: "text-accent-primary",
  receiver: "text-status-success",
  unset: "text-text-tertiary",
};

export function GroundStationMeshCard() {
  const t = useTranslations("groundStationOverview.mesh");
  const role = useGroundStationStore((s) => s.role.info?.current ?? "unset");
  const meshCapable = useGroundStationStore(
    (s) => s.role.info?.mesh_capable ?? false,
  );
  const health = useGroundStationStore((s) => s.mesh.health);

  return (
    <div className="rounded-lg border border-border-default bg-surface-secondary p-3 space-y-2">
      <div className="flex items-baseline justify-between">
        <h3 className="text-xs uppercase tracking-wide text-text-tertiary">
          {t("title")}
        </h3>
        <span className={`text-sm font-medium ${roleAccent[role] ?? "text-text-secondary"}`}>
          {t(`role.${role}`)}
        </span>
      </div>
      {meshCapable ? (
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
          <dt className="text-text-tertiary">{t("status")}</dt>
          <dd
            className={
              health?.up
                ? "text-status-success"
                : "text-text-secondary"
            }
          >
            {health?.up ? t("up") : t("down")}
          </dd>

          <dt className="text-text-tertiary">{t("peers")}</dt>
          <dd className="text-text-primary tabular-nums">
            {health?.peer_count ?? 0}
          </dd>

          <dt className="text-text-tertiary">{t("partition")}</dt>
          <dd className={health?.partition ? "text-status-warning" : "text-text-secondary"}>
            {health?.partition ? t("partitioned") : t("connected")}
          </dd>

          {health?.mesh_id && (
            <>
              <dt className="text-text-tertiary">{t("meshId")}</dt>
              <dd className="text-text-secondary font-mono truncate">
                {health.mesh_id}
              </dd>
            </>
          )}
        </dl>
      ) : (
        <p className="text-xs text-text-tertiary">{t("notCapable")}</p>
      )}
    </div>
  );
}
