/**
 * @module client-types
 * @description Shared types, type-name lookup, and signature resolver used by
 * the DroneCAN client. Lifted out of `client.ts` to keep that file under the
 * 500-LOC hard rule per the GCS code-size convention.
 * @license GPL-3.0-only
 */

import { DATA_TYPE_IDS, DSDL_SIGNATURES } from "./signatures";

/** Direction of an RPC trace event. */
export type RpcDirection = "out" | "in";

/** Kind of transfer surfaced on the bus log. */
export type BusEventKind = "message" | "request" | "response";

/** Per-call options for every service method. */
export interface ServiceCallOptions {
  timeoutMs?: number;
  retries?: number;
}

/** Event emitted to the bus log for every decoded transfer. */
export interface AnyTransferEvent {
  /** Wall-clock timestamp in ms. */
  ts: number;
  kind: BusEventKind;
  /** Source node ID (0 for anonymous). */
  srcNodeId: number;
  /** Destination node ID for service transfers. */
  dstNodeId?: number;
  /** Data type ID. */
  dataTypeId: number;
  /** Friendly name for the type ID, when known. */
  typeName?: string;
  /** Transfer ID. */
  transferId: number;
  /** Frame priority. */
  priority: number;
  /** Payload bytes (defensive copy). */
  payload: Uint8Array;
}

/** Constructor options. */
export interface DroneCanClientOptions {
  /** Self node ID to put on outbound frames. Defaults to 127. */
  selfNodeId?: number;
}

/** File-server lifecycle handle returned by `serveFileReads`. */
export interface FileReadServerHandle {
  stop(): void;
}

/** Options for the file-read server. */
export interface ServeFileReadsOptions {
  fileData: Uint8Array;
  path?: string;
  /** Fired after every served chunk. */
  onChunkServed?: (offset: number, len: number) => void;
}

/** Internal file-server bookkeeping. */
export interface FileReadServerState {
  fileData: Uint8Array;
  path: string;
  onChunkServed?: (offset: number, len: number) => void;
  stop(): void;
}

/** Lookup the human name of a known data type id + kind. */
export function typeNameFor(
  dataTypeId: number,
  kind: "message" | "service",
): string | undefined {
  if (kind === "message") {
    switch (dataTypeId) {
      case DATA_TYPE_IDS.NodeStatus:
        return "NodeStatus";
      case DATA_TYPE_IDS.EscRawCommand:
        return "esc.RawCommand";
      case DATA_TYPE_IDS.GnssFix2:
        return "gnss.Fix2";
      case DATA_TYPE_IDS.MagneticFieldStrength2:
        return "ahrs.MagneticFieldStrength2";
      default:
        return undefined;
    }
  }
  if (kind === "service") {
    switch (dataTypeId) {
      case DATA_TYPE_IDS.GetNodeInfo:
        return "GetNodeInfo";
      case DATA_TYPE_IDS.paramGetSet:
        return "param.GetSet";
      case DATA_TYPE_IDS.paramExecuteOpcode:
        return "param.ExecuteOpcode";
      case DATA_TYPE_IDS.RestartNode:
        return "RestartNode";
      case DATA_TYPE_IDS.fileBeginFirmwareUpdate:
        return "file.BeginFirmwareUpdate";
      case DATA_TYPE_IDS.fileRead:
        return "file.Read";
      case DATA_TYPE_IDS.GetTransportStats:
        return "GetTransportStats";
      default:
        return undefined;
    }
  }
  return undefined;
}

/** Signature resolver used by the inbound transfer decoder for CRC checks. */
export function resolveSignature(
  dataTypeId: number,
  kind: "message" | "service" | "anonymous",
): bigint | undefined {
  if (kind === "message") {
    switch (dataTypeId) {
      case DATA_TYPE_IDS.NodeStatus:
        return DSDL_SIGNATURES.NodeStatus;
      case DATA_TYPE_IDS.EscRawCommand:
        return DSDL_SIGNATURES.EscRawCommand;
      case DATA_TYPE_IDS.GnssFix2:
        return DSDL_SIGNATURES.GnssFix2;
      case DATA_TYPE_IDS.MagneticFieldStrength2:
        return DSDL_SIGNATURES.MagneticFieldStrength2;
      default:
        return undefined;
    }
  }
  if (kind === "service") {
    switch (dataTypeId) {
      case DATA_TYPE_IDS.GetNodeInfo:
        return DSDL_SIGNATURES.GetNodeInfo;
      case DATA_TYPE_IDS.paramGetSet:
        return DSDL_SIGNATURES.paramGetSet;
      case DATA_TYPE_IDS.paramExecuteOpcode:
        return DSDL_SIGNATURES.paramExecuteOpcode;
      case DATA_TYPE_IDS.RestartNode:
        return DSDL_SIGNATURES.RestartNode;
      case DATA_TYPE_IDS.fileBeginFirmwareUpdate:
        return DSDL_SIGNATURES.fileBeginFirmwareUpdate;
      case DATA_TYPE_IDS.fileRead:
        return DSDL_SIGNATURES.fileRead;
      case DATA_TYPE_IDS.GetTransportStats:
        return DSDL_SIGNATURES.GetTransportStats;
      default:
        return undefined;
    }
  }
  return undefined;
}
