/**
 * @module plugins/contributions/OverlaysSection
 * @description Video overlays and notification channels the plugin's GCS half
 * mounts. Each row shows the surface it lands on as a plain-language chip.
 *
 * @license GPL-3.0-only
 */

"use client";

import { Layers } from "lucide-react";
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

type Slot = NonNullable<InstallManifestSummary["contributesSlots"]>[number];

export function OverlaysSection({ overlays }: { overlays: ReadonlyArray<Slot> }) {
  const t = useTranslations("pluginInstall.review.contributions");
  if (overlays.length === 0) return null;
  return (
    <ContribCategory icon={Layers} label={t("overlays")} count={overlays.length}>
      {overlays.map((slot) => (
        <ContribRow
          key={`${slot.slot}:${slot.panelId}`}
          icon={resolveNamedIcon(slot.icon)}
          primary={resolveContribLabel(slot.title ?? slot.panelId)}
          monoId={slot.panelId}
          chips={<MetaChip>{t(`slotKind.${slotKindKey(slot.slot)}`)}</MetaChip>}
        />
      ))}
    </ContribCategory>
  );
}
