/**
 * The Skill Bar editor's skill drawer: every skill available for the selected
 * drone, grouped Built-in vs each contributing plugin. A drawer item is both
 * draggable (drag onto a slot to bind) and a focusable button (Enter binds it
 * into the focused slot via the parent's keyboard flow). A skill already bound
 * somewhere shows a small "bound" marker so the operator sees its placement.
 *
 * @module fly/SkillDrawer
 * @license GPL-3.0-only
 */

"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { useSkillRegistry, type Skill } from "@/lib/skills";
import { skillDisplayLabel } from "@/lib/skills/skill-label";
import { resolveNamedIcon } from "@/lib/icons/icon-registry";
import { SKILL_DRAG_TYPE, packSkillDrag } from "./skill-drag";

interface SkillDrawerProps {
  droneId: string | null;
  /** Skill ids currently placed in a slot (for the "bound" marker). */
  boundSkillIds: Set<string>;
  /** Bind a drawer skill into the operator's currently-focused slot. */
  onPickSkill: (skillId: string) => void;
}

interface SkillGroup {
  key: string;
  /** Pre-resolved heading text. */
  heading: string;
  skills: Skill[];
}

export function SkillDrawer({
  droneId,
  boundSkillIds,
  onPickSkill,
}: SkillDrawerProps) {
  const t = useTranslations("skillBindings");
  const tRoot = useTranslations();

  const registrySkills = useSkillRegistry((s) => s.skills);
  const resolveForDrone = useSkillRegistry((s) => s.resolveForDrone);

  const resolved = useMemo<Skill[]>(() => {
    if (!droneId) return [];
    return resolveForDrone(droneId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [droneId, resolveForDrone, registrySkills]);

  const groups = useMemo<SkillGroup[]>(() => {
    const builtin: Skill[] = [];
    const byPlugin = new Map<string, Skill[]>();
    for (const skill of resolved) {
      if (skill.source === "plugin") {
        const pid = skill.pluginId ?? "plugin";
        const list = byPlugin.get(pid) ?? [];
        list.push(skill);
        byPlugin.set(pid, list);
      } else {
        builtin.push(skill);
      }
    }
    const result: SkillGroup[] = [];
    if (builtin.length > 0) {
      result.push({
        key: "builtin",
        heading: t("groupBuiltin"),
        skills: builtin,
      });
    }
    for (const [pid, skills] of byPlugin) {
      result.push({
        key: `plugin:${pid}`,
        // A plugin group heading shows the plugin's own skill label scope —
        // there is no separate plugin display name on a Skill, so use the
        // generic "plugin" heading with the id for disambiguation.
        heading: t("groupPlugin", { name: pid }),
        skills,
      });
    }
    return result;
  }, [resolved, t]);

  if (!droneId) {
    return (
      <p className="px-2 py-3 text-xs text-text-tertiary">{t("noDrone")}</p>
    );
  }

  if (groups.length === 0) {
    return (
      <p className="px-2 py-3 text-xs text-text-tertiary">{t("noSkills")}</p>
    );
  }

  return (
    <div className="flex flex-col gap-3" role="list" aria-label={t("drawerLabel")}>
      {groups.map((group) => (
        <div key={group.key} className="flex flex-col gap-1">
          <h4 className="px-1 text-[10px] font-semibold uppercase tracking-wide text-text-tertiary">
            {group.heading}
          </h4>
          <div className="flex flex-wrap gap-1">
            {group.skills.map((skill) => {
              const label = skillDisplayLabel(skill, tRoot);
              const bound = boundSkillIds.has(skill.id);
              const Icon = resolveNamedIcon(skill.icon);
              return (
                <button
                  key={skill.id}
                  type="button"
                  role="listitem"
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.effectAllowed = "copy";
                    e.dataTransfer.setData(
                      SKILL_DRAG_TYPE,
                      packSkillDrag({ kind: "skill", skillId: skill.id }),
                    );
                  }}
                  onClick={() => onPickSkill(skill.id)}
                  aria-label={
                    bound
                      ? t("drawerItemBound", { label })
                      : t("drawerItem", { label })
                  }
                  className="flex items-center gap-1.5 border border-border-default bg-bg-tertiary px-2 py-1 text-xs text-text-primary transition-colors hover:border-accent-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary"
                >
                  <Icon size={12} className="shrink-0 text-text-secondary" aria-hidden />
                  <span>{label}</span>
                  {bound ? (
                    <span className="text-[9px] uppercase tracking-wide text-accent-primary">
                      {t("boundTag")}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
