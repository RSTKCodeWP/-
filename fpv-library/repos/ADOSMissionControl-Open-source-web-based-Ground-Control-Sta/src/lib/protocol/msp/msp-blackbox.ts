/**
 * Blackbox log download protocol for MSP flight controllers.
 *
 * Downloads blackbox data from onboard flash via MSP_DATAFLASH_READ (71),
 * erases flash via MSP_DATAFLASH_ERASE (72), and reads flash summary
 * via MSP_DATAFLASH_SUMMARY (70).
 *
 * @module protocol/msp/msp-blackbox
 */

import { MSP } from './msp-constants';
import type { MspSerialQueue } from './msp-serial-queue';
import { decodeMspDataflashRead } from './msp-decoders-ext';
import { decodeMspDataflashSummary } from './msp-decoders';

// ── Types ──────────────────────────────────────────────────

export interface BlackboxDownloadProgress {
  bytesRead: number;
  totalBytes: number;
  percentComplete: number;
}

export type ProgressCallback = (progress: BlackboxDownloadProgress) => void;

export interface FlashSummary {
  ready: boolean;
  sectors: number;
  totalSize: number;
  usedSize: number;
}

// ── Constants ──────────────────────────────────────────────

/** 4KB per read request. */
const CHUNK_SIZE = 4096;

/** Maximum time to wait for flash erase (seconds). */
const ERASE_TIMEOUT_SECONDS = 60;

// ── Public API ─────────────────────────────────────────────

/**
 * Get flash summary (total size, used size, ready state).
 * Sends MSP_DATAFLASH_SUMMARY (70).
 */
export async function getFlashSummary(queue: MspSerialQueue): Promise<FlashSummary> {
  const frame = await queue.send(MSP.MSP_DATAFLASH_SUMMARY);
  const dv = new DataView(frame.payload.buffer, frame.payload.byteOffset, frame.payload.byteLength);
  const summary = decodeMspDataflashSummary(dv);
  return {
    ready: summary.ready,
    sectors: summary.sectors,
    totalSize: summary.totalSize,
    usedSize: summary.usedSize,
  };
}

/**
 * Download blackbox log data from onboard flash.
 *
 * Reads data in 4KB chunks via MSP_DATAFLASH_READ (71).
 * Returns the complete log as a Uint8Array.
 *
 * @param queue - MSP serial queue for sending commands
 * @param startAddress - Flash address to start reading from
 * @param totalSize - Total bytes to read
 * @param onProgress - Optional progress callback
 * @returns Complete log data
 */
export async function downloadBlackboxLog(
  queue: MspSerialQueue,
  startAddress: number,
  totalSize: number,
  onProgress?: ProgressCallback,
): Promise<Uint8Array> {
  const result = new Uint8Array(totalSize);
  let bytesRead = 0;
  let address = startAddress;

  while (bytesRead < totalSize) {
    const requestSize = Math.min(CHUNK_SIZE, totalSize - bytesRead);

    // Build MSP_DATAFLASH_READ request: U32 address + U16 requestSize
    const payload = new Uint8Array(6);
    const reqDv = new DataView(payload.buffer);
    reqDv.setUint32(0, address, true);
    reqDv.setUint16(4, requestSize, true);

    const frame = await queue.send(MSP.MSP_DATAFLASH_READ, payload);

    // Decode response
    const respDv = new DataView(
      frame.payload.buffer,
      frame.payload.byteOffset,
      frame.payload.byteLength,
    );
    const response = decodeMspDataflashRead(respDv);

    // If we got no data, the flash might be done or broken
    if (response.data.length === 0) break;

    // Copy data to result buffer
    const copyLen = Math.min(response.data.length, totalSize - bytesRead);
    result.set(response.data.subarray(0, copyLen), bytesRead);

    bytesRead += copyLen;
    address += copyLen;

    onProgress?.({
      bytesRead,
      totalBytes: totalSize,
      percentComplete: Math.round((bytesRead / totalSize) * 100),
    });

    // Small delay to not overwhelm the FC
    if (bytesRead < totalSize) {
      await new Promise<void>((r) => setTimeout(r, 10));
    }
  }

  return result.subarray(0, bytesRead);
}

/**
 * Erase all blackbox data from flash.
 * Sends MSP_DATAFLASH_ERASE (72) and polls until complete.
 *
 * @param queue - MSP serial queue for sending commands
 * @returns true if erase completed, false if timed out
 */
export async function eraseBlackboxFlash(queue: MspSerialQueue): Promise<boolean> {
  // Send erase command
  await queue.send(MSP.MSP_DATAFLASH_ERASE);

  // Poll until erase is complete (flash ready state + usedSize = 0)
  for (let i = 0; i < ERASE_TIMEOUT_SECONDS; i++) {
    await new Promise<void>((r) => setTimeout(r, 1000));

    try {
      const summary = await getFlashSummary(queue);
      if (summary.ready && summary.usedSize === 0) {
        return true;
      }
    } catch {
      // FC may be busy erasing and not respond to queries; keep polling
    }
  }

  return false;
}
