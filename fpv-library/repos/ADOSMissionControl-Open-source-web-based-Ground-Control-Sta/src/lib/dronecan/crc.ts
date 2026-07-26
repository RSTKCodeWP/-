/**
 * @module crc
 * @description CRC-16-CCITT used by the DroneCAN transfer layer.
 *
 * Parameters: polynomial 0x1021, initial value 0xFFFF, MSB-first, no
 * reflection, no final XOR. Self-check string "123456789" yields 0x29B1.
 * @license GPL-3.0-only
 */

/** Fold a single byte into a running CRC-16-CCITT value. */
export function crcCcittByte(byte: number, accumulator: number): number {
  let crc = (accumulator ^ ((byte & 0xff) << 8)) & 0xffff;
  for (let bit = 0; bit < 8; bit++) {
    if ((crc & 0x8000) !== 0) {
      crc = ((crc << 1) ^ 0x1021) & 0xffff;
    } else {
      crc = (crc << 1) & 0xffff;
    }
  }
  return crc;
}

/**
 * Compute CRC-16-CCITT over a byte sequence using the given initial value.
 * Pass the previous return value to chain multiple buffers into one CRC.
 */
export function crcCcitt(bytes: Uint8Array, initial = 0xffff): number {
  let crc = initial & 0xffff;
  for (let i = 0; i < bytes.length; i++) {
    crc = crcCcittByte(bytes[i], crc);
  }
  return crc;
}

/**
 * Compute the multi-frame transfer CRC for a payload of a given DSDL type.
 * The signature contributes as eight little-endian bytes prepended to the
 * payload before the CRC accumulator is finalized.
 */
export function transferCrc(
  signature: bigint,
  payload: Uint8Array,
): number {
  const sigBytes = new Uint8Array(8);
  let sig = signature;
  const FF = BigInt(0xff);
  const EIGHT = BigInt(8);
  for (let i = 0; i < 8; i++) {
    sigBytes[i] = Number(sig & FF);
    sig >>= EIGHT;
  }
  let crc = crcCcitt(sigBytes, 0xffff);
  crc = crcCcitt(payload, crc);
  return crc & 0xffff;
}
