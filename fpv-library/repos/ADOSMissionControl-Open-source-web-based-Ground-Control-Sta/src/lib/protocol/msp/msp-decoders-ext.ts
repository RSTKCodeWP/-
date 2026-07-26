/**
 * Extended MSP response payload decoders.
 *
 * Decoders for motor telemetry, dataflash reads, debug values,
 * GPS satellite info, UID, VTX table entries, and MCU info.
 *
 * Pure functions — each takes a DataView of the MSP response payload
 * (NOT the full MSP frame) and returns a typed object.
 *
 * All multi-byte values are little-endian.
 *
 * @module protocol/msp/msp-decoders-ext
 */

// ── DataView helpers ─────────────────────────────────────────

function readU8(dv: DataView, offset: number): number {
  return dv.getUint8(offset);
}

function readU16(dv: DataView, offset: number): number {
  return dv.getUint16(offset, true);
}

function readS16(dv: DataView, offset: number): number {
  return dv.getInt16(offset, true);
}

function readU32(dv: DataView, offset: number): number {
  return dv.getUint32(offset, true);
}

function readString(dv: DataView, offset: number, length: number): string {
  let s = '';
  for (let i = 0; i < length; i++) {
    s += String.fromCharCode(dv.getUint8(offset + i));
  }
  return s;
}

// ── Decoded result types ─────────────────────────────────────

export interface MspMotorTelemetry {
  motorCount: number;
  rpm: number[];
  invalidPercent: number[];
  temperature: number[];
  voltage: number[];
  current: number[];
  consumption: number[];
}

export interface MspDataflashRead {
  readAddress: number;
  data: Uint8Array;
  isCompressed: boolean;
  compressedSize: number;
}

export interface MspDebug {
  values: number[];
}

export interface MspGpsSvInfo {
  channel: number;
  svId: number;
  quality: number;
  cno: number;
}

export interface MspUid {
  uid: number[];
}

export interface MspVtxTableBand {
  bandNumber: number;
  bandName: string;
  bandLetter: string;
  isFactoryBand: boolean;
  frequencies: number[];
}

export interface MspVtxTablePowerLevel {
  powerNumber: number;
  powerValue: number;
  powerLabel: string;
}

export interface MspMcuInfo {
  clockFrequencyHz: number;
}

// ── Decoder functions ────────────────────────────────────────

/**
 * MSP_MOTOR_TELEMETRY (139)
 *
 * U8 motorCount, then per motor:
 *   U32 rpm
 *   U16 invalidPercent
 *   U8  temperature (°C)
 *   U16 voltage (÷100 = V)
 *   U16 current (÷100 = A)
 *   U16 consumption (mAh)
 */
export function decodeMspMotorTelemetry(dv: DataView): MspMotorTelemetry {
  const motorCount = readU8(dv, 0);
  const rpm: number[] = [];
  const invalidPercent: number[] = [];
  const temperature: number[] = [];
  const voltage: number[] = [];
  const current: number[] = [];
  const consumption: number[] = [];

  // 13 bytes per motor: U32 + U16 + U8 + U16 + U16 + U16
  const bytesPerMotor = 13;
  for (let i = 0; i < motorCount; i++) {
    const off = 1 + i * bytesPerMotor;
    if (off + bytesPerMotor > dv.byteLength) break;
    rpm.push(readU32(dv, off));
    invalidPercent.push(readU16(dv, off + 4));
    temperature.push(readU8(dv, off + 6));
    voltage.push(readU16(dv, off + 7) / 100);
    current.push(readU16(dv, off + 9) / 100);
    consumption.push(readU16(dv, off + 11));
  }

  return { motorCount, rpm, invalidPercent, temperature, voltage, current, consumption };
}

/**
 * MSP_DATAFLASH_READ (71) response
 *
 * U32 readAddress, then:
 *   If compressed (newer firmware with MSPv2):
 *     U16 compressedSize
 *     U16 decompressedSize (unused here, caller handles decompression)
 *     compressed data bytes
 *   If not compressed:
 *     raw data bytes after address
 *
 * Compression is detected by checking if the payload is longer than
 * 4 + remaining data (the extra 4 bytes are the two U16 size fields).
 * In practice, we detect compression by checking if the total payload
 * length is greater than readAddress(4) + rawData, which means the
 * firmware prepended size fields.
 *
 * Betaflight configurator detects compression via MSPv2 flag byte.
 * For simplicity, we check if the payload has the extra size header.
 */
