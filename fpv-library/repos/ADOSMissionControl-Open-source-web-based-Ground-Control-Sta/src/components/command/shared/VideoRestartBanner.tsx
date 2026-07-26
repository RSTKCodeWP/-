"use client";

/**
 * @module VideoRestartBanner
 * @description Banner that appears once the agent reports the video
 * pipeline has restarted more times than the operator should have to
 * tolerate without intervention. The agent resets the count after the
 * stream stays healthy for the configured cool-down, so the banner
 * disappears on its own once the pipeline stabilises.
 * @license GPL-3.0-only
 */

import { AlertTriangle } from "lucide-react";
import { useTranslations } from "next-intl";
import { useAgentCapabilitiesStore } from "@/stores/agent-capabilities-store";

const RESTART_THRESHOLD = 5;

export function VideoRestartBanner() {
  const count = useAgentCapabilitiesStore((s) => s.videoRestartAttempts);
  const t = useTranslations("video.restartBanner");

  if (count < RESTART_THRESHOLD) return null;

  return (
    <div
      role="alert"
      className="flex items-start gap-3 px-4 py-2.5 rounded-lg border bg-status-warning/10 border-status-warning/30 text-status-warning"
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{t("title")}</p>
        <p className="text-xs opacity-80">{t("message", { count })}</p>
      </div>
    </div>
  );
}
