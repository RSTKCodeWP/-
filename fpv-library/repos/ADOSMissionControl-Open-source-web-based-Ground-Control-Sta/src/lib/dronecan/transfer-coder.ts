/**
 * @module transfer-coder
 * @description Multi-frame transfer assembly and disassembly for DroneCAN.
 *
 * Single-frame transfers (payload <= 7 bytes) carry the payload bytes followed
 * by a single tail byte with SOT=1, EOT=1, TOGGLE=0, and the 5-bit transfer
 * ID. No CRC.
 *
 * Multi-frame transfers prepend a 16-bit CRC over (signature || payload) and
 * fragment the resulting buffer into 7-byte chunks, each followed by a tail
 * byte. The toggle bit alternates per frame, starting at 0 on the first frame.
 * The first frame carries: CRC_LO | CRC_HI | 5 payload bytes | tail. Each
 * subsequent frame carries up to 7 payload bytes | tail.
 *
 * The decoder is a simple state machine keyed by (src node, data type, kind,
 * transfer ID). It buffers fragments until EOT, verifies the toggle sequence
 * and the CRC, and emits the reassembled payload. Stale buffers are flushed
 * after a 2-second reassembly timeout.
 * @license GPL-3.0-only
 */

import {
  decodeId,
  decodeTailByte,
  encodeAnonymousMessageId,
  encodeMessageId,
  encodeServiceId,
  encodeTailByte,
} from "./frame-codec";
import { transferCrc } from "./crc";
import { computeAnonymousDiscriminator } from "./anonymous";

/** Maximum payload bytes carried in a single frame. */
const MAX_SINGLE_FRAME_PAYLOAD = 7;

/** Maximum payload bytes on the FIRST frame of a multi-frame transfer (after CRC). */
const FIRST_FRAME_PAYLOAD_AFTER_CRC = 5;

/** Maximum payload bytes on a subsequent multi-frame frame. */
const NEXT_FRAME_PAYLOAD = 7;

/** Reassembly timeout in milliseconds. */
const REASSEMBLY_TIMEOUT_MS = 2000;

/** Descriptor for an outbound transfer. */
export interface OutboundTransfer {
  /** Priority 0..31 (0 = highest). */
  priority: number;
  /** Data type ID. Message types are 16-bit, services are 8-bit. */
  dataTypeId: number;
  /** Source node ID 1..127, or 0 for an anonymous broadcast. */
  srcNodeId: number;
  /** Destination node ID for service frames. Ignored for messages. */
  dstNodeId?: number;
  /** True for a service request, false for a service response. */
  isRequest?: boolean;
  /** 5-bit transfer ID, claimed from the allocator before sending. */
  transferId: number;
  /** Marks the transfer as anonymous. Source node must be 0. */
  isAnonymous?: boolean;
  /** 64-bit signature for the data type, mixed into the multi-frame CRC. */
  signature: bigint;
  /** Whether the encoded ID encodes a service frame. */
  isService?: boolean;
}

/** Single encoded CAN frame ready for the bus. */
export interface EncodedFrame {
  canId: number;
  data: Uint8Array;
}

/** Decoded payload emitted by the reassembler. */
export interface DecodedTransfer {
  srcNodeId: number;
  dstNodeId?: number;
  dataTypeId: number;
  kind: "message" | "service" | "anonymous";
  isRequest?: boolean;
  priority: number;
  transferId: number;
  payload: Uint8Array;
}

/** Options passed to the decoder constructor. */
export interface TransferDecoderOptions {
  /**
   * Resolve a DSDL signature for the given (data type id, kind) tuple. The
   * decoder needs the signature to verify the multi-frame CRC. Return
   * `undefined` to skip CRC verification (single-frame transfers are always
   * accepted because they have no CRC).
   */
  resolveSignature?: (
    dataTypeId: number,
    kind: "message" | "service" | "anonymous",
  ) => bigint | undefined;
  /** Override the default 2-second reassembly timeout. */
  reassemblyTimeoutMs?: number;
}

/**
 * Encode a transfer into a list of CAN frames ready for the bus.
 *
 * Single-frame transfers (payload <= 7) emit one frame with the tail byte
 * marking both start and end. Multi-frame transfers prepend a CRC over the
 * signature and the payload, then fragment.
 */
