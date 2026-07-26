/**
 * Intel HEX firmware file parser.
 *
 * Handles record types 00 (data), 01 (EOF), 02 (extended segment),
 * 04 (extended linear address), 05 (start linear address).
 * Groups sequential addresses into contiguous FirmwareBlock entries.
 *
 * @module protocol/firmware/hex-parser
 */

import type { ParsedFirmware, FirmwareBlock } from "./types";

/**
 * Parse an Intel HEX file into firmware blocks.
 *
 * @param content — Raw .hex file content
 * @returns Parsed firmware with one or more contiguous blocks
 */
export function parseHexFile(content: string): ParsedFirmware {
  const lines = content.split(/\r?\n/).filter((l) => l.startsWith(":"));
  if (lines.length === 0) {
    throw new Error("Invalid HEX file: no records found");
  }

  let extendedAddress = 0;
  const dataEntries: { address: number; data: Uint8Array }[] = [];
  let totalBytes = 0;

  for (const line of lines) {
    const bytes = hexLineToBytes(line);
    validateChecksum(bytes);

    const byteCount = bytes[0];
    const offset = (bytes[1] << 8) | bytes[2];
    const recordType = bytes[3];
    const data = bytes.slice(4, 4 + byteCount);

    switch (recordType) {
      case 0x00: // Data record
        dataEntries.push({
          address: extendedAddress + offset,
          data: new Uint8Array(data),
        });
        totalBytes += byteCount;
        break;

      case 0x01: // EOF
        break;

      case 0x02: // Extended segment address
        extendedAddress = ((data[0] << 8) | data[1]) << 4;
        break;

      case 0x04: // Extended linear address
        extendedAddress = ((data[0] << 8) | data[1]) << 16;
        break;

      case 0x05: // Start linear address (entry point, ignored for flashing)
        break;

      default:
        // Unknown record types are silently ignored
        break;
    }
  }

  if (dataEntries.length === 0) {
    throw new Error("Invalid HEX file: no data records found");
  }

  // Sort by address and merge contiguous entries into blocks
  dataEntries.sort((a, b) => a.address - b.address);
  const blocks: FirmwareBlock[] = [];
  let currentBlock: { address: number; chunks: Uint8Array[] } | null = null;
  let currentEnd = 0;

  for (const entry of dataEntries) {
    if (currentBlock && entry.address === currentEnd) {
      // Contiguous — append to current block
      currentBlock.chunks.push(entry.data);
      currentEnd += entry.data.length;
    } else {
      // Gap — finalize previous block, start new one
      if (currentBlock) {
        blocks.push(finalizeBlock(currentBlock));
      }
      currentBlock = { address: entry.address, chunks: [entry.data] };
      currentEnd = entry.address + entry.data.length;
    }
  }
  if (currentBlock) {
    blocks.push(finalizeBlock(currentBlock));
  }

  return { blocks, totalBytes };
}

/** Convert a hex record line (":AABBCC...") to a byte array. */
function hexLineToBytes(line: string): number[] {
  const hex = line.slice(1); // Remove leading ':'
  const bytes: number[] = [];
  for (let i = 0; i < hex.length; i += 2) {
    bytes.push(parseInt(hex.substring(i, i + 2), 16));
  }
  return bytes;
}

/** Validate the checksum of a parsed hex record. */
function validateChecksum(bytes: number[]): void {
  let sum = 0;
  for (const b of bytes) {
    sum = (sum + b) & 0xff;
  }
  if (sum !== 0) {
    throw new Error("Invalid HEX file: checksum mismatch");
  }
}

/** Merge a block's chunks into a single contiguous Uint8Array. */
function finalizeBlock(block: { address: number; chunks: Uint8Array[] }): FirmwareBlock {
  const totalLength = block.chunks.reduce((sum, c) => sum + c.length, 0);
  const data = new Uint8Array(totalLength);
  let offset = 0;
  for (const chunk of block.chunks) {
    data.set(chunk, offset);
    offset += chunk.length;
  }
  return { address: block.address, data };
}
