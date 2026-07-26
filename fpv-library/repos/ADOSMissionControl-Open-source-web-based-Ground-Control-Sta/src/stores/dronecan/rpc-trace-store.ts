/**
 * @module dronecan/rpc-trace-store
 * @description Zustand store for the DroneCAN RPC / service-call trace view.
 *
 * Holds a ring buffer of recent service requests, responses, broadcasts, and
 * file-read traffic, plus a small filter object the trace panel uses to
 * narrow the displayed list. Cap is 512 events.
 *
 * @license GPL-3.0-only
 */

import { create } from "zustand";
import { RingBuffer } from "@/lib/ring-buffer";

export type RpcEventKind =
  | "request"
  | "response"
  | "broadcast"
  | "file_read_req"
  | "file_read_resp";

export interface RpcEvent {
  t: number;
  kind: RpcEventKind;
  direction: "in" | "out";
  dataTypeId: number;
  dataTypeName: string;
  srcNodeId?: number;
  dstNodeId?: number;
  latencyMs?: number;
  ok: boolean;
  decoded?: unknown;
}

export interface RpcTraceFilters {
  nodeId?: number;
  type?: string;
  errorsOnly?: boolean;
}

const EVENT_CAP = 512;

interface RpcTraceStoreState {
  events: RingBuffer<RpcEvent>;
  filters: RpcTraceFilters;
  _version: number;

  pushEvent: (event: RpcEvent) => void;
  clear: () => void;
  setFilters: (partial: Partial<RpcTraceFilters>) => void;
}

export const useDroneCanRpcTraceStore = create<RpcTraceStoreState>(
  (set, get) => ({
    events: new RingBuffer<RpcEvent>(EVENT_CAP),
    filters: {},
    _version: 0,

    pushEvent: (event) => {
      get().events.push(event);
      set({ _version: get()._version + 1 });
    },

    clear: () => {
      get().events.clear();
      set({ _version: get()._version + 1 });
    },

    setFilters: (partial) => {
      const next: RpcTraceFilters = { ...get().filters, ...partial };
      // Drop keys explicitly set to undefined so the filters object stays
      // minimal and `Object.keys(filters).length` reflects active filters.
      for (const k of Object.keys(partial) as (keyof RpcTraceFilters)[]) {
        if (partial[k] === undefined) {
          delete next[k];
        }
      }
      set({ filters: next, _version: get()._version + 1 });
    },
  }),
);
