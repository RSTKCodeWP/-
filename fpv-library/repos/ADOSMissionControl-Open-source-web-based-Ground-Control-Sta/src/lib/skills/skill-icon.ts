/**
 * Resolve a skill's lucide icon component from its icon name. Thin alias over
 * the shared icon registry so the Skill Bar slot, the gamepad radial, the
 * command palette, and the plugin surfaces all render the same glyph. An
 * unknown name (e.g. a plugin icon the vocabulary does not cover) falls back to
 * a generic glyph rather than crashing.
 *
 * @module skills/skill-icon
 * @license GPL-3.0-only
 */

import { resolveNamedIcon } from "@/lib/icons/icon-registry";
import type { LucideIcon } from "lucide-react";

/** The lucide icon for a skill's icon name, falling back to a generic glyph. */
export function resolveSkillIcon(iconName: string): LucideIcon {
  return resolveNamedIcon(iconName);
}
