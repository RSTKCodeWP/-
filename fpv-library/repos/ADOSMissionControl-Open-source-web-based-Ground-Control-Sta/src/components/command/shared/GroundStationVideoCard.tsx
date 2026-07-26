"use client";

/**
 * @module GroundStationVideoCard
 * @description Downlink video for the GroundStationOverview. A ground
 * station decodes the drone's stream off the radio and republishes it on
 * the same WHEP endpoint a drone camera uses, so this reuses VideoFeedCard
 * verbatim and only adds a label + a live/idle status pill. The inner
 * card renders its own NO SIGNAL overlay when the agent isn't streaming.
 * @license GPL-3.0-only
 */

import { useTranslations } from "next-intl";
import { useVideoStore } from "@/stores/video-store";
import { cn } from "@/lib/utils";
import { VideoFeedCard } from "./VideoFeedCard";

export function GroundStationVideoCard() {
  const t = useTranslations("groundStationOverview.video");
  const agentVideoState = useVideoStore((s) => s.agentVideoState);

  const { label, tone } =
    agentVideoState === "running"
      ? { label: t("live"), tone: "text-status-success" }
      : agentVideoState === "starting" || agentVideoState === "connecting"
        ? { label: t("connecting"), tone: "text-status-warning" }
        : { label: t("noSignal"), tone: "text-text-tertiary" };

  return (
    <div className="rounded-lg border border-border-default bg-surface-secondary p-3 space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-xs uppercase tracking-wide text-text-tertiary">
          {t("title")}
        </h3>
        <span className={cn("text-[10px] uppercase tracking-wide", tone)}>
          {label}
        </span>
      </div>
      <VideoFeedCard />
    </div>
  );
}
