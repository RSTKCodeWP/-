/**
 * STM32 chip signature table for serial bootloader identification.
 *
 * Maps chip signature IDs (from GET_ID command) to chip information
 * including flash size, page size, and erase mode.
 *
 * @module protocol/firmware/stm32-chip-table
 */

import type { ChipInfo } from "./types";

/** Chip signature to chip info lookup table. */
export const CHIP_TABLE: Record<number, Omit<ChipInfo, "signature">> = {
  0x410: { name: "STM32F103 Medium-density", flashSize: 128 * 1024, pageSize: 1024, flashBase: 0x08000000, useExtendedErase: false },
  0x411: { name: "STM32F2xx", flashSize: 1024 * 1024, pageSize: 16384, flashBase: 0x08000000, useExtendedErase: true },
  0x412: { name: "STM32F103 Low-density", flashSize: 32 * 1024, pageSize: 1024, flashBase: 0x08000000, useExtendedErase: false },
  0x413: { name: "STM32F405/F407", flashSize: 1024 * 1024, pageSize: 16384, flashBase: 0x08000000, useExtendedErase: true },
  0x414: { name: "STM32F103 High-density", flashSize: 512 * 1024, pageSize: 2048, flashBase: 0x08000000, useExtendedErase: false },
  0x419: { name: "STM32F427/F429", flashSize: 2048 * 1024, pageSize: 16384, flashBase: 0x08000000, useExtendedErase: true },
  0x421: { name: "STM32F446", flashSize: 512 * 1024, pageSize: 16384, flashBase: 0x08000000, useExtendedErase: true },
  0x431: { name: "STM32F411", flashSize: 512 * 1024, pageSize: 16384, flashBase: 0x08000000, useExtendedErase: true },
  0x433: { name: "STM32F401 (B/C)", flashSize: 256 * 1024, pageSize: 16384, flashBase: 0x08000000, useExtendedErase: true },
  0x435: { name: "STM32L4xx", flashSize: 1024 * 1024, pageSize: 2048, flashBase: 0x08000000, useExtendedErase: true },
  0x449: { name: "STM32F74x", flashSize: 1024 * 1024, pageSize: 32768, flashBase: 0x08000000, useExtendedErase: true },
  0x450: { name: "STM32H743/H753", flashSize: 2048 * 1024, pageSize: 131072, flashBase: 0x08000000, useExtendedErase: true },
  0x451: { name: "STM32F76x/F77x", flashSize: 2048 * 1024, pageSize: 32768, flashBase: 0x08000000, useExtendedErase: true },
  0x452: { name: "STM32F72x/F73x", flashSize: 512 * 1024, pageSize: 16384, flashBase: 0x08000000, useExtendedErase: true },
  0x480: { name: "STM32H7A3/H7B3", flashSize: 2048 * 1024, pageSize: 8192, flashBase: 0x08000000, useExtendedErase: true },
  0x483: { name: "STM32H723/H725/H730/H733/H735", flashSize: 1024 * 1024, pageSize: 131072, flashBase: 0x08000000, useExtendedErase: true },
};
