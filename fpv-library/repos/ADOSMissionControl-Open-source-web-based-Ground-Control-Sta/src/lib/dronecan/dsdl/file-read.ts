/**
 * @module file-read
 * @description Codec for `uavcan.protocol.file.Read` (service type id 48).
 *
 * Request layout:
 *   uint40 offset            (5 bytes little-endian)
 *   uint8[<=200] path        (tail-array)
 *
 * Response layout:
 *   Error error              (int16 value, 2 bytes little-endian, signed)
 *   uint8[<=256] data        (tail-array)
 *
 * EOF semantics: a response is considered the last response when its
 * `data.length < 256`. A zero-length response is allowed and explicit; the
 * server pads with an empty response after a file whose size is an exact
 * multiple of 256 bytes.
 * @license GPL-3.0-only
 */

export const FILE_READ_MAX_DATA = 256;

export interface FileReadError {
  value: number; // signed 16-bit
}

export interface FileReadRequest {
  offset: bigint;
  path: string;
}

export interface FileReadResponse {
  error: FileReadError;
  data: Uint8Array;
}

const FF = BigInt(0xff);
const EIGHT = BigInt(8);
const MASK_40 = (BigInt(1) << BigInt(40)) - BigInt(1);

export function encodeFileReadRequest(req: FileReadRequest): Uint8Array {
  const pathBytes = new TextEncoder().encode(req.path);
  if (pathBytes.length > 200) {
    throw new Error("path must be <= 200 bytes");
  }
  const out = new Uint8Array(5 + pathBytes.length);
  let v = req.offset & MASK_40;
  for (let i = 0; i < 5; i++) {
    out[i] = Number(v & FF);
    v >>= EIGHT;
  }
  out.set(pathBytes, 5);
  return out;
}

export function decodeFileReadRequest(buf: Uint8Array): FileReadRequest {
  if (buf.length < 5) {
    throw new Error(`FileReadRequest too short: ${buf.length}`);
  }
  let off = BigInt(0);
  for (let i = 0; i < 5; i++) {
    off |= BigInt(buf[i]) << BigInt(i * 8);
  }
  const path = new TextDecoder().decode(buf.subarray(5));
  return { offset: off, path };
}

export function encodeFileReadResponse(res: FileReadResponse): Uint8Array {
  if (res.data.length > FILE_READ_MAX_DATA) {
    throw new Error("FileReadResponse.data must be <= 256 bytes");
  }
  const out = new Uint8Array(2 + res.data.length);
  const dv = new DataView(out.buffer);
  dv.setInt16(0, res.error.value, true);
  out.set(res.data, 2);
  return out;
}

export function decodeFileReadResponse(buf: Uint8Array): FileReadResponse {
  if (buf.length < 2) {
    throw new Error(`FileReadResponse too short: ${buf.length}`);
  }
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  return {
    error: { value: dv.getInt16(0, true) },
    data: new Uint8Array(buf.subarray(2)),
  };
}

/**
 * EOF predicate per the DroneCAN file-read protocol: a response with fewer
 * than 256 data bytes marks the end of the file.
 */
export function isFileReadEof(res: FileReadResponse): boolean {
  return res.data.length < FILE_READ_MAX_DATA;
}
