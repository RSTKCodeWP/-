/**
 * @module timestamp
 * @description Codec helper for `uavcan.Timestamp`.
 *
 * Wire layout (56 bits):
 *   uint56  usec      microseconds since some monotonic epoch
 *
 * The field composes inside larger DSDL types via `BitReader` / `BitWriter`,
 * so the helpers below take the bit stream rather than allocating their own
 * byte buffers.
 *
 * @license GPL-3.0-only
 */

import { BitReader, BitWriter } from "../bit-buffer";

/** A monotonic microsecond timestamp. */
export interface Timestamp {
  usecMonotonic: bigint;
}

/** Width of a `uavcan.Timestamp` field in bits. */
export const TIMESTAMP_BITS = 56;

/** Read a `Timestamp` from the current position in a `BitReader`. */
export function decodeTimestamp(r: BitReader): Timestamp {
  return { usecMonotonic: r.readBig(TIMESTAMP_BITS, false) };
}

/** Write a `Timestamp` at the current position in a `BitWriter`. */
export function encodeTimestamp(w: BitWriter, t: Timestamp): void {
  w.writeBig(t.usecMonotonic, TIMESTAMP_BITS);
}
