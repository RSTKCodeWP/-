/**
 * @module plugins/contributions/ParametersSection
 * @description The declarative settings a plugin's GCS half renders natively.
 * Each parameter shows its humanized key, its control type, and (for enums)
 * the allowed values so the operator sees what is configurable before
 * installing.
 *
 * @license GPL-3.0-only
 */

"use client";

import { SlidersHorizontal } from "lucide-react";
import { useTranslations } from "next-intl";

import { resolveNamedIcon } from "@/lib/icons/icon-registry";
import { resolveContribLabel } from "@/lib/skills/skill-label";
import { inferWidget, type PluginParameter } from "@/lib/plugins/parameters/schema";
import type { InstallManifestSummary } from "../install-dialog/types";

import {
  ContribCategory,
  ContribRow,
  MetaChip,
} from "./contribution-primitives";

type Param = NonNullable<InstallManifestSummary["contributesParameters"]>[number];

/** A widget → glyph-name hint so a range reads as a slider, an enum as a list. */
function widgetIconName(param: PluginParameter): string {
  const widget = inferWidget(param.schema, param.ui);
  switch (widget) {
    case "boolean":
      return "settings";
    case "enum":
      return "layers";
    case "range":
    case "number":
      return "gauge";
    default:
      return "settings";
  }
}

export function ParametersSection({
  parameters,
}: {
  parameters: ReadonlyArray<Param>;
}) {
  const t = useTranslations("pluginInstall.review.contributions");
  if (parameters.length === 0) return null;
  return (
    <ContribCategory
      icon={SlidersHorizontal}
      label={t("parameters")}
      count={parameters.length}
    >
      {parameters.map((param) => {
        const widget = inferWidget(param.schema, param.ui);
        const enumValues =
          param.schema.enum && param.schema.enum.length > 0
            ? param.schema.enum.map(String).join(" · ")
            : undefined;
        return (
          <ContribRow
            key={param.key}
            icon={resolveNamedIcon(widgetIconName(param))}
            primary={resolveContribLabel(param.key)}
            secondary={enumValues}
            chips={<MetaChip>{widget}</MetaChip>}
          />
        );
      })}
    </ContribCategory>
  );
}
