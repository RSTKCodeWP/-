/**
 * @module get-node-info
 * @description Codec for `uavcan.protocol.GetNodeInfo` (service type id 1).
 *
 * Request is empty.
 *
 * Response layout (variable length, up to ~313 bytes):
 *   NodeStatus            (7 bytes)
 *   SoftwareVersion       (15 bytes)
 *     uint8  major
 *     uint8  minor
 *     uint8  optional_field_flags
 *     uint32 vcs_commit         (little-endian)
 *     uint64 image_crc          (little-endian)
 *   HardwareVersion       (variable: 18 + N bytes)
 *     uint8  major
 *     uint8  minor
 *     uint8[16] unique_id
 *     uint8  certificate_len    (length prefix for COA bytes, 0..255)
 *     uint8[certificate_len] certificate_of_authenticity
 *   uint8[<=80] name      (tail-array, no length prefix when last)
 * @license GPL-3.0-only
 */

import {
  decodeNodeStatus,
  encodeNodeStatus,
  type NodeStatus,
  NODE_STATUS_SIZE,
} from "./node-status";

export interface SoftwareVersion {
  major: number;
  minor: number;
  optional_field_flags: number;
  vcs_commit: number;
  image_crc: bigint;
}

export interface HardwareVersion {
  major: number;
  minor: number;
  unique_id: Uint8Array; // length 16
  certificate_of_authenticity: Uint8Array; // length 0..255
}

export interface GetNodeInfoResponse {
  status: NodeStatus;
  software_version: SoftwareVersion;
  hardware_version: HardwareVersion;
  name: string;
}

export function encodeGetNodeInfoRequest(): Uint8Array {
  return new Uint8Array(0);
}

export function decodeGetNodeInfoRequest(_buf: Uint8Array): void {
  // No fields.
}

export function encodeGetNodeInfoResponse(res: GetNodeInfoResponse): Uint8Array {
  if (res.hardware_version.unique_id.length !== 16) {
    throw new Error("HardwareVersion.unique_id must be 16 bytes");
  }
  const nameBytes = new TextEncoder().encode(res.name);
  if (nameBytes.length > 80) {
    throw new Error("GetNodeInfoResponse.name must be <= 80 bytes");
  }
  const coa = res.hardware_version.certificate_of_authenticity;
  if (coa.length > 255) {
    throw new Error("certificate_of_authenticity must be <= 255 bytes");
  }

  const out = new Uint8Array(
    NODE_STATUS_SIZE + 15 + 19 + coa.length + nameBytes.length,
  );
  let off = 0;
  out.set(encodeNodeStatus(res.status), off);
  off += NODE_STATUS_SIZE;

  // SoftwareVersion
  const dv = new DataView(out.buffer);
  out[off++] = res.software_version.major & 0xff;
  out[off++] = res.software_version.minor & 0xff;
  out[off++] = res.software_version.optional_field_flags & 0xff;
  dv.setUint32(off, res.software_version.vcs_commit >>> 0, true);
  off += 4;
  // image_crc 64-bit little-endian
  let crc = res.software_version.image_crc;
  const FF = BigInt(0xff);
  const EIGHT = BigInt(8);
  for (let i = 0; i < 8; i++) {
    out[off++] = Number(crc & FF);
    crc >>= EIGHT;
  }

  // HardwareVersion
  out[off++] = res.hardware_version.major & 0xff;
  out[off++] = res.hardware_version.minor & 0xff;
  out.set(res.hardware_version.unique_id, off);
  off += 16;
  out[off++] = coa.length & 0xff;
  out.set(coa, off);
  off += coa.length;

  // name (tail-array, no length prefix)
  out.set(nameBytes, off);

  return out;
}

export function decodeGetNodeInfoResponse(buf: Uint8Array): GetNodeInfoResponse {
  if (buf.length < NODE_STATUS_SIZE + 15 + 18) {
    throw new Error(`GetNodeInfoResponse payload too short: ${buf.length}`);
  }
  let off = 0;
  const status = decodeNodeStatus(buf.subarray(off, off + NODE_STATUS_SIZE));
  off += NODE_STATUS_SIZE;

  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  const swMajor = buf[off++];
  const swMinor = buf[off++];
  const swFlags = buf[off++];
  const vcs = dv.getUint32(off, true);
  off += 4;
  let imageCrc = BigInt(0);
  for (let i = 0; i < 8; i++) {
    imageCrc |= BigInt(buf[off + i]) << BigInt(i * 8);
  }
  off += 8;

  const hwMajor = buf[off++];
  const hwMinor = buf[off++];
  const uniqueId = new Uint8Array(buf.subarray(off, off + 16));
  off += 16;
  const coaLen = buf[off++];
  const coa = new Uint8Array(buf.subarray(off, off + coaLen));
  off += coaLen;

  const nameBytes = buf.subarray(off);
  const name = new TextDecoder().decode(nameBytes);

  return {
    status,
    software_version: {
      major: swMajor,
      minor: swMinor,
      optional_field_flags: swFlags,
      vcs_commit: vcs,
      image_crc: imageCrc,
    },
    hardware_version: {
      major: hwMajor,
      minor: hwMinor,
      unique_id: uniqueId,
      certificate_of_authenticity: coa,
    },
    name,
  };
}
