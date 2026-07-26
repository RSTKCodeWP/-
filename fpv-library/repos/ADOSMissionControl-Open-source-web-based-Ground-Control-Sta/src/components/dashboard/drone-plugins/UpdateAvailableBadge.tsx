"use client";

/**
 * @module UpdateAvailableBadge
 * @description Compact "Update available" badge rendered next to a
 * plugin row inside the per-drone Plugins tab. Reads from
 * `usePluginUpdateStore` and only renders when the agent's auto-update
 * loop has flagged that a newer version exists but won't be applied
 * automatically (major version bump, new permissions, board mismatch,
 * or operator-pinned version). Clicking the badge opens the per-plugin
 * update settings drawer via the parent-supplied `onClick` callback.
 *
 * @license GPL-3.0-only
 */

import { useTranslations } from "next-intl";

import { cn } from "@/lib/utils";
import { usePluginUpdateStore } from "@/stores/plugin-update-store";

interface UpdateAvailableBadgeProps {
  /** Cloud device id of the drone hosting the plugin. */
  deviceId: string;
  /** Plugin identifier on the agent. */
  pluginId: string;
  /** Click handler — opens the update settings drawer in the parent. */
  onClick?: () => void;
  /** Optional class on the badge button. */
  className?: string;
}

export function UpdateAvailableBadge({
  deviceId,
  pluginId,
  onClick,
  className,
}: UpdateAvailableBadgeProps) {
  const t = useTranslations("pluginRegistry.autoUpdate");
  const event = usePluginUpdateStore((s) =>
    s.pendingUpdates.find(
      (e) => e.deviceId === deviceId && e.pluginId === pluginId,
    ),
  );

  if (!event) return null;

  // Tooltip body explains why the auto-update loop skipped this
  // version. Each reason has its own i18n key with a deterministic
  // version-delta substitution for the operator's reading speed.
  const tooltip = t(`tooltipReason.${event.reason}`, {
    current: event.currentVersion,
    latest: event.latestVersion,
  });

  return (
    <button
      type="button"
      data-testid={`plugin-update-badge-${pluginId}`}
      title={tooltip}
      aria-label={tooltip}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        "border-status-warning/40 bg-status-warning/10 text-status-warning",
        "transition-colors hover:bg-status-warning/20 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-status-warning",
        className,
      )}
    >
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-status-warning" />
      <span>{t("badge")}</span>
    </button>
  );
}
