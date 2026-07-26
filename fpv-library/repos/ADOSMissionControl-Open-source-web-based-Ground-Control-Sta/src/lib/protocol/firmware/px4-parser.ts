/**
 * PX4 .px4 firmware file parser.
 *
 * PX4 firmware files are JSON with a base64-encoded, zlib-compressed
 * firmware image. Format: { "magic": "PX4FWv1", "board_id": N,
 * "image": "base64(zlib(binary))", "image_size": N, ... }
 *
 * @module protocol/firmware/px4-parser
 */

import pako from "pako";
import type { ParsedFirmware } from "./types";

/** Default flash base address for STM32 MCUs. */
const FLASH_BASE = 0x08000000;

/**
 * Parse a PX4 .px4 firmware file.
 *
 * @param text — Raw file content as string (JSON)
 * @returns Parsed firmware with a single block at 0x08000000
 */
export function parsePx4File(text: string): ParsedFirmware {
  let json: Record<string, unknown>;
  try {
    json = JSON.parse(text);
  } catch {
    throw new Error("Invalid PX4 file: not valid JSON");
  }

  if (json.magic !== "PX4FWv1") {
    throw new Error(
      `Invalid PX4 file: expected magic "PX4FWv1", got "${String(json.magic)}"`
    );
  }

  if (typeof json.image !== "string") {
    throw new Error("Invalid PX4 file: missing 'image' field");
  }

  // Base64 decode the compressed image
  let compressedBytes: Uint8Array;
  try {
    const binaryString = atob(json.image as string);
    compressedBytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      compressedBytes[i] = binaryString.charCodeAt(i);
    }
  } catch {
    throw new Error("Invalid PX4 file: corrupt base64 image data");
  }

  // Decompress zlib data
  let data: Uint8Array;
  try {
    data = pako.inflate(compressedBytes);
  } catch {
    throw new Error("Invalid PX4 file: zlib decompression failed");
  }

  // Verify decompressed size if image_size is present
  if (typeof json.image_size === "number" && data.length !== json.image_size) {
    throw new Error(
      `Invalid PX4 file: decompressed size ${data.length} does not match expected ${json.image_size}`
    );
  }

  const boardId = typeof json.board_id === "number" ? json.board_id : undefined;
  const description = typeof json.summary === "string"
    ? (json.summary as string)
    : typeof json.description === "string"
      ? (json.description as string)
      : undefined;

  return {
    blocks: [{ address: FLASH_BASE, data }],
    totalBytes: data.length,
    boardId,
    description,
  };
}
