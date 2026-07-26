/**
 * @module AgentCapabilities
 * @description Internal aggregator for the agent-capabilities slice. The
 * thin barrel at `src/stores/agent-capabilities-store.ts` re-exports from
 * here so existing callsites that import `useAgentCapabilitiesStore` and
 * `AgentCapabilitiesStore` keep working without import changes.
 *
 * @license GPL-3.0-only
 */

export { useAgentCapabilitiesStore } from "./state";
export type {
  AgentCapabilitiesActions,
  AgentCapabilitiesState,
  AgentCapabilitiesStore,
  AgentProfile,
  AgentRole,
  ManualConnectionUrls,
  RuntimeMode,
  WfbFailoverState,
} from "./types";
