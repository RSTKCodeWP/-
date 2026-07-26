"use client";

/**
 * @module CanStatusBanner
 * @description Compact horizontal status strip for the CAN Config page.
 *
 * Shows the currently selected drone, CAN1 / CAN2 bitrates (best-effort
 * from the cached drone params), SLCAN passthrough state derived from
 * `CAN_SLCAN_CPORT`, the count of online DroneCAN nodes from the node
 * store, and the live bus fps from the bus store.
 *
 * Everything is read-only here. The banner is purely an at-a-glance
 * surface — knobs live in their respective sections.
 *
 * @license GPL-3.0-only
 */

import { useTranslations } from "next-intl";
import { useDroneManager } from "@/stores/drone-manager";
import { useDroneCanNodeStore } from "@/stores/dronecan/node-store";
import { useDroneCanBusStore } from "@/stores/dronecan/bus-store";

function formatBitrate(value: number | undefined): string {
  if (!value || value <= 0) return "—";
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(value % 1_000_000 === 0 ? 0 : 1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(value % 1_000 === 0 ? 0 : 1)}k`;
  return String(value);
}

export interface CanStatusBannerProps {
  /** Live param map keyed by ArduPilot parameter name (from usePanelParams). */
  params: Map<string, number>;
}

export function CanStatusBanner({ params }: CanStatusBannerProps) {
  const t = useTranslations("canConfig.banner");

  const selectedDrone = useDroneManager((s) => s.getSelectedDrone());
  const onlineNodes = useDroneCanNodeStore((s) => {
    // Subscribe to the version counter so the readout updates on every
    // node-store mutation rather than only on a fresh render.
    void s._version;
    return s.getOnlineCount();
  });
  const fps = useDroneCanBusStore((s) => s.counters.fps);

  const can1Bitrate = params.get("CAN_P1_BITRATE");
  const can2Bitrate = params.get("CAN_P2_BITRATE");
  const slcanCport = params.get("CAN_SLCAN_CPORT") ?? 0;
  const slcanActive = slcanCport > 0;

  return (
    <div className="flex flex-wrap items-center gap-4 px-4 py-2 border border-border-default bg-bg-secondary text-[11px]">
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${selectedDrone ? "bg-status-success" : "bg-text-tertiary"}`} />
        <span className="text-text-tertiary uppercase tracking-wider">{t("drone")}</span>
        <span className="text-text-primary font-medium">{selectedDrone ? selectedDrone.name : "—"}</span>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-text-tertiary uppercase tracking-wider">CAN1 {t("bitrate")}</span>
        <span className="text-text-primary font-mono">{formatBitrate(can1Bitrate)}</span>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-text-tertiary uppercase tracking-wider">CAN2 {t("bitrate")}</span>
        <span className="text-text-primary font-mono">{formatBitrate(can2Bitrate)}</span>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-text-tertiary uppercase tracking-wider">SLCAN</span>
        <span className={slcanActive ? "text-status-warning font-medium" : "text-text-secondary"}>
          {slcanActive ? t("slcanActive") : t("slcanInactive")}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-text-tertiary uppercase tracking-wider">{t("nodes")}</span>
        <span className="text-text-primary font-mono">{onlineNodes}</span>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-text-tertiary uppercase tracking-wider">{t("fps")}</span>
        <span className="text-text-primary font-mono">{fps}</span>
      </div>
    </div>
  );
}
