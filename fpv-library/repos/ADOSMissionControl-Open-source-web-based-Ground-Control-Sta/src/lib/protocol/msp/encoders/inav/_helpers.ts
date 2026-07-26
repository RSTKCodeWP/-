/**
 * Local DataView write helpers for iNav MSP encoders. Little-endian to
 * match MSP wire convention.
 *
 * @module protocol/msp/encoders/inav/_helpers
 */

export function writeU8(dv: DataView, offset: number, value: number): void {
  dv.setUint8(offset, value);
}

export function writeU16(dv: DataView, offset: number, value: number): void {
  dv.setUint16(offset, value, true);
}

export function writeU32(dv: DataView, offset: number, value: number): void {
  dv.setUint32(offset, value, true);
}

export function writeS32(dv: DataView, offset: number, value: number): void {
  dv.setInt32(offset, value, true);
}

/** Write a null-terminated ASCII string and return total bytes written (including null). */
export function writeCString(buf: Uint8Array, offset: number, str: string): number {
  for (let i = 0; i < str.length; i++) {
    buf[offset + i] = str.charCodeAt(i);
  }
  buf[offset + str.length] = 0;
  return str.length + 1;
}
