/**
 * Flash operations for STM32 serial bootloader.
 *
 * Erase, write, read, and jump operations extracted from STM32SerialFlasher.
 * Each function takes a context object providing low-level serial helpers.
 *
 * @module protocol/firmware/stm32-serial-flash
 */

import type { FlashProgressCallback, ParsedFirmware, ChipInfo } from "./types";

// Bootloader commands
const CMD_READ_MEMORY = 0x11;
const CMD_GO = 0x21;
const CMD_WRITE_MEMORY = 0x31;
const CMD_ERASE = 0x43;
const CMD_EXTENDED_ERASE = 0x44;

const WRITE_BLOCK_SIZE = 256;
const READ_BLOCK_SIZE = 256;
const ERASE_TIMEOUT = 30000;

export { WRITE_BLOCK_SIZE, READ_BLOCK_SIZE };

export interface SerialFlashContext {
  sendBytes(data: Uint8Array): Promise<void>;
  sendCommand(cmd: number): Promise<void>;
  sendAddress(address: number): Promise<void>;
  waitForAck(timeoutMs?: number): Promise<void>;
  waitForBytes(count: number, timeoutMs?: number): Promise<number[]>;
  checkAbort(): void;
}

/** Erase flash pages covered by firmware blocks. */
export async function eraseFlash(
  ctx: SerialFlashContext,
  chipInfo: ChipInfo,
  supportsExtendedErase: boolean,
  blocks: ParsedFirmware["blocks"],
): Promise<void> {
  if (supportsExtendedErase || chipInfo.useExtendedErase) {
    await ctx.sendCommand(CMD_EXTENDED_ERASE);

    const pages = new Set<number>();
    for (const block of blocks) {
      const startPage = Math.floor((block.address - chipInfo.flashBase) / chipInfo.pageSize);
      const endPage = Math.floor((block.address + block.data.length - 1 - chipInfo.flashBase) / chipInfo.pageSize);
      for (let p = startPage; p <= endPage; p++) pages.add(p);
    }

    const pageList = Array.from(pages).sort((a, b) => a - b);
    const numPages = pageList.length;
    const data = new Uint8Array(2 + numPages * 2);
    data[0] = ((numPages - 1) >> 8) & 0xff;
    data[1] = (numPages - 1) & 0xff;
    for (let i = 0; i < numPages; i++) {
      data[2 + i * 2] = (pageList[i] >> 8) & 0xff;
      data[2 + i * 2 + 1] = pageList[i] & 0xff;
    }

    let checksum = 0;
    for (const b of data) checksum ^= b;
    const payload = new Uint8Array(data.length + 1);
    payload.set(data);
    payload[data.length] = checksum;

    await ctx.sendBytes(payload);
    await ctx.waitForAck(ERASE_TIMEOUT);
  } else {
    await ctx.sendCommand(CMD_ERASE);

    const pages = new Set<number>();
    for (const block of blocks) {
      const startPage = Math.floor((block.address - chipInfo.flashBase) / chipInfo.pageSize);
      const endPage = Math.floor((block.address + block.data.length - 1 - chipInfo.flashBase) / chipInfo.pageSize);
      for (let p = startPage; p <= endPage; p++) pages.add(p);
    }

    const pageList = Array.from(pages).sort((a, b) => a - b);
    const numPages = pageList.length;
    const data = new Uint8Array(1 + numPages);
    data[0] = numPages - 1;
    for (let i = 0; i < numPages; i++) data[1 + i] = pageList[i] & 0xff;

    let checksum = 0;
    for (const b of data) checksum ^= b;
    const payload = new Uint8Array(data.length + 1);
    payload.set(data);
    payload[data.length] = checksum;

    await ctx.sendBytes(payload);
    await ctx.waitForAck(ERASE_TIMEOUT);
  }
}

/** Write firmware blocks to flash. */
export async function writeFlash(
  ctx: SerialFlashContext,
  blocks: ParsedFirmware["blocks"],
  onProgress: FlashProgressCallback,
): Promise<void> {
  const totalBytes = blocks.reduce((sum, b) => sum + b.data.length, 0);
  let writtenBytes = 0;

  for (const block of blocks) {
    let offset = 0;
    while (offset < block.data.length) {
      ctx.checkAbort();
      const chunkSize = Math.min(WRITE_BLOCK_SIZE, block.data.length - offset);
      const address = block.address + offset;
      const chunk = block.data.slice(offset, offset + chunkSize);

      await writeMemory(ctx, address, chunk);

      writtenBytes += chunkSize;
      offset += chunkSize;
      const percent = 25 + Math.round((writtenBytes / totalBytes) * 50);
      onProgress({
        phase: "flashing", percent,
        message: `Writing... ${writtenBytes}/${totalBytes} bytes`,
        bytesWritten: writtenBytes, bytesTotal: totalBytes,
        phasePercent: Math.round((writtenBytes / totalBytes) * 100),
      });
    }
  }
}

/** WRITE_MEMORY command -- write up to 256 bytes at an address. */
async function writeMemory(ctx: SerialFlashContext, address: number, data: Uint8Array): Promise<void> {
  await ctx.sendCommand(CMD_WRITE_MEMORY);
  await ctx.sendAddress(address);

  const padded = new Uint8Array(data.length + (data.length % 2 === 0 ? 0 : 1));
  padded.set(data);

  const payload = new Uint8Array(1 + padded.length + 1);
  payload[0] = padded.length - 1;
  payload.set(padded, 1);

  let checksum = payload[0];
  for (let i = 0; i < padded.length; i++) checksum ^= padded[i];
  payload[payload.length - 1] = checksum;

  await ctx.sendBytes(payload);
  await ctx.waitForAck();
}

/** READ_MEMORY command -- read up to 256 bytes from an address. */
export async function readFlash(ctx: SerialFlashContext, address: number, length: number): Promise<Uint8Array> {
  await ctx.sendCommand(CMD_READ_MEMORY);
  await ctx.sendAddress(address);
  const n = length - 1;
  await ctx.sendBytes(new Uint8Array([n, ~n & 0xff]));
  await ctx.waitForAck();
  return new Uint8Array(await ctx.waitForBytes(length));
}

/** GO command -- jump to address and start executing. */
export async function jumpToApp(ctx: SerialFlashContext, address: number): Promise<void> {
  try {
    await ctx.sendCommand(CMD_GO);
    await ctx.sendAddress(address);
  } catch {
    // Expected -- device resets after GO command
  }
}
