/**
 * @module NodeRegistry
 * @description Public barrel for the canonical node-registry store. The store
 * is the eventual single source of fleet identity, keyed by a stable nodeId,
 * with presence / connection / FC as independent sub-states.
 *
 * Ships dark: nothing imports this barrel yet, and it changes no existing
 * behavior.
 *
 * @license GPL-3.0-only
 */

export { useNodeRegistryStore } from "./node-registry-store";
export type {
  NodeRegistryActions,
  NodeRegistryState,
  NodeRegistryStore,
} from "./node-registry-store";

export {
  resolveNodeId,
  shouldRemoveEntry,
  emptyEntry,
  emptyPresence,
  emptyConnection,
  emptyFc,
  mergePresence,
  dropPresenceSource,
  mergeConnection,
  mergeFcTelemetry,
} from "./reconcile";

export type {
  NodeArmState,
  NodeCloudPosture,
  NodeConnection,
  NodeEntry,
  NodeFc,
  NodeFcBattery,
  NodeFcGps,
  NodeFcPosition,
  NodePresence,
  NodeProfile,
  NodeRole,
  NodeTransport,
  PresenceSource,
} from "./types";
