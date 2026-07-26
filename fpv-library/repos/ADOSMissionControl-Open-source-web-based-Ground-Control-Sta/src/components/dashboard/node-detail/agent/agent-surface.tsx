/**
 * @module node-detail/agent/agent-surface
 * @description The single Agent surface appended to every profile's surface
 * list. Ungrouped (renders as a standalone tab at the end of the strip); its
 * body is the AgentTab, which collapses the companion-computer sub-pages.
 * @license GPL-3.0-only
 */

import type { SurfaceSpec } from "../surface-types";
import { AgentTab } from "./AgentTab";

export const AGENT_SURFACE: SurfaceSpec = {
  id: "agent",
  labelKey: "dronePanel.agent",
  render: (ctx) => <AgentTab ctx={ctx} />,
};
