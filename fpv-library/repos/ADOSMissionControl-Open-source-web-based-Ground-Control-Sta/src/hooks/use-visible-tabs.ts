/**
 * @module useVisibleTabs
 * @description Derives which Command sub-tabs should be visible based on agent
 *   capabilities. Profile-aware: ground stations drop tabs that only make sense
 *   on a flying node.
 * @license GPL-3.0-only
 */

import { useMemo } from "react";
import { useAgentCapabilitiesStore } from "@/stores/agent-capabilities-store";

export type StaticTab = "overview" | "system";
export type DynamicTab = "plugins";
export type CommandSubTab = StaticTab | DynamicTab;

export function useVisibleTabs(): CommandSubTab[] {
  const profile = useAgentCapabilitiesStore((s) => s.profile);

  return useMemo(() => {
    const tabs: CommandSubTab[] = ["overview"];

    // Ground stations don't fly. Drop tabs that only make sense on a
    // node that flies a vehicle. Compute nodes get their own panel
    // tree (handled at the panel level, not here).
    const isGroundStation = profile === "ground-station";

    tabs.push("system");
    // Plugins surface lives on the Command page so install +
    // enable/disable is one click from the active-drone view.
    // Ground stations do not host drone-side plugins. Always present
    // otherwise so the install affordance is discoverable even on a
    // fresh drone with zero plugins installed.
    if (!isGroundStation) {
      tabs.push("plugins");
    }
    return tabs;
  }, [profile]);
}
