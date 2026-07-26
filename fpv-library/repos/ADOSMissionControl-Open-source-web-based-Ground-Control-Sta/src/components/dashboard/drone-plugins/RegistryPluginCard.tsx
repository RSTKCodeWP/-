"use client";

/**
 * @module RegistryPluginCard
 * @description Inline card rendered on the per-drone Plugins tab for one
 * registry plugin. Surfaces the catalog name, description, category,
 * author, license, tier, and an Install button that's
 * compatibility-gated against the connected drone. Click Install — the
 * parent grid resolves the version row's manifest, parses it, and opens
 * `PluginInstallDialog` on its single-page review surface. From there
 * the operator approves permissions and the dialog hands the URL + SHA
 * pin to the agent's install-from-URL endpoint.
 *
 * Risk classification is intentionally NOT rendered on the card — risk
 * is tied to the actual manifest and surfaces inside the review modal
 * where the operator can also see which permissions drive the rating.
 *
 * @license GPL-3.0-only
 */

import { useMemo } from "react";
import { useQuery } from "convex/react";
import { useTranslations } from "next-intl";
import { Cpu, Layout, Package, PenTool, Radio, Sparkles } from "lucide-react";

import { api } from "../../../../convex/_generated/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { resolveNamedIcon } from "@/lib/icons/icon-registry";
import {
  pluginMatchesProfile,
  type PluginTargetProfile,
} from "@/lib/plugins/types";
import { useAgentCapabilitiesStore } from "@/stores/agent-capabilities-store";

import { useRegistryCompatibility } from "../../plugins/install-dialog/use-registry-compatibility";

type RegistryCategory = "drivers" | "ui" | "ai" | "telemetry" | "tools";

export interface RegistryPluginRow {
  _id: string;
  plugin_id: string;
  name: string;
  description: string;
  category: RegistryCategory;
  license: string;
  author_id: string;
  verified_publisher: boolean;
  latest_version: string;
  icon_url?: string;
  /** A declared named icon (shared icon vocabulary, e.g. "camera"). When the
   * catalog carries one it drives the preview glyph; otherwise the per-plugin
   * fallback map below (then the category glyph) applies. */
  icon?: string;
  tier?: "first_party" | "verified" | "community";
  /** Node profiles the plugin's agent half targets (`drone` /
   * `ground-station` / `workstation`), denormalized from the manifest. Absent
   * on older catalog rows → treated as drone-only by {@link pluginMatchesProfile}
   * so a drone-targeting plugin is not offered on a ground-station or
   * workstation node. */
  target_profiles?: PluginTargetProfile[];
}

type CardState = "loading" | { error: string } | undefined;

export interface RegistryPluginCardProps {
  plugin: RegistryPluginRow;
  /** Whether the plugin already lives on the target drone's install
   * state. When `true` the card disables Install and surfaces an
   * "Installed" pill. */
  installed: boolean;
  /** Transient install state managed by the parent grid. */
  state: CardState;
  onInstall: () => void;
}

/** Lucide icon + tailwind classes paired with each registry category.
 * The category pill picks the right combo at render time so the colour
 * language matches the catalog filter chips. */
const CATEGORY_STYLE: Record<
  RegistryCategory,
  {
    icon: typeof Package;
    classes: string;
  }
> = {
  drivers: {
    icon: Cpu,
    classes:
      "border-accent-primary/40 bg-accent-primary/10 text-accent-primary",
  },
  ui: {
    icon: Layout,
    classes:
      "border-text-secondary/40 bg-bg-tertiary text-text-primary",
  },
  ai: {
    icon: Sparkles,
    classes:
      "border-status-warning/40 bg-status-warning/10 text-status-warning",
  },
  telemetry: {
    icon: Radio,
    classes:
      "border-status-success/40 bg-status-success/10 text-status-success",
  },
  tools: {
    icon: PenTool,
    classes:
      "border-text-secondary/40 bg-surface-secondary text-text-secondary",
  },
};

/** A distinct named glyph per first-party plugin (from the shared icon
 * vocabulary) so two plugins in the same category still read apart at a glance.
 * A plugin whose catalog row carries a declared `icon` uses that instead; a
 * plugin in neither falls back to its category icon, so a community plugin
 * always gets a real glyph — never a bare letter. Keep in lockstep with the
 * website mirror (`website/src/components/extensions/ExtensionIcon.tsx`). */
