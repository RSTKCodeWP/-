"use client";

/**
 * @module ReceiverCard
 * @description Relay-side view of the current receiver: mDNS host, UDP
 * port, fragments seen vs forwarded, and receiver reachability state.
 * @license GPL-3.0-only
 */

import { useTranslations } from "next-intl";
import { useGroundStationStore } from "@/stores/ground-station-store";

function formatAge(lastSeenMs: number): string {
  if (!lastSeenMs) return "--";
  const ageS = Math.max(0, Math.floor((Date.now() - lastSeenMs) / 1000));
  if (ageS < 60) return `${ageS}s`;
  if (ageS < 3600) return `${Math.floor(ageS / 60)}m`;
  return `${Math.floor(ageS / 3600)}h`;
}

export function ReceiverCard() {
  const t = useTranslations("hardware.distributedRx");
  const status = useGroundStationStore((s) => s.distributedRx.relayStatus);

  if (!status) {
    return (
      <div className="p-4 bg-surface-primary border border-border-default/40">
        <div className="text-sm text-text-tertiary italic">{t("noRelayStatus")}</div>
      </div>
    );
  }

  const reachable = status.up;
  return (
    <div className="p-4 bg-surface-primary border border-border-default/40 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-text-primary">{t("forwardingTo")}</div>
        <div
          className={
            reachable
              ? "text-xs uppercase tracking-wider text-status-success"
              : "text-xs uppercase tracking-wider text-status-warning"
          }
        >
          {reachable ? t("reachable") : t("unreachable")}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <div className="text-text-tertiary uppercase tracking-wider">
            {t("receiverIp")}
          </div>
          <div className="font-mono text-text-primary">
            {status.receiver_ip ?? "--"}:{status.receiver_port}
          </div>
        </div>
        <div>
          <div className="text-text-tertiary uppercase tracking-wider">
            {t("lastSeen")}
          </div>
          <div className="font-mono text-text-primary">
            {formatAge(status.receiver_last_seen_ms)} ago
          </div>
        </div>
        <div>
          <div className="text-text-tertiary uppercase tracking-wider">
            {t("fragmentsSeen")}
          </div>
          <div className="font-mono text-text-primary">
            {status.fragments_seen.toLocaleString()}
          </div>
        </div>
        <div>
          <div className="text-text-tertiary uppercase tracking-wider">
            {t("fragmentsForwarded")}
          </div>
          <div className="font-mono text-text-primary">
            {status.fragments_forwarded.toLocaleString()}
          </div>
        </div>
      </div>
    </div>
  );
}