export function decodeMspDataflashRead(dv: DataView): MspDataflashRead {
  const readAddress = readU32(dv, 0);

  // Check for compression header: total length suggests extra 4 bytes of size info
  // The MSPv2 flag byte (bit 0) indicates compression in BF configurator.
  // We detect by checking if the remaining bytes make sense as compressed data.
  // Simple approach: payload after address is the data (uncompressed path).
  // The caller can check isCompressed and handle accordingly.
  const dataStart = 4;
  const remainingBytes = dv.byteLength - dataStart;

  // If remaining >= 4 bytes, check if it could be compressed format
  // Compressed format: U16 compressedSize + U16 decompressedSize + data
  if (remainingBytes >= 4) {
    const possibleCompressedSize = readU16(dv, 4);
    const possibleDecompressedSize = readU16(dv, 6);

    // If compressedSize + 4 (headers) matches remaining, it's compressed
    if (
      possibleCompressedSize > 0 &&
      possibleDecompressedSize > 0 &&
      possibleCompressedSize + 4 === remainingBytes &&
      possibleDecompressedSize > possibleCompressedSize
    ) {
      const data = new Uint8Array(dv.buffer, dv.byteOffset + 8, possibleCompressedSize);
      return {
        readAddress,
        data,
        isCompressed: true,
        compressedSize: possibleCompressedSize,
      };
    }
  }

  // Uncompressed: raw data after address
  const data = new Uint8Array(dv.buffer, dv.byteOffset + dataStart, remainingBytes);
  return {
    readAddress,
    data,
    isCompressed: false,
    compressedSize: 0,
  };
}

/**
 * MSP_DEBUG (254)
 * 4x S16 debug values
 */
export function decodeMspDebug(dv: DataView): MspDebug {
  const count = Math.min(4, Math.floor(dv.byteLength / 2));
  const values: number[] = [];
  for (let i = 0; i < count; i++) {
    values.push(readS16(dv, i * 2));
  }
  return { values };
}

/**
 * MSP_GPS_SV_INFO (164)
 * U8 numChannels, then per channel: U8 channel, U8 svId, U8 quality, U8 cno
 */
export function decodeMspGpsSvInfo(dv: DataView): MspGpsSvInfo[] {
  if (dv.byteLength < 1) return [];

  const numChannels = readU8(dv, 0);
  const result: MspGpsSvInfo[] = [];
  const bytesPerChannel = 4;

  for (let i = 0; i < numChannels; i++) {
    const off = 1 + i * bytesPerChannel;
    if (off + bytesPerChannel > dv.byteLength) break;
    result.push({
      channel: readU8(dv, off),
      svId: readU8(dv, off + 1),
      quality: readU8(dv, off + 2),
      cno: readU8(dv, off + 3),
    });
  }

  return result;
}

/**
 * MSP_UID (160)
 * 3x U32 unique chip ID
 */
export function decodeMspUid(dv: DataView): MspUid {
  const uid: number[] = [];
  const count = Math.min(3, Math.floor(dv.byteLength / 4));
  for (let i = 0; i < count; i++) {
    uid.push(readU32(dv, i * 4));
  }
  return { uid };
}

/**
 * MSP_VTXTABLE_BAND (137)
 *
 * U8 bandNumber
 * U8 bandNameLength
 * ASCII bandName (bandNameLength bytes)
 * U8 bandLetter (single ASCII char)
 * U8 isFactoryBand (bool)
 * U8 channelCount
 * U16[] frequencies (channelCount entries)
 */
export function decodeMspVtxTableBand(dv: DataView): MspVtxTableBand {
  let offset = 0;

  const bandNumber = readU8(dv, offset);
  offset += 1;

  const bandNameLength = readU8(dv, offset);
  offset += 1;

  const bandName = readString(dv, offset, bandNameLength);
  offset += bandNameLength;

  const bandLetter = String.fromCharCode(readU8(dv, offset));
  offset += 1;

  const isFactoryBand = readU8(dv, offset) !== 0;
  offset += 1;

  const channelCount = readU8(dv, offset);
  offset += 1;

  const frequencies: number[] = [];
  for (let i = 0; i < channelCount; i++) {
    if (offset + 2 > dv.byteLength) break;
    frequencies.push(readU16(dv, offset));
    offset += 2;
  }

  return { bandNumber, bandName, bandLetter, isFactoryBand, frequencies };
}

/**
 * MSP_VTXTABLE_POWERLEVEL (138)
 *
 * U8  powerNumber
 * U16 powerValue
 * U8  labelLength
 * ASCII label (labelLength bytes)
 */
export function decodeMspVtxTablePowerLevel(dv: DataView): MspVtxTablePowerLevel {
  const powerNumber = readU8(dv, 0);
  const powerValue = readU16(dv, 1);
  const labelLength = readU8(dv, 3);
  const powerLabel = readString(dv, 4, labelLength);

  return { powerNumber, powerValue, powerLabel };
}

/**
 * MSP2_MCU_INFO (0x300C)
 * U32 clockFrequencyHz
 */
export function decodeMspMcuInfo(dv: DataView): MspMcuInfo {
  return {
    clockFrequencyHz: readU32(dv, 0),
  };
}
