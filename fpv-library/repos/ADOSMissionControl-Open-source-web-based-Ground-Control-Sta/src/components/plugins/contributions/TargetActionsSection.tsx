/**
 * @module plugins/contributions/TargetActionsSection
 * @description The cockpit target actions the plugin's GCS half adds to the
 * click-a-target popup. Each row shows its glyph, humanized label, the class
 * it applies to (when narrowed), and its default hotkey.
 *
 * @license GPL-3.0-only
 */

"use client";

import { Crosshair } from "lucide-react";
import { useTranslations } from "next-intl";

import { resolveNamedIcon } from "@/lib/icons/icon-registry";
import { resolveContribLabel } from "@/lib/skills/skill-label";
import type { InstallManifestSummary } from "../install-dialog/types";

import {
  ContribCategory,
  ContribRow,
  KeyChip,
  MetaChip,
} from "./contribution-primitives";

type Action = NonNullable<
  InstallManifestSummary["contributesTargetActions"]
>[number];

export function TargetActionsSection({
  actions,
}: {
  actions: ReadonlyArray<Action>;
}) {
  const t = useTranslations("pluginInstall.review.contributions");
  if (actions.length === 0) return null;
  return (
    <ContribCategory
      icon={Crosshair}
      label={t("targetActions")}
      count={actions.length}
    >
      {actions.map((action) => (
        <ContribRow
          key={action.id}
          icon={resolveNamedIcon(action.icon)}
          primary={resolveContribLabel(action.label ?? action.id)}
          monoId={action.id}
          chips={
            <>
              {action.appliesToClass ? (
                <MetaChip>{action.appliesToClass}</MetaChip>
              ) : null}
              {action.defaultKey ? <KeyChip keyLabel={action.defaultKey} /> : null}
            </>
          }
        />
      ))}
    </ContribCategory>
  );
}
