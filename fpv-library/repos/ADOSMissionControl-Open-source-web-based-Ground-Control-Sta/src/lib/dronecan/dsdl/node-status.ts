/**
 * @module node-status
 * @description Codec for `uavcan.protocol.NodeStatus` (data type id 341).
 *
 * Wire layout (56 bits, 7 bytes total — fits a single CAN frame, no CRC):
 *   uint32  uptime_sec                       (bytes 0..3, little-endian)
 *   uint2   health                           (byte 4, bits 0..1)
 *   uint3   mode                             (byte 4, bits 2..4)
 *   uint3   sub_mode (reserved, must be 0)   (byte 4, bits 5..7)
 *   uint16  vendor_specific_status_code      (bytes 5..6, little-endian)
 * @license GPL-3.0-only
 */

export const HEALTH_OK = 0;
export const HEALTH_WARNING = 1;
export const HEALTH_ERROR = 2;
export const HEALTH_CRITICAL = 3;

export const MODE_OPERATIONAL = 0;
export const MODE_INITIALIZATION = 1;
export const MODE_MAINTENANCE = 2;
export const MODE_SOFTWARE_UPDATE = 3;
export const MODE_OFFLINE = 7;

export type NodeHealth = 0 | 1 | 2 | 3;
export type NodeMode = 0 | 1 | 2 | 3 | 7;

export interface NodeStatus {
  uptime_sec: number;
  health: NodeHealth;
  mode: NodeMode;
  vendor_specific_status_code: number;
}

/** Wire size of NodeStatus in bytes. */
export const NODE_STATUS_SIZE = 7;

export function encodeNodeStatus(status: NodeStatus): Uint8Array {
  const buf = new Uint8Array(NODE_STATUS_SIZE);
  const dv = new DataView(buf.buffer);
  dv.setUint32(0, status.uptime_sec >>> 0, true);
  const health = status.health & 0x3;
  const mode = status.mode & 0x7;
  buf[4] = (health & 0x3) | ((mode & 0x7) << 2);
  dv.setUint16(5, status.vendor_specific_status_code & 0xffff, true);
  return buf;
}

export function decodeNodeStatus(buf: Uint8Array): NodeStatus {
  if (buf.length < NODE_STATUS_SIZE) {
    throw new Error(`NodeStatus payload too short: ${buf.length}`);
  }
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  const uptime = dv.getUint32(0, true);
  const packed = buf[4];
  const health = (packed & 0x3) as NodeHealth;
  const mode = ((packed >> 2) & 0x7) as NodeMode;
  const vendor = dv.getUint16(5, true);
  return {
    uptime_sec: uptime,
    health,
    mode,
    vendor_specific_status_code: vendor,
  };
}
