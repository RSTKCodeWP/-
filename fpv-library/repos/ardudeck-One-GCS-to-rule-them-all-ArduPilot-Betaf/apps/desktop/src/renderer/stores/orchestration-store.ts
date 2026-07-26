/**
 * Orchestration server state: capabilities advertised by each connected
 * orchestration link plus the latest control-plane updates (intent acks /
 * status / errors). Fed by COMMS_ORCHESTRATION_STATUS.
 */

import { create } from 'zustand';
import type { OrchestrationStatusIpc, OrchestrationRosterEntry } from '../../shared/ipc-channels';

export interface OrchestrationServerState {
  transportId: string;
  serverName: string;
  serverVersion: string;
  capabilities: string[];
  /** Most recent control message, summarized for display. */
  lastControl: { type?: string; id?: string; state?: string; message?: string } | null;
  /** Fleet identity: each presented virtual sysid -> durable UUID + bearer. */
  roster: OrchestrationRosterEntry[];
}

interface OrchestrationStore {
  servers: Record<string, OrchestrationServerState>;
  applyStatus: (status: OrchestrationStatusIpc) => void;
  removeServer: (transportId: string) => void;
  clear: () => void;
}

export const useOrchestrationStore = create<OrchestrationStore>((set, get) => ({
  servers: {},

  applyStatus: (status) => {
    const prev = get().servers[status.transportId];
    const base: OrchestrationServerState = prev ?? {
      transportId: status.transportId,
      serverName: 'orchestration server',
      serverVersion: '',
      capabilities: [],
      lastControl: null,
      roster: [],
    };
    let next: OrchestrationServerState;
    if (status.kind === 'welcome') {
      next = {
        ...base,
        serverName: status.serverName ?? base.serverName,
        serverVersion: status.serverVersion ?? base.serverVersion,
        capabilities: status.capabilities ?? base.capabilities,
      };
    } else if (status.kind === 'roster') {
      next = { ...base, roster: status.roster ?? base.roster };
    } else {
      next = {
        ...base,
        lastControl: status.control
          ? { type: status.control.type, id: status.control.id, state: status.control.state, message: status.control.message }
          : base.lastControl,
      };
    }
    set({ servers: { ...get().servers, [status.transportId]: next } });
  },

  removeServer: (transportId) => {
    const next = { ...get().servers };
    delete next[transportId];
    set({ servers: next });
  },

  clear: () => set({ servers: {} }),
}));
