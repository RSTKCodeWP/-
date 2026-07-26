/**
 * @module plugins/contributions/TabsSection
 * @description The tabs + panels the plugin's GCS half mounts (node-detail
 * tabs, cockpit panels, FC/hardware tabs). Each row shows the surface it lands
 * on as a plain-language chip so the operator sees where the plugin will
 * appear in Mission Control.
 *
 * @license GPL-3.0-only
 */

"use client";

import { LayoutPanelTop } from "lucide-react";
import { useTranslations } from "next-intl";

import { resolveNamedIcon } from "@/lib/icons/icon-registry";
import { resolveContribLabel } from "@/lib/skills/skill-label";
import type { InstallManifestSummary } from "../install-dialog/types";

import {
  ContribCategory,
  ContribRow,
  MetaChip,
  slotKindKey,
} from "./contribution-primitives";

type Tab = NonNullable<InstallManifestSummary["contributesTabs"]>[number];
type Slot = NonNullable<InstallManifestSummary["contributesSlots"]>[number];

interface SurfaceItem {
  panelId: string;
  title?: string;
  icon?: string;
  slot: string;
}

export function TabsSection({
  tabs,
  panels,
}: {
  tabs: ReadonlyArray<Tab>;
  panels: ReadonlyArray<Slot>;
}) {
  const t = useTranslations("pluginInstall.review.contributions");
  const items: SurfaceItem[] = [
    ...tabs.map((tab) => ({
      panelId: tab.panelId,
      title: tab.title,
      icon: tab.icon,
      slot: "node.detail.tab",
    })),
    ...panels.map((panel) => ({
      panelId: panel.panelId,
      title: panel.title,
      icon: panel.icon,
      slot: panel.slot,
    })),
  ];
  if (items.length === 0) return null;
  return (
    <ContribCategory
      icon={LayoutPanelTop}
      label={t("tabs")}
      count={items.length}
    >
      {items.map((item) => (
        <ContribRow
          key={`${item.slot}:${item.panelId}`}
          icon={resolveNamedIcon(item.icon)}
          primary={resolveContribLabel(item.title ?? item.panelId)}
          monoId={item.panelId}
          chips={<MetaChip>{t(`slotKind.${slotKindKey(item.slot)}`)}</MetaChip>}
        />
      ))}
    </ContribCategory>
  );
}
