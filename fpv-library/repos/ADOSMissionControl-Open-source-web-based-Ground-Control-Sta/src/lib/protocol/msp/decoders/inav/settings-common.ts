/**
 * MSP2_COMMON_* setting decoders: opaque value bytes, setting info
 * metadata, and the parameter-group list.
 *
 * @module protocol/msp/decoders/inav/settings-common
 */

import { readU8, readU16, readS16, readS32, readU32, readFloat32, readCString } from "./helpers";
import type { INavCommonSetting, INavSettingInfo, INavPgList } from "./types";

/** MODE_LOOKUP flag in the setting mode byte (firmware setting_mode_e bit 6). */
const MODE_LOOKUP = 1 << 6; // 0x40
/** Defensive cap so a non-lookup setting wrongly flagged can't loop forever. */
const MAX_ENUM_LABELS = 512;

/** Decode the trailing current value by setting type, or undefined if absent. */
function decodeValueAt(dv: DataView, off: number, type: number): number | undefined {
  switch (type) {
    case 0: return off < dv.byteLength ? readU8(dv, off) : undefined;            // UINT8
    case 1: return off < dv.byteLength ? dv.getInt8(off) : undefined;            // INT8
    case 2: return off + 1 < dv.byteLength ? readU16(dv, off) : undefined;       // UINT16
    case 3: return off + 1 < dv.byteLength ? readS16(dv, off) : undefined;       // INT16
    case 4: return off + 3 < dv.byteLength ? readU32(dv, off) : undefined;       // UINT32
    case 5: return off + 3 < dv.byteLength ? readFloat32(dv, off) : undefined;   // FLOAT
    default: return undefined;                                                   // STRING / unknown
  }
}

// ── MSP2 COMMON SETTING decoders ─────────────────────────────

/**
 * MSP2_COMMON_SETTING (0x1003) response.
 *
 * Raw bytes. Caller interprets based on the setting type from SETTING_INFO.
 */
export function decodeCommonSetting(dv: DataView): INavCommonSetting {
  return { raw: new Uint8Array(dv.buffer, dv.byteOffset, dv.byteLength) };
}

/**
 * MSP2_COMMON_SETTING_INFO (0x1007) response — firmware byte layout
 * (iNav `fc/fc_msp.c` mspSettingInfoCommand; matches the reference configurator):
 *
 *   cstring name            (null-terminated)
 *   U16     pgId
 *   U8      type             (setting_type_e 0..6)
 *   U8      section          (bits 3-5 of the packed firmware type)
 *   U8      mode             (bit 6 = MODE_LOOKUP)
 *   S32     min              (signed)
 *   U32     max              (unsigned)
 *   U16     index            (absolute setting index)
 *   U8      profileCurrent
 *   U8      profileCount
 *   if MODE_LOOKUP: cstring  label × (max - min + 1)   (enum value labels)
 *   value                    (current value, decoded by type)
 */
export function decodeCommonSettingInfo(dv: DataView): INavSettingInfo {
  // readCString returns [string, bytesConsumed] — advance off by the consumed
  // count, never assign it (that would discard the accumulated offset).
  const [name, nameLen] = readCString(dv, 0);
  let off = nameLen;
  const pgId = readU16(dv, off); off += 2;
  const type = readU8(dv, off); off += 1;
  const section = readU8(dv, off); off += 1;
  const mode = readU8(dv, off); off += 1;
  const min = readS32(dv, off); off += 4;
  const max = readU32(dv, off); off += 4;
  const index = readU16(dv, off); off += 2;
  const profileCurrent = readU8(dv, off); off += 1;
  const profileCount = readU8(dv, off); off += 1;

  let enumValues: string[] | undefined;
  if ((mode & MODE_LOOKUP) !== 0 && max >= min && max - min < MAX_ENUM_LABELS) {
    enumValues = [];
    for (let i = min; i <= max && off < dv.byteLength; i++) {
      const [label, consumed] = readCString(dv, off);
      enumValues.push(label);
      off += consumed;
    }
  }

  const value = decodeValueAt(dv, off, type);
  return { name, pgId, type, section, mode, min, max, index, profileCurrent, profileCount, enumValues, value };
}

/**
 * MSP2_COMMON_PG_LIST (0x1008) response.
 *
 * Repeated U16 pgId values.
 */
export function decodeCommonPgList(dv: DataView): INavPgList {
  const pgIds: number[] = [];
  let offset = 0;
  while (offset + 1 < dv.byteLength) {
    pgIds.push(readU16(dv, offset));
    offset += 2;
  }
  return { pgIds };
}
