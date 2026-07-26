/**
 * Resolve a skill's display label + one-line effect for the bar and slots.
 *
 * Built-in skills carry a fully-qualified i18n key ROOT in `label` (e.g.
 * `"skills.arm"`); the display name lives at `<root>.label` and the effect at
 * `<root>.effect`. Plugin skills carry their label as a literal string (so a
 * plugin author does not have to ship GCS translations) — those render the
 * literal directly and have no separate effect line.
 *
 * @module skills/skill-label
 * @license GPL-3.0-only
 */

import type { Skill } from "./types";

type Translate = (key: string, values?: Record<string, string | number>) => string;

/** The display name for a skill. */
export function skillDisplayLabel(skill: Skill, t: Translate): string {
  if (skill.source === "plugin") {
    // A plugin label that happens to be a dotted i18n key resolves; a literal
    // falls back to itself. Either way we never append ".label" to it.
    return safeTranslateOrLiteral(skill.label, t);
  }
  return t(`${skill.label}.label`);
}

/**
 * Resolve a contribution's display label for surfaces that render a plugin's
 * declared label directly (the install pop-up, the plugin cards) WITHOUT a
 * translate function. A plugin often ships its label as a key into its OWN
 * bundle catalog (e.g. `"skill.track"`) that the GCS next-intl catalog cannot
 * resolve — rather than leak the raw key, humanize the last dotted segment
 * (`"skill.track"` -> "Track", `"camera.zoom_in"` -> "Zoom In"). A human label
 * that already contains a space or capital is passed through untouched.
 */
export function resolveContribLabel(label: string): string {
  const trimmed = label.trim();
  if (!trimmed) return trimmed;
  // Looks like a display string already (has whitespace or a capital letter).
  if (/\s/.test(trimmed) || /[A-Z]/.test(trimmed)) return trimmed;
  // Dotted lowercase identifier key -> humanize the last segment.
  if (/^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$/.test(trimmed)) {
    const last = trimmed.split(".").pop() ?? trimmed;
    return humanize(last);
  }
  // A bare lowercase token/id -> humanize it too.
  if (/^[a-z][a-z0-9_-]*$/.test(trimmed)) return humanize(trimmed);
  return trimmed;
}

function humanize(token: string): string {
  return token
    .split(/[_-]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** The one-line effect text for a skill, or "" when none (plugin skills). */
export function skillEffectText(skill: Skill, t: Translate): string {
  if (skill.source === "plugin") return "";
  return t(`${skill.label}.effect`);
}

function safeTranslateOrLiteral(value: string, t: Translate): string {
  if (value.includes(".")) {
    try {
      return t(value);
    } catch {
      return value;
    }
  }
  return value;
}
