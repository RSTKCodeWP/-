/**
 * @module AgentConnectionStore
 * @description Thin re-export shim. The store implementation lives in the
 * `./agent-connection/` slice package. This file exists to preserve the
 * `@/stores/agent-connection-store` import path used across the app.
 * @license GPL-3.0-only
 */

export {
  useAgentConnectionStore,
  type AgentConnectionStore,
  type LocalState,
  type LocalActions,
  type LocalStateSlice,
  type CloudState,
  type CloudActions,
  type CloudStateSlice,
  type ClientManagerActions,
  type ClientManagerSlice,
  type StalePairingInfo,
  type StalePairingReason,
} from "./agent-connection";