const PLUGIN_ICON_NAME: Record<string, string> = {
  "com.altnautica.follow-me": "follow",
  "com.altnautica.vision-nav": "navigation",
  "com.altnautica.battery-health-panel": "battery",
  "com.altnautica.thermal-flir-lepton-usb": "thermal",
  "com.altnautica.mavlink-gimbal-v2": "gimbal",
  "com.altnautica.siyi-pod": "camera",
};

export function RegistryPluginCard({
  plugin,
  installed,
  state,
  onInstall,
}: RegistryPluginCardProps) {
  const t = useTranslations("pluginRegistry.browse");

  // The connected node's resolved profile + whether its capabilities have
  // loaded, so we can gate Install on a plugin the paired node cannot host
  // (a drone-only plugin on a workstation, a ground-station-only plugin on a
  // drone). The profile gate applies only once the profile is known; before
  // that the version gate's `no_agent` state already blocks Install.
  const nodeProfile = useAgentCapabilitiesStore((s) => s.profile);
  const profileLoaded = useAgentCapabilitiesStore((s) => s.loaded);

  // `listPlugins` returns the plugin row but not the per-version
  // compatibility envelope. `getPlugin` fills in `agent_min_version`
  // and `supported_boards`; Convex deduplicates the subscription
  // across cards that share an id.
  const detail = useQuery(api.pluginRegistry.getPlugin, {
    pluginId: plugin.plugin_id,
  }) as
    | {
        versions: ReadonlyArray<{
          version: string;
          agent_min_version: string;
          agent_max_version?: string;
          supported_boards?: ReadonlyArray<string>;
        }>;
      }
    | null
    | undefined;

  const latestVersionRow = useMemo(() => {
    if (!detail || detail === null) return null;
    return (
      detail.versions.find((v) => v.version === plugin.latest_version) ?? null
    );
  }, [detail, plugin.latest_version]);

  const compat = useRegistryCompatibility(
    latestVersionRow ?? {
      agent_min_version: plugin.latest_version,
      supported_boards: undefined,
    },
  );

  const isLoading = state === "loading";
  const errMessage =
    state && typeof state === "object" && "error" in state ? state.error : null;

  // Hard blocks: the install genuinely cannot proceed.
  //   * no_agent: no drone to install into
  //   * version: agent version is out of range, the agent will reject
  //   * isLoading: install in flight, debounce
  //   * installed: already on the drone
  // Soft warnings: the install MIGHT not work but the agent re-checks
  // every constraint at archive time and rejects cleanly. Keep the
  // button clickable so the operator can try; surface the warning so
  // they know what to expect.
  const compatHardBlock =
    !compat.compatible &&
    (compat.reason === "no_agent" || compat.reason === "version");
  const compatSoftWarning =
    !latestVersionRow ||
    (!compat.compatible && compat.reason === "board");

  // The paired node cannot host this plugin's target profile. A hard block:
  // installing would land an archive the agent (or the node's surface tree)
  // has no home for. Only asserted once the profile is known.
  const profileBlock =
    profileLoaded && !pluginMatchesProfile(plugin.target_profiles, nodeProfile);

  const disabled = installed || isLoading || compatHardBlock || profileBlock;

  const tooltip = (() => {
    if (installed) return undefined;
    if (profileBlock) {
      return t("card.notCompatible.profile");
    }
    if (compat.reason === "no_agent") {
      return compat.detail ?? t("card.notCompatible.noAgent");
    }
    if (compat.reason === "version") {
      return t("card.notCompatible.version", {
        version: compat.detail ?? "?",
      });
    }
    if (!latestVersionRow) {
      return t("card.notCompatible.loadingDetail");
    }
    if (compat.reason === "board") {
      return t("card.notCompatible.board");
    }
    return undefined;
  })();

  const warningText = (() => {
    if (!compatSoftWarning) return null;
    if (!latestVersionRow) {
      return t("card.notCompatible.loadingDetail");
    }
    if (compat.reason === "board") {
      return t("card.notCompatible.board");
    }
    return null;
  })();

  const tierKey =
    plugin.tier ?? (plugin.verified_publisher ? "verified" : "community");

  const categoryStyle = CATEGORY_STYLE[plugin.category];
  const CategoryIcon = categoryStyle.icon;
  // Preview glyph: the catalog's declared icon, else a distinct per-plugin
  // glyph, else the category icon — never a bare letter. All resolve through
  // the shared icon vocabulary. The catalog's icon_url SVGs are not hosted, so
  // the glyph is the canonical preview.
  const declaredIconName = plugin.icon ?? PLUGIN_ICON_NAME[plugin.plugin_id];
  const PreviewIcon = declaredIconName
    ? resolveNamedIcon(declaredIconName)
    : CategoryIcon;

  return (
    <li className="h-full">
      {/* The whole card is the click target: it opens the install/detail
       * modal (the same action as the Install button). Keyboard-operable
       * via role=button + Enter/Space. */}
      <div
        role="button"
        tabIndex={0}
        onClick={onInstall}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onInstall();
          }
        }}
        aria-label={t("card.viewDetails")}
        className="flex h-full cursor-pointer flex-col gap-2 rounded-lg border border-border-default bg-bg-secondary p-3 transition-colors hover:border-border-strong hover:bg-bg-tertiary/40 focus:outline-none focus-visible:ring-1 focus-visible:ring-accent-primary"
      >
        <div className="flex items-start gap-3">
          <div
            className={
              "flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border " +
              categoryStyle.classes
            }
          >
            <PreviewIcon className="h-5 w-5" aria-hidden />
          </div>
          <div className="min-w-0 flex-1 space-y-1.5">
            <div className="flex flex-wrap items-center gap-1.5">
              <h4 className="truncate text-sm font-medium text-text-primary">
                {plugin.name}
              </h4>
              <span className="text-xs text-text-tertiary">
                v{plugin.latest_version}
              </span>
              {installed && (
                <Badge variant="success" size="sm">
                  {t("card.installedPill")}
                </Badge>
              )}
            </div>
            <div className="flex flex-wrap gap-1">
              <span
                className={
                  "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium " +
                  categoryStyle.classes
                }
              >
                <CategoryIcon className="h-3 w-3" aria-hidden />
                {t(`category.${plugin.category}`)}
              </span>
              <Badge variant="info" size="sm">
                {plugin.license}
              </Badge>
              {tierKey === "first_party" && (
                <Badge variant="success" size="sm">
                  {t("card.tierBadge.first_party")}
                </Badge>
              )}
              {tierKey === "verified" && (
                <Badge variant="info" size="sm">
                  {t("card.tierBadge.verified")}
                </Badge>
              )}
            </div>
          </div>
          <Button
            size="sm"
            variant={
              installed || compatHardBlock || profileBlock
                ? "secondary"
                : "primary"
            }
            disabled={disabled}
            onClick={(e) => {
              e.stopPropagation();
              onInstall();
            }}
            title={tooltip}
            className="shrink-0"
          >
            {installed
              ? t("card.installed")
              : isLoading
                ? t("card.installing")
                : t("card.install")}
          </Button>
        </div>

        <p className="line-clamp-2 text-xs text-text-secondary">
          {plugin.description}
        </p>

        <p className="mt-auto truncate text-[11px] text-text-tertiary">
          {t("card.byAuthor", { author: plugin.author_id })}
        </p>

        {errMessage && (
          <div
            className="flex items-start justify-between gap-2 rounded border border-status-error/40 bg-status-error/10 px-2 py-1.5 text-xs text-status-error"
            role="alert"
          >
            <div className="min-w-0 flex-1 break-words">
              <p className="font-medium">{t("card.error.title")}</p>
              <p className="mt-0.5 text-[11px] opacity-90">{errMessage}</p>
            </div>
            <Button
              size="sm"
              variant="ghost"
              onClick={(e) => {
                e.stopPropagation();
                onInstall();
              }}
              className="shrink-0"
            >
              {t("card.error.retry")}
            </Button>
          </div>
        )}

        {warningText && !errMessage && (
          <p
            className="rounded border border-status-warning/40 bg-status-warning/10 px-2 py-1 text-[11px] text-status-warning"
            role="status"
          >
            {warningText}
          </p>
        )}
      </div>
    </li>
  );
}
