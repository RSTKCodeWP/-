/**
 * MSP OSD config decoder.
 *
 * @module protocol/msp/decoders/config/osd
 */

import { readU8, readU16 } from '../../msp-decode-utils';

export interface MspOsdConfig {
  flags: number;
  videoSystem: number;
  units: number;
  rssiAlarm: number;
  capacityWarning: number;
  items: Array<{ position: number }>;
}

/**
 * MSP_OSD_CONFIG (84)
 *
 * The OSD config format is complex and version-dependent. Core fields that
 * are stable across API versions are extracted; remaining bytes are decoded
 * as U16 element positions.
 */
export function decodeMspOsdConfig(dv: DataView): MspOsdConfig {
  if (dv.byteLength === 0) {
    return { flags: 0, videoSystem: 0, units: 0, rssiAlarm: 0, capacityWarning: 0, items: [] };
  }

  const flags = readU8(dv, 0);
  const videoSystem = readU8(dv, 1);
  const units = readU8(dv, 2);
  const rssiAlarm = readU8(dv, 3);
  const capacityWarning = readU16(dv, 4);

  // Remaining bytes are U16 item positions
  const itemOffset = 6;
  const items: Array<{ position: number }> = [];
  for (let i = itemOffset; i + 1 < dv.byteLength; i += 2) {
    items.push({ position: readU16(dv, i) });
  }

  return { flags, videoSystem, units, rssiAlarm, capacityWarning, items };
}
