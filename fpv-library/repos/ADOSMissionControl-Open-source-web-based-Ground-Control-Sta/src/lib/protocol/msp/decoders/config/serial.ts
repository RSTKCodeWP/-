/**
 * MSP serial port config decoder.
 *
 * @module protocol/msp/decoders/config/serial
 */

import { readU8, readU16, readU32 } from '../../msp-decode-utils';

export interface MspSerialPort {
  identifier: number;
  functions: number;
  mspBaudRate: number;
  gpsBaudRate: number;
  telemetryBaudRate: number;
  blackboxBaudRate: number;
}

export interface MspSerialConfig {
  ports: MspSerialPort[];
}

/**
 * MSP_CF_SERIAL_CONFIG (54)
 *
 * 7 bytes per port: U8 identifier, U16 functions, U8 msp, U8 gps, U8 telem, U8 blackbox.
 * Baud rate fields are indices into the BAUD_RATES array. Raw indices are
 * returned and the consumer maps them to actual baud values.
 */
export function decodeMspSerialConfig(dv: DataView): MspSerialConfig {
  const bytesPerPort = 7; // U8 + U16 + 4*U8
  const portCount = dv.byteLength / bytesPerPort;
  const ports: MspSerialPort[] = [];
  for (let i = 0; i < portCount; i++) {
    const off = i * bytesPerPort;
    ports.push({
      identifier: readU8(dv, off),
      functions: readU16(dv, off + 1),
      mspBaudRate: readU8(dv, off + 3),
      gpsBaudRate: readU8(dv, off + 4),
      telemetryBaudRate: readU8(dv, off + 5),
      blackboxBaudRate: readU8(dv, off + 6),
    });
  }
  return { ports };
}

/**
 * MSP2_COMMON_SERIAL_CONFIG (0x1009)
 *
 * U8 count, then per port (>= 10 bytes): U8 identifier, U32 functionMask,
 * U8 msp, U8 gps, U8 telem, U8 blackbox. A per-port stride >10 (from newer
 * firmware appending fields) is tolerated by deriving it from count.
 */
export function decodeMspSerialConfig2(dv: DataView): MspSerialConfig {
  const count = dv.byteLength >= 1 ? readU8(dv, 0) : 0;
  const ports: MspSerialPort[] = [];
  if (count <= 0) return { ports };
  const stride = Math.floor((dv.byteLength - 1) / count);
  for (let i = 0; i < count; i++) {
    const off = 1 + i * stride;
    ports.push({
      identifier: readU8(dv, off),
      functions: readU32(dv, off + 1),
      mspBaudRate: readU8(dv, off + 5),
      gpsBaudRate: readU8(dv, off + 6),
      telemetryBaudRate: readU8(dv, off + 7),
      blackboxBaudRate: readU8(dv, off + 8),
    });
  }
  return { ports };
}
