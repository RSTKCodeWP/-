/**
 * DFU flash operations: erase, write, and verify.
 *
 * Extracted from STM32DfuFlasher for file size.
 *
 * @module protocol/firmware/stm32-dfu-flash
 */

import type { FlashProgressCallback, ParsedFirmware, DfuFlashLayout } from "./types";

export interface DfuFlashContext {
  transferSize: number;
  flashLayout: DfuFlashLayout | null;
  erasePage(address: number): Promise<void>;
  loadAddress(address: number): Promise<void>;
  writeBlock(blockNum: number, data: Uint8Array): Promise<void>;
  readBlock(blockNum: number, length: number): Promise<Uint8Array>;
  checkAbort(): void;
}

export async function dfuErasePages(ctx: DfuFlashContext, firmware: ParsedFirmware, onProgress: FlashProgressCallback): Promise<void> {
  if (!ctx.flashLayout) throw new Error("Flash layout not available");
  const sectorsToErase: number[] = [];
  for (const block of firmware.blocks) {
    const blockEnd = block.address + block.data.length;
    for (const sector of ctx.flashLayout.sectors) {
      for (let i = 0; i < sector.count; i++) {
        const sectorAddr = sector.address + i * sector.size;
        const sectorEnd = sectorAddr + sector.size;
        if (sectorAddr < blockEnd && sectorEnd > block.address) {
          if (!sectorsToErase.includes(sectorAddr)) sectorsToErase.push(sectorAddr);
        }
      }
    }
  }
  for (let i = 0; i < sectorsToErase.length; i++) {
    ctx.checkAbort();
    await ctx.erasePage(sectorsToErase[i]);
    onProgress({
      phase: "erasing", percent: 15 + Math.round(((i + 1) / sectorsToErase.length) * 10),
      message: `Erasing sector ${i + 1}/${sectorsToErase.length} at 0x${sectorsToErase[i].toString(16)}`,
      phasePercent: Math.round(((i + 1) / sectorsToErase.length) * 100),
    });
  }
}

export async function dfuWriteBlocks(ctx: DfuFlashContext, firmware: ParsedFirmware, onProgress: FlashProgressCallback): Promise<void> {
  const totalBytes = firmware.totalBytes;
  let writtenBytes = 0;
  for (const block of firmware.blocks) {
    await ctx.loadAddress(block.address);
    let offset = 0;
    let blockNum = 2;
    while (offset < block.data.length) {
      ctx.checkAbort();
      const chunkSize = Math.min(ctx.transferSize, block.data.length - offset);
      await ctx.writeBlock(blockNum, block.data.slice(offset, offset + chunkSize));
      writtenBytes += chunkSize;
      offset += chunkSize;
      blockNum++;
      onProgress({
        phase: "flashing", percent: 25 + Math.round((writtenBytes / totalBytes) * 50),
        message: `Writing... ${writtenBytes}/${totalBytes} bytes`,
        bytesWritten: writtenBytes, bytesTotal: totalBytes,
        phasePercent: Math.round((writtenBytes / totalBytes) * 100),
      });
    }
  }
}

export async function dfuVerifyBlocks(ctx: DfuFlashContext, firmware: ParsedFirmware, onProgress: FlashProgressCallback): Promise<void> {
  const totalBytes = firmware.totalBytes;
  let verifiedBytes = 0;
  for (const block of firmware.blocks) {
    await ctx.loadAddress(block.address);
    let offset = 0;
    let blockNum = 2;
    while (offset < block.data.length) {
      ctx.checkAbort();
      const chunkSize = Math.min(ctx.transferSize, block.data.length - offset);
      const readData = await ctx.readBlock(blockNum, chunkSize);
      for (let i = 0; i < chunkSize; i++) {
        if (readData[i] !== block.data[offset + i]) {
          throw new Error(`Verification failed at 0x${(block.address + offset + i).toString(16).toUpperCase()}`);
        }
      }
      verifiedBytes += chunkSize;
      offset += chunkSize;
      blockNum++;
      onProgress({
        phase: "verifying", percent: 75 + Math.round((verifiedBytes / totalBytes) * 20),
        message: `Verifying... ${verifiedBytes}/${totalBytes} bytes`,
        bytesWritten: verifiedBytes, bytesTotal: totalBytes,
        phasePercent: Math.round((verifiedBytes / totalBytes) * 100),
      });
    }
  }
}
