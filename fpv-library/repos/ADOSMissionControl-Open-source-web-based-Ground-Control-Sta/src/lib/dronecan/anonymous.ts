/**
 * @module anonymous
 * @description Anonymous-frame discriminator. The 14-bit discriminator on an
 * anonymous broadcast is the low 14 bits of CRC-16-CCITT over the message
 * payload (poly 0x1021, init 0xFFFF, MSB-first). Two nodes that simultaneously
 * announce themselves use the discriminator to disambiguate their otherwise
 * identical frames during node-ID allocation.
 * @license GPL-3.0-only
 */

import { crcCcitt } from "./crc";

/**
 * Compute the 14-bit anonymous discriminator over the given payload.
 * @returns A 14-bit value in the range 0..0x3FFF.
 */
export function computeAnonymousDiscriminator(payload: Uint8Array): number {
  const crc = crcCcitt(payload, 0xffff);
  return crc & 0x3fff;
}
