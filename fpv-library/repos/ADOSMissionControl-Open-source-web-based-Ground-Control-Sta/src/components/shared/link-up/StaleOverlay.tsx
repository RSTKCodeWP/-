"use client";

/**
 * @module link-up/StaleOverlay
 * @description A small "data paused" chip a live agent card surfaces while the
 * heartbeat is stale or offline, so last-known values stay readable underneath
 * (rather than a blank spinner). Reads the same useFreshness() source as the
 * page-level StaleBanner so the two never contradict. Render inside a `relative`
 * container; the chip pins to the top-right by default.
 * @license GPL-3.0-only
 */

import { useTranslations } from "next-intl";
import { PauseCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { useFreshness } from "@/lib/agent/freshness";

interface StaleOverlayProps {
  className?: string;
}

export function StaleOverlay({ className }: StaleOverlayProps) {
  const t = useTranslations("linkUp");
  const freshness = useFreshness();

  if (freshness.state === "live" || freshness.state === "unknown") return null;

  const offline = freshness.state === "offline";

  return (
    <div
      role="status"
      aria-live="polite"
      title={t("stalePaused.tooltip", { ago: freshness.label })}
      className={cn(
        "absolute top-2 right-2 z-10 flex items-center gap-1 rounded px-1.5 py-0.5",
        "text-[10px] font-medium border backdrop-blur-sm",
        offline
          ? "bg-status-error/10 border-status-error/30 text-status-error"
          : "bg-status-warning/10 border-status-warning/30 text-status-warning",
        className,
      )}
    >
      <PauseCircle size={11} />
      {t("stalePaused.chip")}
    </div>
  );
}
