/**
 * @module signatures
 * @description Precomputed 64-bit DSDL signatures and data type IDs for the
 * eight standard DroneCAN messages the GCS speaks. The signatures are used by
 * the transfer coder when computing the multi-frame CRC.
 * @license GPL-3.0-only
 */

/**
 * 64-bit DSDL signatures keyed by short name. Each value is the canonical
 * DSDL signature for the matching `uavcan.protocol.*` type.
 */
export const DSDL_SIGNATURES = {
  NodeStatus: BigInt("0x0F0868D0C1A7C6F1"),
  GetNodeInfo: BigInt("0xEE468A8121C46A9E"),
  paramGetSet: BigInt("0xA7B622F939D1A4D5"),
  paramExecuteOpcode: BigInt("0x3B131AC5EB69D2CD"),
  RestartNode: BigInt("0x569E05394A3017F0"),
  fileBeginFirmwareUpdate: BigInt("0xB7D725DF72724126"),
  fileRead: BigInt("0x8DCDCA939F33F678"),
  GetTransportStats: BigInt("0xBE6F76A7EC312B04"),
  EscRawCommand: BigInt("0x217F5C87D7EC951D"),
  GnssFix2: BigInt("0xCA41E7000F37435F"),
  MagneticFieldStrength2: BigInt("0xB6AC0C442430297E"),
} as const;

/**
 * Data type IDs for the eight standard DroneCAN messages the GCS speaks.
 * Message broadcasts use a 16-bit type ID; services use an 8-bit type ID.
 */
export const DATA_TYPE_IDS = {
  /** Message broadcast `uavcan.protocol.NodeStatus` (16-bit). */
  NodeStatus: 341,
  /** Service `uavcan.protocol.GetNodeInfo` (8-bit). */
  GetNodeInfo: 1,
  /** Service `uavcan.protocol.param.GetSet` (8-bit). */
  paramGetSet: 11,
  /** Service `uavcan.protocol.param.ExecuteOpcode` (8-bit). */
  paramExecuteOpcode: 10,
  /** Service `uavcan.protocol.RestartNode` (8-bit). */
  RestartNode: 5,
  /** Service `uavcan.protocol.file.BeginFirmwareUpdate` (8-bit). */
  fileBeginFirmwareUpdate: 40,
  /** Service `uavcan.protocol.file.Read` (8-bit). */
  fileRead: 48,
  /** Service `uavcan.protocol.GetTransportStats` (8-bit). */
  GetTransportStats: 4,
  /** Message broadcast `uavcan.equipment.esc.RawCommand` (16-bit). */
  EscRawCommand: 1030,
  /** Message broadcast `uavcan.equipment.gnss.Fix2` (16-bit). */
  GnssFix2: 1063,
  /** Message broadcast `uavcan.equipment.ahrs.MagneticFieldStrength2` (16-bit). */
  MagneticFieldStrength2: 1002,
} as const;

export type DsdlSignatureName = keyof typeof DSDL_SIGNATURES;
