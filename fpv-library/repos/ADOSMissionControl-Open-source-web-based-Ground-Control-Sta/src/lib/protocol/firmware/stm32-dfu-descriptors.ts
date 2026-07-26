/**
 * DFuSe descriptor parsing and flash layout extraction for STM32 USB DFU.
 *
 * Helper functions extracted from STM32DfuFlasher for reading USB string
 * descriptors, configuration descriptors, and parsing DFuSe flash layout
 * from alternate setting interface names.
 *
 * @module protocol/firmware/stm32-dfu-descriptors
 */

import type { DfuFlashLayout, DfuSector } from "./types";

/** Read a USB string descriptor by index. Returns decoded string or null on failure. */
export async function readStringDescriptor(device: USBDevice, index: number): Promise<string | null> {
  if (index === 0) return null;
  try {
    const result = await device.controlTransferIn(
      { requestType: "standard", recipient: "device", request: 6, value: 0x0300 | index, index: 0 },
      255,
    );
    if (!result.data || result.data.byteLength < 4) return null;
    const length = result.data.getUint8(0);
    let str = "";
    for (let i = 2; i < length && i < result.data.byteLength; i += 2) {
      str += String.fromCharCode(result.data.getUint16(i, true));
    }
    return str || null;
  } catch {
    return null;
  }
}

/** Read raw USB configuration descriptor. Returns DataView or null on failure. */
export async function readConfigDescriptor(device: USBDevice): Promise<DataView | null> {
  try {
    // First read to get total length (wTotalLength at bytes 2-3)
    const header = await device.controlTransferIn(
      { requestType: "standard", recipient: "device", request: 6, value: 0x0200, index: 0 },
      4,
    );
    if (!header.data || header.data.byteLength < 4) return null;
    const totalLength = header.data.getUint16(2, true);

    // Read full descriptor
    const full = await device.controlTransferIn(
      { requestType: "standard", recipient: "device", request: 6, value: 0x0200, index: 0 },
      totalLength,
    );
    return full.data ?? null;
  } catch {
    return null;
  }
}

/**
 * Extract iInterface string index for each alternate setting from raw config descriptor.
 * Walks the descriptor chain looking for interface descriptors (type 4).
 */
export function getInterfaceStringIndices(configDesc: DataView, interfaceNumber: number): Map<number, number> {
  const indices = new Map<number, number>();
  let offset = 0;

  while (offset + 2 <= configDesc.byteLength) {
    const bLength = configDesc.getUint8(offset);
    const bDescriptorType = configDesc.getUint8(offset + 1);
    if (bLength === 0) break;

    // Interface descriptor: type 4, length >= 9
    if (bDescriptorType === 4 && bLength >= 9 && offset + 8 < configDesc.byteLength) {
      const bInterfaceNumber = configDesc.getUint8(offset + 2);
      const bAlternateSetting = configDesc.getUint8(offset + 3);
      const iInterface = configDesc.getUint8(offset + 8);
      if (bInterfaceNumber === interfaceNumber && iInterface > 0) {
        indices.set(bAlternateSetting, iInterface);
      }
    }

    offset += bLength;
  }

  return indices;
}

/**
 * Parse flash layout from USB alternate setting interface name.
 * Format: "@Internal Flash /0x08000000/04*016Kg,01*064Kg,07*128Kg"
 *
 * 3-layer fallback:
 * 1. Try alt.interfaceName (Chrome-cached string descriptor)
 * 2. Manually read string descriptors via USB control transfers
 * 3. Return null (caller falls back to mass erase)
 */
export async function getFlashLayout(
  device: USBDevice,
  interfaceNumber: number,
): Promise<DfuFlashLayout | null> {
  const iface = device.configuration?.interfaces.find(
    (i) => i.interfaceNumber === interfaceNumber
  );
  if (!iface) return null;

  // Collect candidate descriptor strings — try Chrome-cached names first
  const candidates: string[] = [];
  for (const alt of iface.alternates) {
    if (alt.interfaceName) candidates.push(alt.interfaceName);
  }

  // Fallback: manually read string descriptors if Chrome didn't populate them
  if (candidates.length === 0) {
    const configDesc = await readConfigDescriptor(device);
    if (configDesc) {
      const stringIndices = getInterfaceStringIndices(configDesc, interfaceNumber);
      for (const [, stringIndex] of stringIndices) {
        const str = await readStringDescriptor(device, stringIndex);
        if (str) candidates.push(str);
      }
    }
  }

  // Parse the first valid DFuSe descriptor string
  for (const rawName of candidates) {
    // Strip non-printable characters (F722, AT32 F437 garbage bytes)
    const name = rawName.replace(/[^\x20-\x7E]+/g, "");
    if (!name.includes("@")) continue;

    const match = name.match(/@(.+?)\/0x([0-9A-Fa-f]+)\/(.+)/);
    if (!match) continue;

    const memName = match[1].trim();
    const baseAddress = parseInt(match[2], 16);
    const sectorDesc = match[3];

    const sectors: DfuSector[] = [];
    let totalSize = 0;
    let currentAddress = baseAddress;

    // Parse sector descriptions like "04*016Kg,01*064Kg,07*128Kg"
    const parts = sectorDesc.split(",");
    for (const part of parts) {
      const sectorMatch = part.trim().match(/(\d+)\*(\d+)(.)(.)$/);
      if (!sectorMatch) continue;

      const count = parseInt(sectorMatch[1]);
      let size = parseInt(sectorMatch[2]);

      // Size multiplier
      const multiplier = sectorMatch[3];
      if (multiplier === "K" || multiplier === "k") size *= 1024;
      else if (multiplier === "M" || multiplier === "m") size *= 1024 * 1024;

      const properties = sectorMatch[4].toLowerCase();

      sectors.push({
        address: currentAddress,
        size,
        count,
        properties,
      });

      const regionSize = size * count;
      currentAddress += regionSize;
      totalSize += regionSize;
    }

    return { name: memName, baseAddress, sectors, totalSize };
  }

  return null;
}

/** Read wTransferSize from DFU Functional Descriptor (type 0x21). Falls back to given default. */
export async function getTransferSize(device: USBDevice, defaultSize: number): Promise<number> {
  const configDesc = await readConfigDescriptor(device);
  if (configDesc) {
    let offset = 0;
    while (offset + 2 <= configDesc.byteLength) {
      const bLength = configDesc.getUint8(offset);
      const bDescriptorType = configDesc.getUint8(offset + 1);
      if (bLength === 0) break;

      // DFU Functional Descriptor: 9 bytes, type 0x21
      if (bDescriptorType === 0x21 && bLength >= 7 && offset + 6 < configDesc.byteLength) {
        return configDesc.getUint16(offset + 5, true); // wTransferSize at bytes 5-6
      }
      offset += bLength;
    }
  }
  return defaultSize;
}
