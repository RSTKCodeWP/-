/**
 * ArduPilot APJ firmware file parser.
 *
 * APJ files are JSON with a base64-encoded firmware image.
 * Format: { "board_id": N, "image": "base64...", ... }
 *
 * @module protocol/firmware/apj-parser
 */

import type { ParsedFirmware } from "./types";

/** Default flash base address for STM32 MCUs. */
const FLASH_BASE = 0x08000000;

/**
 * Parse an ArduPilot .apj firmware file.
 *
 * @param content — Raw file content as string (JSON)
 * @returns Parsed firmware with a single block at 0x08000000
 */
export function parseApjFile(content: string): ParsedFirmware {
  let json: Record<string, unknown>;
  try {
    json = JSON.parse(content);
  } catch {
    throw new Error("Invalid APJ file: not valid JSON");
  }

  if (typeof json.image !== "string") {
    throw new Error("Invalid APJ file: missing 'image' field");
  }

  // Decode base64 image to binary
  let binaryString: string;
  try {
    binaryString = atob(json.image as string);
  } catch {
    throw new Error("Invalid APJ file: corrupt firmware image data");
  }
  const data = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    data[i] = binaryString.charCodeAt(i);
  }

  const boardId = typeof json.board_id === "number" ? json.board_id : undefined;
  const boardRevision = typeof json.board_revision === "number" ? json.board_revision : undefined;
  const description = typeof json.summary === "string" ? json.summary : undefined;

  return {
    blocks: [{ address: FLASH_BASE, data }],
    totalBytes: data.length,
    boardId,
    boardRevision,
    description,
  };
}
