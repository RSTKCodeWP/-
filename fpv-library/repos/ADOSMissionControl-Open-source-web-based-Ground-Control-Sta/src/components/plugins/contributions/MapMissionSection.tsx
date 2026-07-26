/**
 * @module plugins/contributions/MapMissionSection
 * @description The map overlays and mission templates the plugin's GCS half
 * adds — both the dedicated `mapOverlays` / `missionTemplates` contributions and
 * the `map.overlay` / `mission.template` slot panels. One combined section so
 * map/mission surfaces read together.
 *
 * @license GPL-3.0-only
 */

"use client";

import { Map as MapIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { resolveNamedIcon } from "@/lib/icons/icon-registry";
import { resolveContribLabel } from "@/lib/skills/skill-label";
import type { InstallManifestSummary } from "../install-dialog/types";

import {
  ContribCategory,
  ContribRow,
  MetaChip,
} from "./contribution-primitives";

type Slot = NonNullable<InstallManifestSummary["contributesSlots"]>[number];
type MapOverlay = NonNullable<
  InstallManifestSummary["contributesMapOverlays"]
>[number];
type MissionTemplate = NonNullable<
  InstallManifestSummary["contributesMissionTemplates"]
>[number];

interface MapItem {
  id: string;
  title?: string;
  icon?: string;
  kind: "mapOverlay" | "missionTemplate";
}

export function MapMissionSection({
  mapSlots,
  missionSlots = [],
  mapOverlays,
  missionTemplates,
}: {
  mapSlots: ReadonlyArray<Slot>;
  /** `mission.template` slot panels (distinct from the dedicated
   * `missionTemplates` contribution). */
  missionSlots?: ReadonlyArray<Slot>;
  mapOverlays: ReadonlyArray<MapOverlay>;
  missionTemplates: ReadonlyArray<MissionTemplate>;
}) {
  const t = useTranslations("pluginInstall.review.contributions");
  const items: MapItem[] = [
    ...mapSlots.map((s) => ({
      id: s.panelId,
      title: s.title,
      icon: s.icon,
      kind: "mapOverlay" as const,
    })),
    ...mapOverlays.map((m) => ({
      id: m.id,
      title: m.title,
      icon: m.icon,
      kind: "mapOverlay" as const,
    })),
    ...missionSlots.map((s) => ({
      id: s.panelId,
      title: s.title,
      icon: s.icon,
      kind: "missionTemplate" as const,
    })),
    ...missionTemplates.map((m) => ({
      id: m.id,
      title: m.title,
      icon: m.icon,
      kind: "missionTemplate" as const,
    })),
  ];
  if (items.length === 0) return null;
  return (
    <ContribCategory icon={MapIcon} label={t("mapMission")} count={items.length}>
      {items.map((item) => (
        <ContribRow
          key={`${item.kind}:${item.id}`}
          icon={resolveNamedIcon(item.icon ?? item.kind)}
          primary={resolveContribLabel(item.title ?? item.id)}
          monoId={item.id}
          chips={
            <MetaChip>
              {item.kind === "mapOverlay"
                ? t("slotKind.mapOverlay")
                : t("slotKind.missionTemplate")}
            </MetaChip>
          }
        />
      ))}
    </ContribCategory>
  );
}
