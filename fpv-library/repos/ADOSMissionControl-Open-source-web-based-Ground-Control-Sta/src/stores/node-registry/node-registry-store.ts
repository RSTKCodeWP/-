/**
 * @module NodeRegistry/store
 * @description The canonical node-registry Zustand store: the one source of
 * fleet identity, keyed by a stable `nodeId`. Reducers feed presence,
 * connection, and FC sub-states independently; the garbage-collection rule
 * removes a row only once it has neither a presence source nor an attached
 * flight controller.
 *
 * Ships dark: this store is intentionally not imported anywhere yet and
 * changes no existing behavior. The bridges will later feed it and project
 * its entries back into the existing fleet shape.
 *
 * @license GPL-3.0-only
 */

import { create } from "zustand";

import {
  dropPresenceSource,
  emptyEntry,
  mergeConnection,
  mergeFcTelemetry,
  mergePresence,
  shouldRemoveEntry,
} from "./reconcile";
import type {
  NodeConnection,
  NodeEntry,
  NodeFc,
  NodePresence,
  PresenceSource,
} from "./types";

export interface NodeRegistryState {
  /** All known nodes, keyed by stable nodeId. */
  nodes: Record<string, NodeEntry>;
  /** Epoch ms of the last mutation, for cheap change detection. */
  lastUpdate: number;
}

export interface NodeRegistryActions {
  /**
   * Upsert a presence observation for `nodeId` from `source`. Creates the
   * entry if absent. Cloud-authoritative identity fields win when supplied;
   * the freshest heartbeat is kept; `source` is added to the sources list.
   */
  upsertPresence: (
    nodeId: string,
    presence: Partial<NodePresence>,
    source: PresenceSource,
  ) => void;

  /**
   * Drop a single presence `source` for `nodeId`. If that removes the last
   * presence source and no FC is attached, the entry is garbage-collected.
   */
  dropPresence: (nodeId: string, source: PresenceSource) => void;

  /**
   * Attach a flight controller (by its drone-manager managed id) to a node.
   * Creates the entry if absent. While attached the entry survives GC even
   * with zero presence sources (a direct-USB FC has no agent presence).
   */
  attachFc: (nodeId: string, managedId: string) => void;

  /**
   * Detach the flight controller from `nodeId` (clear managedId). Presence and
   * connection are left intact; if the node then has no presence sources it is
   * garbage-collected.
   */
  detachFc: (nodeId: string) => void;

  /** Merge a connection patch (transport, mavlinkUrl, fcConnected) for a node. */
  updateConnection: (
    nodeId: string,
    connection: Partial<NodeConnection>,
  ) => void;

  /** Merge FC telemetry into a node's FC sub-state (managedId preserved). */
  updateFcTelemetry: (nodeId: string, telemetry: Partial<NodeFc>) => void;

  /** Read a single entry, or undefined if absent. */
  getEntry: (nodeId: string) => NodeEntry | undefined;

  /** Remove every entry. */
  clear: () => void;
}

export type NodeRegistryStore = NodeRegistryState & NodeRegistryActions;

/**
 * Apply a transform to one entry (creating it if absent) and run the GC rule
 * on the result, returning the next `nodes` map. Pure given `nodes`.
 */
function applyToEntry(
  nodes: Record<string, NodeEntry>,
  nodeId: string,
  transform: (entry: NodeEntry) => NodeEntry,
): Record<string, NodeEntry> {
  const existing = nodes[nodeId] ?? emptyEntry(nodeId);
  const updated = transform(existing);
  const next = { ...nodes };
  if (shouldRemoveEntry(updated)) {
    delete next[nodeId];
  } else {
    next[nodeId] = updated;
  }
  return next;
}

export const useNodeRegistryStore = create<NodeRegistryStore>((set, get) => ({
  nodes: {},
  lastUpdate: 0,

  upsertPresence: (nodeId, presence, source) =>
    set((state) => ({
      nodes: applyToEntry(state.nodes, nodeId, (entry) => ({
        ...entry,
        presence: mergePresence(entry.presence, presence, source),
      })),
      lastUpdate: Date.now(),
    })),

  dropPresence: (nodeId, source) =>
    set((state) => {
      if (!state.nodes[nodeId]) return state;
      return {
        nodes: applyToEntry(state.nodes, nodeId, (entry) => ({
          ...entry,
          presence: dropPresenceSource(entry.presence, source),
        })),
        lastUpdate: Date.now(),
      };
    }),

  attachFc: (nodeId, managedId) =>
    set((state) => ({
      nodes: applyToEntry(state.nodes, nodeId, (entry) => ({
        ...entry,
        fc: { ...entry.fc, managedId },
      })),
      lastUpdate: Date.now(),
    })),

  detachFc: (nodeId) =>
    set((state) => {
      if (!state.nodes[nodeId]) return state;
      return {
        nodes: applyToEntry(state.nodes, nodeId, (entry) => ({
          ...entry,
          fc: { ...entry.fc, managedId: null },
        })),
        lastUpdate: Date.now(),
      };
    }),

  updateConnection: (nodeId, connection) =>
    set((state) => {
      if (!state.nodes[nodeId]) return state;
      return {
        nodes: applyToEntry(state.nodes, nodeId, (entry) => ({
          ...entry,
          connection: mergeConnection(entry.connection, connection),
        })),
        lastUpdate: Date.now(),
      };
    }),

  updateFcTelemetry: (nodeId, telemetry) =>
    set((state) => {
      if (!state.nodes[nodeId]) return state;
      return {
        nodes: applyToEntry(state.nodes, nodeId, (entry) => ({
          ...entry,
          fc: mergeFcTelemetry(entry.fc, telemetry),
        })),
        lastUpdate: Date.now(),
      };
    }),

  getEntry: (nodeId) => get().nodes[nodeId],

  clear: () => set({ nodes: {}, lastUpdate: Date.now() }),
}));
