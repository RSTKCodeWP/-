/**
 * @module plugins/contributions/SkillsSection
 * @description The Skills row list in the install pop-up's contributions
 * block. Each skill renders its resolved glyph, its humanized label (no more
 * raw `skill.track` i18n keys), its default hotkey chord, and toggle / confirm
 * / arm-requirement badges — the fields the old bare-pill list dropped.
 *
 * @license GPL-3.0-only
 */

"use client";

import { Zap } from "lucide-react";
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

type Skill = NonNullable<InstallManifestSummary["contributesSkills"]>[number];

export function SkillsSection({
  skills,
}: {
  skills: ReadonlyArray<Skill>;
}) {
  const t = useTranslations("pluginInstall.review.contributions");
  if (skills.length === 0) return null;
  return (
    <ContribCategory icon={Zap} label={t("skills")} count={skills.length}>
      {skills.map((skill) => {
        const Icon = resolveNamedIcon(skill.icon);
        const key = skill.defaultBinding?.key ?? undefined;
        return (
          <ContribRow
            key={skill.id}
            icon={Icon}
            primary={resolveContribLabel(skill.label)}
            monoId={skill.id}
            chips={
              <>
                {key ? <KeyChip keyLabel={key} /> : null}
                {skill.toggle ? (
                  <MetaChip tone="accent">{t("toggle")}</MetaChip>
                ) : null}
                {skill.confirm ? (
                  <MetaChip tone="warn">{t("confirm")}</MetaChip>
                ) : null}
                {skill.armRequirement === "armed" ? (
                  <MetaChip>{t("armArmed")}</MetaChip>
                ) : skill.armRequirement === "disarmed" ? (
                  <MetaChip>{t("armDisarmed")}</MetaChip>
                ) : null}
              </>
            }
          />
        );
      })}
    </ContribCategory>
  );
}
