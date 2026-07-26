/**
 * DataView helpers shared by every iNav MSP decoder. All multi-byte reads
 * are little-endian to match MSP wire convention.
 *
 * @module protocol/msp/decoders/inav/helpers
 */

export function readU8(dv: DataView, offset: number): number {
  return dv.getUint8(offset);
}

export function readU16(dv: DataView, offset: number): number {
  return dv.getUint16(offset, true);
}

export function readS16(dv: DataView, offset: number): number {
  return dv.getInt16(offset, true);
}

export function readS32(dv: DataView, offset: number): number {
  return dv.getInt32(offset, true);
}

export function readU32(dv: DataView, offset: number): number {
  return dv.getUint32(offset, true);
}

export function readFloat32(dv: DataView, offset: number): number {
  return dv.getFloat32(offset, true);
}

/** Read a null-terminated ASCII string starting at offset. Returns `[string, bytesConsumed]`. */
export function readCString(dv: DataView, offset: number): [string, number] {
  let end = offset;
  while (end < dv.byteLength && dv.getUint8(end) !== 0) end++;
  const bytes = new Uint8Array(dv.buffer, dv.byteOffset + offset, end - offset);
  const str = String.fromCharCode(...bytes);
  return [str, end - offset + 1]; // +1 for null terminator
}
