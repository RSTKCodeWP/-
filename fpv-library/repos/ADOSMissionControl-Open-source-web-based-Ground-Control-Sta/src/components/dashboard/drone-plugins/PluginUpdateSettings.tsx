"use client";

/**
 * @module PluginUpdateSettings
 * @description Per-plugin update settings drawer. Shown inside the
 * per-drone Plugins tab when the operator clicks an
 * `<UpdateAvailableBadge>` or a "Configure updates" action on a plugin
 * card. Surfaces the auto-update toggle, the optional version pin, and
 * the last-checked timestamp from the agent's auto-update loop.
 *
 * v1 limitation: the GCS cannot mutate the agent's auto-update config
 * from this drawer. The two controls (auto-update toggle + version
 * pin) are read-only with a hint pointing the operator at the `ados
 * plugin auto-update` CLI on the drone itself. A follow-up cycle will
 * add a REST surface on the agent that lets the GCS enqueue a config
 * mutation through the existing command queue.
 *
 * @license GPL-3.0-only
 */

import { useMemo } from "react";
import { useQuery } from "convex/react";
import { useTranslations } from "next-intl";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select, type SelectOption } from "@/components/ui/select";
import { useAuthStore } from "@/stores/auth-store";
import { usePluginUpdateStore } from "@/stores/plugin-update-store";
import { isDemoMode } from "@/lib/utils";
import { api } from "../../../../convex/_generated/api";

interface PluginUpdateSettingsProps {
  /** Cloud device id of the drone the plugin is installed on. */
  deviceId: string;
  /** Plugin identifier on the agent. */
  pluginId: string;
  /** Display name to render in the drawer title. */
  pluginName: string;
  /** Version currently running on the agent. */
  currentVersion: string;
  /** Whether the agent has auto-update enabled for this plugin. */
  autoUpdate: boolean;
  /** Operator-selected pinned version, if any. */
  pinnedVersion?: string | null;
  /** Epoch ms the agent last ran its registry sweep, if known. */
  lastUpdateCheckAt?: number | null;
  /** Closes the drawer. */
  onClose: () => void;
}

export function PluginUpdateSettings({
  deviceId,
  pluginId,
  pluginName,
  currentVersion,
  autoUpdate,
  pinnedVersion,
  lastUpdateCheckAt,
  onClose,
}: PluginUpdateSettingsProps) {
  const t = useTranslations("pluginRegistry.autoUpdate.settings");
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  // Fetch the registry catalog for this plugin so the operator can
  // see the list of versions in the pin dropdown. Skip in demo mode
  // and when not authenticated so the drawer doesn't crash on a
  // missing Convex deployment.
  const catalog = useQuery(
    api.pluginRegistry.getPlugin,
    isAuthenticated && !isDemoMode() ? { pluginId } : "skip",
  );

  const versionOptions = useMemo<SelectOption[]>(() => {
    const opts: SelectOption[] = [
      { value: "__auto__", label: t("pinnedVersionAuto") },
    ];
    if (catalog?.versions) {
      for (const v of catalog.versions) {
        opts.push({ value: v.version, label: `v${v.version}` });
      }
    }
    return opts;
  }, [catalog, t]);

  const pinnedValue = pinnedVersion ?? "__auto__";

  // The agent emits a relative-time string the GCS cannot match
  // without locale-aware formatting. Keep it simple: render the
  // English-style absolute date when known, fallback when not.
  const lastCheckedLabel = useMemo(() => {
    if (!lastUpdateCheckAt) return t("lastCheckedNever");
    const date = new Date(lastUpdateCheckAt);
    return t("lastChecked", { time: date.toLocaleString() });
  }, [lastUpdateCheckAt, t]);

  // Surface the pending event for this plugin (if any) so the operator
  // can confirm which version the badge was pointing at. Reading the
  // store inline keeps the drawer reactive when a fresh event arrives
  // mid-session.
  const pending = usePluginUpdateStore((s) =>
    s.pendingUpdates.find(
      (e) => e.deviceId === deviceId && e.pluginId === pluginId,
    ),
  );

  return (
    <div
      data-testid={`plugin-update-settings-${pluginId}`}
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-md border border-border-default bg-bg-secondary p-4 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="mb-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-text-primary">
              {t("title", { pluginName })}
            </h2>
            <code className="block truncate text-xs text-text-tertiary">
              {pluginId}
            </code>
          </div>
          <button
            type="button"
            aria-label={t("close")}
            onClick={onClose}
            className="text-text-tertiary hover:text-text-primary"
          >
            <X size={16} />
          </button>
        </header>

        <dl className="mb-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-2 text-xs">
          <dt className="text-text-tertiary">{t("currentVersion")}</dt>
          <dd className="text-text-primary">v{currentVersion}</dd>
          {pending ? (
            <>
              <dt className="text-text-tertiary">{t("latestAvailable")}</dt>
              <dd className="text-status-warning">v{pending.latestVersion}</dd>
            </>
          ) : null}
        </dl>

        <fieldset className="mb-3 space-y-2" disabled>
          <div className="flex items-center justify-between gap-3">
            <label
              htmlFor={`auto-update-toggle-${pluginId}`}
              className="text-xs text-text-primary"
            >
              {t("autoUpdateLabel")}
            </label>
            <input
              id={`auto-update-toggle-${pluginId}`}
              type="checkbox"
              checked={autoUpdate}
              readOnly
              disabled
              className="h-4 w-4 cursor-not-allowed accent-accent-primary"
            />
          </div>
          <div>
            <label
              htmlFor={`pinned-version-${pluginId}`}
              className="mb-1 block text-xs text-text-primary"
            >
              {t("pinnedVersionLabel")}
            </label>
            <Select
              value={pinnedValue}
              options={versionOptions}
              onChange={() => {
                /* read-only in v1 */
              }}
              disabled
            />
          </div>
          <p className="text-[11px] text-text-tertiary">{t("autoUpdateHint")}</p>
        </fieldset>

        <p className="mb-3 text-[11px] text-text-tertiary">{lastCheckedLabel}</p>

        <div className="flex justify-end">
          <Button variant="secondary" size="sm" onClick={onClose}>
            {t("close")}
          </Button>
        </div>
      </div>
    </div>
  );
}
