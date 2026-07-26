/**
 * @module FleetNetworkStore
 * @description Zustand store for ADOS Drone Agent fleet network state
 * (MeshNet enrollment and mesh peers).
 * @license GPL-3.0-only
 */

import { create } from "zustand";
import type { MeshNetEnrollment, NetworkPeer } from "@/lib/agent/types";
import { useAgentConnectionStore } from "./agent-connection-store";

interface FleetNetworkState {
  enrollment: MeshNetEnrollment | null;
  peers: NetworkPeer[];
}

interface FleetNetworkActions {
  fetchEnrollment: () => Promise<void>;
  fetchPeers: () => Promise<void>;
  clear: () => void;
}

export type FleetNetworkStore = FleetNetworkState & FleetNetworkActions;

export const useFleetNetworkStore = create<FleetNetworkStore>((set) => ({
  enrollment: null,
  peers: [],

  async fetchEnrollment() {
    const { client, cloudMode } = useAgentConnectionStore.getState();
    if (cloudMode) {
      useAgentConnectionStore.getState().sendCloudCommand("get_enrollment");
      return;
    }
    if (!client) return;
    try {
      const enrollment = await client.getEnrollment();
      set({ enrollment });
    } catch { /* silent */ }
  },

  async fetchPeers() {
    const { client, cloudMode } = useAgentConnectionStore.getState();
    if (cloudMode) {
      useAgentConnectionStore.getState().sendCloudCommand("get_peers");
      return;
    }
    if (!client) return;
    try {
      const peers = await client.getPeers();
      set({ peers });
    } catch { /* silent */ }
  },

  clear() {
    set({
      enrollment: null,
      peers: [],
    });
  },
}));
