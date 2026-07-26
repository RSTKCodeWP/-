/**
 * @module get-transport-stats
 * @description Codec for `uavcan.protocol.GetTransportStats` (service id 4).
 *
 * Request is empty.
 *
 * Response layout:
 *   uint48  transfer_count
 *   uint48  message_count
 *   uint48  error_count
 *   CanIfaceStats[<=3]  can_iface_stats   (tail-array of fixed-size items)
 *
 * CanIfaceStats layout (18 bytes each):
 *   uint48  frames_tx
 *   uint48  frames_rx
 *   uint48  errors
 *
 * Each uint48 is encoded as 6 little-endian bytes.
 * @license GPL-3.0-only
 */

export interface CanIfaceStats {
  frames_tx: bigint;
  frames_rx: bigint;
  errors: bigint;
}

export interface GetTransportStatsResponse {
  transfer_count: bigint;
  message_count: bigint;
  error_count: bigint;
  can_iface_stats: CanIfaceStats[];
}

const TS_ZERO = BigInt(0);
const TS_ONE = BigInt(1);
const TS_FF = BigInt(0xff);
const TS_EIGHT = BigInt(8);
const MASK_48 = (TS_ONE << BigInt(48)) - TS_ONE;

function encodeUint48(value: bigint): Uint8Array {
  const out = new Uint8Array(6);
  let v = value & MASK_48;
  for (let i = 0; i < 6; i++) {
    out[i] = Number(v & TS_FF);
    v >>= TS_EIGHT;
  }
  return out;
}

function decodeUint48(buf: Uint8Array, off: number): bigint {
  let v = TS_ZERO;
  for (let i = 0; i < 6; i++) {
    v |= BigInt(buf[off + i] ?? 0) << BigInt(i * 8);
  }
  return v;
}

export function encodeGetTransportStatsRequest(): Uint8Array {
  return new Uint8Array(0);
}

export function decodeGetTransportStatsRequest(_buf: Uint8Array): void {
  // No fields.
}

export function encodeGetTransportStatsResponse(
  res: GetTransportStatsResponse,
): Uint8Array {
  if (res.can_iface_stats.length > 3) {
    throw new Error("can_iface_stats must have at most 3 entries");
  }
  const out = new Uint8Array(18 + res.can_iface_stats.length * 18);
  let off = 0;
  out.set(encodeUint48(res.transfer_count), off);
  off += 6;
  out.set(encodeUint48(res.message_count), off);
  off += 6;
  out.set(encodeUint48(res.error_count), off);
  off += 6;
  for (const s of res.can_iface_stats) {
    out.set(encodeUint48(s.frames_tx), off);
    off += 6;
    out.set(encodeUint48(s.frames_rx), off);
    off += 6;
    out.set(encodeUint48(s.errors), off);
    off += 6;
  }
  return out;
}

export function decodeGetTransportStatsResponse(
  buf: Uint8Array,
): GetTransportStatsResponse {
  if (buf.length < 18) {
    throw new Error(`GetTransportStatsResponse too short: ${buf.length}`);
  }
  let off = 0;
  const transfer_count = decodeUint48(buf, off);
  off += 6;
  const message_count = decodeUint48(buf, off);
  off += 6;
  const error_count = decodeUint48(buf, off);
  off += 6;

  const ifaces: CanIfaceStats[] = [];
  while (off + 18 <= buf.length && ifaces.length < 3) {
    const frames_tx = decodeUint48(buf, off);
    off += 6;
    const frames_rx = decodeUint48(buf, off);
    off += 6;
    const errors = decodeUint48(buf, off);
    off += 6;
    ifaces.push({ frames_tx, frames_rx, errors });
  }

  return {
    transfer_count,
    message_count,
    error_count,
    can_iface_stats: ifaces,
  };
}
