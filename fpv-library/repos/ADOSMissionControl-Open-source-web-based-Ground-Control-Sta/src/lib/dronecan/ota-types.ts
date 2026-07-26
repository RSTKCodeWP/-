/**
 * @module ota-types
 * @description Shared types and percent-bracket helpers for the DroneCAN OTA
 * orchestrator. Split from `ota.ts` to keep that file under the 500-LOC hard
 * rule.
 * @license GPL-3.0-only
 */

/** OTA lifecycle states. */
export type OtaState =
  | "IDLE"
  | "ARMING"
  | "BEGIN_SENT"
  | "TRANSFERRING"
  | "REBOOTING"
  | "VERIFYING"
  | "DONE"
  | "ABORTED"
  | "FAILED";

/** Stable error codes surfaced on failure. */
export type OtaErrorCode =
  | "BEGIN_REJECTED"
  | "TIMEOUT"
  | "NODE_GONE"
  | "CRC_MISMATCH"
  | "USER_ABORTED"
  | "TRANSPORT_LOST"
  | "VERSION_MISMATCH"
  | "INVALID_ARGS";

/** Single transition row for the snapshot log. */
export interface OtaTransitionLogEntry {
  ts: number;
  from: OtaState;
  to: OtaState;
  note?: string;
}

/** Single RPC trace row for the snapshot log. */
export interface OtaRpcTraceEntry {
  ts: number;
  kind: "request" | "response" | "message";
  type: string;
  dir: "out" | "in";
  latencyMs?: number;
  ok: boolean;
}

/** Snapshot delivered to subscribers. */
export interface OtaSnapshot {
  state: OtaState;
  percent: number;
  bytesSent: number;
  bytesTotal: number;
  lastOffset: number;
  lastChunkLen: number;
  retries: number;
  timeouts: number;
  beginError?: number;
  lastNodeStatus?: {
    mode: number;
    health: number;
    uptime_sec: number;
  };
  transitionLog: OtaTransitionLogEntry[];
  rpcTrace: OtaRpcTraceEntry[];
  errorCode?: OtaErrorCode;
  errorMessage?: string;
}

/** Caller-provided OTA start arguments. */
export interface OtaStartOptions {
  targetNodeId: number;
  fileBytes: Uint8Array;
  expectedSwVersion?: { major: number; minor: number };
  /** Node ID listed inside the BeginFirmwareUpdate request. Defaults to self. */
  sourceNodeId?: number;
}

/** Per-state percent bracket. */
export const PERCENT_ARMING_END = 3;
export const PERCENT_BEGIN_END = 10;
export const PERCENT_TRANSFER_END = 90;
export const PERCENT_REBOOTING_END = 95;
export const PERCENT_VERIFY_END = 100;

/** Timer windows (ms). */
export const BEGIN_TIMEOUT_MS = 2000;
export const ENTER_SU_TIMEOUT_MS = 5000;
export const STALL_AFTER_BEGIN_MS = 5000;
export const REBOOT_TIMEOUT_MS = 30000;
export const VERIFY_TIMEOUT_MS = 15000;

/** The remote file path the orchestrator serves. */
export const REMOTE_PATH = "a.bin";

/** Internal mutable state captured by the orchestrator. */
export interface InternalState {
  state: OtaState;
  bytesSent: number;
  lastOffset: number;
  lastChunkLen: number;
  retries: number;
  timeouts: number;
  highestOffset: number;
  beginError?: number;
  lastNodeStatus?: {
    mode: number;
    health: number;
    uptime_sec: number;
  };
  errorCode?: OtaErrorCode;
  errorMessage?: string;
  resolved: boolean;
}

export function freshState(): InternalState {
  return {
    state: "IDLE",
    bytesSent: 0,
    lastOffset: 0,
    lastChunkLen: 0,
    retries: 0,
    timeouts: 0,
    highestOffset: 0,
    resolved: false,
  };
}

export function computePercent(state: InternalState, total: number): number {
  switch (state.state) {
    case "IDLE":
      return 0;
    case "ARMING":
      return PERCENT_ARMING_END;
    case "BEGIN_SENT":
      return PERCENT_BEGIN_END;
    case "TRANSFERRING": {
      const span = PERCENT_TRANSFER_END - PERCENT_BEGIN_END;
      if (total <= 0) return PERCENT_BEGIN_END;
      const fraction = Math.min(1, state.highestOffset / total);
      return PERCENT_BEGIN_END + span * fraction;
    }
    case "REBOOTING":
      return PERCENT_REBOOTING_END;
    case "VERIFYING":
      return PERCENT_VERIFY_END - 2;
    case "DONE":
      return PERCENT_VERIFY_END;
    case "ABORTED":
    case "FAILED":
      return state.bytesSent > 0
        ? PERCENT_BEGIN_END +
            (PERCENT_TRANSFER_END - PERCENT_BEGIN_END) *
              (total > 0 ? state.highestOffset / total : 0)
        : 0;
  }
}