export function encodeTransfer(
  payload: Uint8Array,
  descriptor: OutboundTransfer,
): EncodedFrame[] {
  const tid = descriptor.transferId & 0x1f;
  const canId = packId(descriptor, payload);

  if (payload.length <= MAX_SINGLE_FRAME_PAYLOAD) {
    const buffer = new Uint8Array(payload.length + 1);
    buffer.set(payload, 0);
    buffer[payload.length] = encodeTailByte(true, true, false, tid);
    return [{ canId, data: buffer }];
  }

  const crc = transferCrc(descriptor.signature, payload);
  const totalLen = payload.length;
  const frames: EncodedFrame[] = [];
  let toggle = false;
  let offset = 0;

  while (offset < totalLen) {
    const isFirst = offset === 0;
    const isLastFrame =
      (isFirst && totalLen <= FIRST_FRAME_PAYLOAD_AFTER_CRC) ||
      (!isFirst && totalLen - offset <= NEXT_FRAME_PAYLOAD);

    if (isFirst) {
      const take = Math.min(FIRST_FRAME_PAYLOAD_AFTER_CRC, totalLen);
      const buffer = new Uint8Array(take + 2 + 1);
      buffer[0] = crc & 0xff;
      buffer[1] = (crc >> 8) & 0xff;
      buffer.set(payload.subarray(0, take), 2);
      buffer[buffer.length - 1] = encodeTailByte(true, isLastFrame, toggle, tid);
      frames.push({ canId, data: buffer });
      offset += take;
    } else {
      const remaining = totalLen - offset;
      const take = Math.min(NEXT_FRAME_PAYLOAD, remaining);
      const buffer = new Uint8Array(take + 1);
      buffer.set(payload.subarray(offset, offset + take), 0);
      buffer[buffer.length - 1] = encodeTailByte(
        false,
        isLastFrame,
        toggle,
        tid,
      );
      frames.push({ canId, data: buffer });
      offset += take;
    }

    toggle = !toggle;
  }

  return frames;
}

function packId(descriptor: OutboundTransfer, payload: Uint8Array): number {
  if (descriptor.isAnonymous) {
    const discriminator = computeAnonymousDiscriminator(payload);
    return encodeAnonymousMessageId(
      descriptor.priority,
      descriptor.dataTypeId,
      discriminator,
    );
  }
  if (descriptor.isService) {
    return encodeServiceId(
      descriptor.priority,
      descriptor.isRequest ?? false,
      descriptor.dataTypeId,
      descriptor.dstNodeId ?? 0,
      descriptor.srcNodeId,
    );
  }
  return encodeMessageId(
    descriptor.priority,
    descriptor.dataTypeId,
    descriptor.srcNodeId,
  );
}

interface PendingTransfer {
  fragments: Uint8Array[];
  expectedToggle: boolean;
  startedAt: number;
  priority: number;
  kind: "message" | "service" | "anonymous";
  isRequest?: boolean;
  srcNodeId: number;
  dstNodeId?: number;
  dataTypeId: number;
  transferId: number;
}

/**
 * Stateful reassembler for inbound CAN frames. Push frames as they arrive and
 * receive whole DroneCAN transfers via the registered callback.
 */
export class TransferDecoder {
  private readonly pending = new Map<string, PendingTransfer>();
  private readonly listeners: Array<(transfer: DecodedTransfer) => void> = [];
  private readonly resolveSignature?: TransferDecoderOptions["resolveSignature"];
  private readonly reassemblyTimeoutMs: number;

  constructor(options: TransferDecoderOptions = {}) {
    this.resolveSignature = options.resolveSignature;
    this.reassemblyTimeoutMs =
      options.reassemblyTimeoutMs ?? REASSEMBLY_TIMEOUT_MS;
  }

  /** Subscribe to assembled transfers. Returns an unsubscribe function. */
  onTransfer(cb: (transfer: DecodedTransfer) => void): () => void {
    this.listeners.push(cb);
    return () => {
      const idx = this.listeners.indexOf(cb);
      if (idx >= 0) this.listeners.splice(idx, 1);
    };
  }

