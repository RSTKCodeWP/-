/**
 * CRC32 and utility helpers for PX4 bootloader protocol.
 *
 * @module protocol/firmware/px4-serial-helpers
 */

// ── CRC32 Lookup Table ──────────────────────────────────────

/** Pre-computed CRC32 table (IEEE 802.3 polynomial). */
const CRC32_TABLE = new Uint32Array(256);
for (let i = 0; i < 256; i++) {
  let crc = i;
  for (let j = 0; j < 8; j++) {
    crc = crc & 1 ? (crc >>> 1) ^ 0xedb88320 : crc >>> 1;
  }
  CRC32_TABLE[i] = crc;
}

/** Compute CRC32 over a Uint8Array. */
export function crc32(data: Uint8Array): number {
  let crc = 0xffffffff;
  for (let i = 0; i < data.length; i++) {
    crc = (crc >>> 8) ^ CRC32_TABLE[(crc ^ data[i]) & 0xff];
  }
  return (crc ^ 0xffffffff) >>> 0;
}

// ── PX4 Bootloader Protocol Constants ────────────────────────

export const PX4_BL = {
  INSYNC: 0x12,
  EOC: 0x20,
  OK: 0x10,
  FAILED: 0x11,
  INVALID: 0x13,
  GET_SYNC: 0x21,
  GET_DEVICE: 0x22,
  CHIP_ERASE: 0x23,
  PROG_MULTI: 0x27,
  GET_CRC: 0x29,
  REBOOT: 0x30,
  PROG_MULTI_MAX: 252,
  DEFAULT_TIMEOUT: 5000,
  ERASE_TIMEOUT: 30000,
} as const;

import type { ParsedFirmware } from "./types";

/** Flatten all firmware blocks into a single contiguous Uint8Array. */
export function flattenFirmware(firmware: ParsedFirmware): Uint8Array {
  if (firmware.blocks.length === 1) {
    return firmware.blocks[0].data;
  }
  const total = firmware.blocks.reduce((sum, b) => sum + b.data.length, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const block of firmware.blocks) {
    result.set(block.data, offset);
    offset += block.data.length;
  }
  return result;
}
