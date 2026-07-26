/**
 * @module client-broadcasts
 * @description Outbound DroneCAN broadcast helpers used by the client.
 * Pulled out of `client.ts` to keep that file under the 500 LOC hard cap.
 *
 * @license GPL-3.0-only
 */

import { DEFAULT_PRIORITY } from "./frame-codec";
import { DATA_TYPE_IDS, DSDL_SIGNATURES } from "./signatures";
import { encodeRawCommand } from "./dsdl/esc-raw-command";
import { typeNameFor, type AnyTransferEvent } from "./client-types";
import type { OutboundTransfer } from "./transfer-coder";

/** Input arguments for building an ESC RawCommand broadcast. */
export interface BroadcastEscRawCommandArgs {
  cmd: number[];
  selfNodeId: number;
  transferId: number;
}

/**
 * Compose the outbound transfer descriptor, the encoded payload, and the
 * matching bus-log event for a single ESC RawCommand broadcast.
 */
export function buildEscRawCommandBroadcast(args: BroadcastEscRawCommandArgs): {
  descriptor: OutboundTransfer;
  payload: Uint8Array;
  event: AnyTransferEvent;
} {
  const payload = encodeRawCommand({ cmd: args.cmd });
  const descriptor: OutboundTransfer = {
    priority: DEFAULT_PRIORITY,
    dataTypeId: DATA_TYPE_IDS.EscRawCommand,
    srcNodeId: args.selfNodeId,
    transferId: args.transferId,
    signature: DSDL_SIGNATURES.EscRawCommand,
  };
  const event: AnyTransferEvent = {
    ts: Date.now(),
    kind: "message",
    srcNodeId: args.selfNodeId,
    dataTypeId: DATA_TYPE_IDS.EscRawCommand,
    typeName: typeNameFor(DATA_TYPE_IDS.EscRawCommand, "message"),
    transferId: args.transferId,
    priority: DEFAULT_PRIORITY,
    payload,
  };
  return { descriptor, payload, event };
}
