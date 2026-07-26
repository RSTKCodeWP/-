/**
 * @module link-up/locked-surfaces
 * @description Ids for the companion-computer (agent) surfaces shown in the
 * unified drone-detail view. When a drone has a paired agent these render live;
 * when it is flight-controller only they render as lock-badged teaser tabs whose
 * placeholder routes to pairing. Ids only, no icon component references at
 * module scope (so the file imports cleanly under partial lucide mocks). Tab
 * labels come from the `dronePanel.<id>` i18n keys; the value-prop list and
 * placeholder copy come from `linkUp.surface.<id>`.
 * @license GPL-3.0-only
 */

/** Companion-computer surfaces presented as tabs in the drone-detail view. */
export const AGENT_SURFACE_TAB_IDS = [
  "agent",
  "system",
  "blackbox",
  "plugins",
] as const;

export type AgentSurfaceTabId = (typeof AGENT_SURFACE_TAB_IDS)[number];

/** Headline extras listed inside the locked placeholder, not as tabs. */
export const LOCKED_VALUE_PROP_IDS = ["video", "radio", "cellular"] as const;

const AGENT_TAB_SET: ReadonlySet<string> = new Set(AGENT_SURFACE_TAB_IDS);

/** True when `id` is one of the companion-computer surface tab ids. */
export function isAgentSurfaceTab(id: string): boolean {
  return AGENT_TAB_SET.has(id);
}