  /** Push a frame's CAN ID and data into the reassembler. */
  push(canId: number, data: Uint8Array, now: number = Date.now()): void {
    if (data.length === 0) return;

    this.sweepStale(now);

    const tail = decodeTailByte(data[data.length - 1]);
    const id = decodeId(canId);
    const payload = data.subarray(0, data.length - 1);

    if (tail.sot && tail.eot) {
      this.emit({
        priority: id.priority,
        srcNodeId:
          id.kind === "anonymous" ? 0 : (id as { srcNodeId: number }).srcNodeId,
        dstNodeId: id.kind === "service" ? id.dstNodeId : undefined,
        dataTypeId:
          id.kind === "service"
            ? id.serviceTypeId
            : (id as { dataTypeId: number }).dataTypeId,
        kind: id.kind,
        isRequest: id.kind === "service" ? id.isRequest : undefined,
        transferId: tail.transferId,
        payload: new Uint8Array(payload),
      });
      return;
    }

    const key = this.keyFromId(canId, tail.transferId);
    if (tail.sot) {
      // New multi-frame transfer.
      if (tail.toggle) {
        // First frame must have toggle=0; drop malformed.
        this.pending.delete(key);
        return;
      }
      this.pending.set(key, {
        fragments: [new Uint8Array(payload)],
        expectedToggle: true,
        startedAt: now,
        priority: id.priority,
        kind: id.kind,
        isRequest: id.kind === "service" ? id.isRequest : undefined,
        srcNodeId:
          id.kind === "anonymous" ? 0 : (id as { srcNodeId: number }).srcNodeId,
        dstNodeId: id.kind === "service" ? id.dstNodeId : undefined,
        dataTypeId:
          id.kind === "service"
            ? id.serviceTypeId
            : (id as { dataTypeId: number }).dataTypeId,
        transferId: tail.transferId,
      });
      return;
    }

    const pending = this.pending.get(key);
    if (!pending) {
      // Fragment without a started transfer; ignore (out-of-order EOT, etc.).
      return;
    }

    if (tail.toggle !== pending.expectedToggle) {
      // Toggle mismatch — drop the buffered transfer.
      this.pending.delete(key);
      return;
    }

    pending.fragments.push(new Uint8Array(payload));
    pending.expectedToggle = !pending.expectedToggle;

    if (tail.eot) {
      this.pending.delete(key);
      this.finalize(pending);
    }
  }

  /** Drop any in-progress reassembly buffers. */
  reset(): void {
    this.pending.clear();
  }

  /** Number of pending in-progress transfers (for diagnostics and tests). */
  get pendingCount(): number {
    return this.pending.size;
  }

  private sweepStale(now: number): void {
    if (this.pending.size === 0) return;
    for (const [key, value] of this.pending) {
      if (now - value.startedAt > this.reassemblyTimeoutMs) {
        this.pending.delete(key);
      }
    }
  }

  private finalize(pending: PendingTransfer): void {
    // Concatenate fragments. The first fragment includes the leading 2-byte
    // transfer CRC.
    let totalLen = 0;
    for (const f of pending.fragments) totalLen += f.length;
    if (totalLen < 2) return;

    const merged = new Uint8Array(totalLen);
    let off = 0;
    for (const f of pending.fragments) {
      merged.set(f, off);
      off += f.length;
    }

    const crcExpected = merged[0] | (merged[1] << 8);
    const payload = merged.subarray(2);

    const signature = this.resolveSignature?.(pending.dataTypeId, pending.kind);
    if (signature !== undefined) {
      const crcActual = transferCrc(signature, new Uint8Array(payload));
      if (crcActual !== crcExpected) {
        // CRC mismatch — drop silently.
        return;
      }
    }

    this.emit({
      priority: pending.priority,
      srcNodeId: pending.srcNodeId,
      dstNodeId: pending.dstNodeId,
      dataTypeId: pending.dataTypeId,
      kind: pending.kind,
      isRequest: pending.isRequest,
      transferId: pending.transferId,
      payload: new Uint8Array(payload),
    });
  }

  private emit(transfer: DecodedTransfer): void {
    for (const l of this.listeners) {
      try {
        l(transfer);
      } catch {
        // Listener errors must not break the reassembler.
      }
    }
  }

  private keyFromId(canId: number, transferId: number): string {
    const id = decodeId(canId);
    if (id.kind === "service") {
      return `svc:${id.srcNodeId}:${id.dstNodeId}:${id.serviceTypeId}:${id.isRequest ? 1 : 0}:${transferId}`;
    }
    if (id.kind === "anonymous") {
      return `anon:${id.dataTypeId}:${transferId}`;
    }
    return `msg:${id.srcNodeId}:${id.dataTypeId}:${transferId}`;
  }
}
