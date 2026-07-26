/**
 * Protocol detector for Altnautica Command GCS.
 *
 * Probes a transport to detect the protocol (MAVLink or MSP) and
 * firmware type by sending probe messages and analyzing responses.
 *
 * @module protocol/detector
 */

// When result.protocol === 'msp', callers should create MSPAdapter
// import { MSPAdapter } from './msp-adapter'
import type { FirmwareType } from './types'

// ---------------------------------------------------------------------------
// MAVLink constants
// ---------------------------------------------------------------------------

/** MAV_AUTOPILOT enum values. */
const MAV_AUTOPILOT_ARDUPILOTMEGA = 3
const MAV_AUTOPILOT_PX4 = 12

/** MAV_TYPE values for vehicle classification. */
const MAV_TYPE_FIXED_WING = 1
const MAV_TYPE_QUADROTOR = 2
const MAV_TYPE_COAXIAL = 3
const MAV_TYPE_HELICOPTER = 4
const MAV_TYPE_HEXAROTOR = 13
const MAV_TYPE_OCTOROTOR = 14
const MAV_TYPE_TRICOPTER = 15
const MAV_TYPE_VTOL_FIXEDROTOR = 22
const MAV_TYPE_SUBMARINE = 12
const MAV_TYPE_GROUND_ROVER = 10

/** MAVLink v2 magic byte. */
const MAVLINK_V2_MAGIC = 0xfd
/** MAVLink v1 magic byte. */
const MAVLINK_V1_MAGIC = 0xfe

/** HEARTBEAT message ID. */
const MSG_HEARTBEAT = 0

// ---------------------------------------------------------------------------
// MSP constants
// ---------------------------------------------------------------------------

/** MSP protocol preamble. */
const MSP_PREAMBLE = [0x24, 0x4d, 0x3c] // "$M<"
/** MSP_API_VERSION command. */
const MSP_API_VERSION = 1
/** MSP_FC_VARIANT command (to distinguish BF vs iNav). */
const MSP_FC_VARIANT = 2

// ---------------------------------------------------------------------------
// Detection result
// ---------------------------------------------------------------------------

export interface DetectionResult {
  protocol: 'mavlink' | 'msp' | 'unknown'
  firmwareType: FirmwareType
  systemId?: number
  componentId?: number
  mavType?: number
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Build a minimal MAVLink v2 HEARTBEAT message for probing.
 * System ID 255, Component ID 190 (GCS convention).
 */
function buildMavlinkHeartbeat(): Uint8Array {
  // MAVLink v2 HEARTBEAT: magic + len + incompat + compat + seq + sysid + compid + msgid(3) + payload(9) + crc(2)
  // Simplified: we send a valid-looking heartbeat, the FC replies with its own
  const buf = new Uint8Array(19)
  buf[0] = MAVLINK_V2_MAGIC // magic
  buf[1] = 9               // payload length
  buf[2] = 0               // incompat flags
  buf[3] = 0               // compat flags
  buf[4] = 0               // sequence
  buf[5] = 255             // system ID (GCS)
  buf[6] = 190             // component ID (GCS)
  buf[7] = 0               // msg ID low byte (HEARTBEAT = 0)
  buf[8] = 0               // msg ID mid byte
  buf[9] = 0               // msg ID high byte
  // Payload (9 bytes): custom_mode(4) + type(1) + autopilot(1) + base_mode(1) + system_status(1) + mavlink_version(1)
  buf[10] = 0              // custom_mode[0]
  buf[11] = 0              // custom_mode[1]
  buf[12] = 0              // custom_mode[2]
  buf[13] = 0              // custom_mode[3]
  buf[14] = 6              // MAV_TYPE_GCS
  buf[15] = 0              // MAV_AUTOPILOT_GENERIC
  buf[16] = 0              // base_mode
  buf[17] = 0              // system_status
  buf[18] = 3              // mavlink_version (v2)
  // Note: CRC omitted for simplicity — most FCs will still respond
  // to a heartbeat probe even without valid CRC
  return buf
}

/**
 * Build an MSP request for the given command ID.
 */
function buildMspRequest(command: number): Uint8Array {
  // MSPv1: $M< + size(0) + command + checksum
  const size = 0
  const checksum = size ^ command
  return new Uint8Array([...MSP_PREAMBLE, size, command, checksum])
}

/**
 * Classify ArduPilot vehicle type from MAV_TYPE.
 */
function classifyArduPilotType(mavType: number): FirmwareType {
  switch (mavType) {
    case MAV_TYPE_FIXED_WING:
    // All VTOL variants run ArduPlane firmware (QuadPlane).
    case 19:  // VTOL_TAILSITTER_DUOROTOR
    case 20:  // VTOL_TAILSITTER_QUADROTOR
    case 21:  // VTOL_TILTROTOR
    case MAV_TYPE_VTOL_FIXEDROTOR: // 22
    case 23:  // VTOL_TAILSITTER
    case 24:  // VTOL_TILTWING
    case 25:  // VTOL_RESERVED5
      return 'ardupilot-plane'
    case MAV_TYPE_QUADROTOR:
    case MAV_TYPE_COAXIAL:
    case MAV_TYPE_HELICOPTER:
    case MAV_TYPE_HEXAROTOR:
    case MAV_TYPE_OCTOROTOR:
    case MAV_TYPE_TRICOPTER:
      return 'ardupilot-copter'
    case MAV_TYPE_SUBMARINE:
      return 'ardupilot-sub'
    case MAV_TYPE_GROUND_ROVER:
      return 'ardupilot-rover'
    default:
      return 'ardupilot-copter' // Default multirotor
  }
}

/**
 * Try to parse a MAVLink heartbeat from incoming data.
 * Returns null if no valid heartbeat found.
 */
function parseMavlinkHeartbeat(data: Uint8Array): {
  autopilot: number
  mavType: number
  systemId: number
  componentId: number
} | null {
  for (let i = 0; i < data.length; i++) {
    // MAVLink v2
    if (data[i] === MAVLINK_V2_MAGIC && i + 18 < data.length) {
      const payloadLen = data[i + 1]
      const sysId = data[i + 5]
      const compId = data[i + 6]
      const msgId = data[i + 7] | (data[i + 8] << 8) | (data[i + 9] << 16)
      if (msgId === MSG_HEARTBEAT && payloadLen >= 9) {
        return {
          mavType: data[i + 14],
          autopilot: data[i + 15],
          systemId: sysId,
          componentId: compId,
        }
      }
    }
    // MAVLink v1
    if (data[i] === MAVLINK_V1_MAGIC && i + 13 < data.length) {
      const payloadLen = data[i + 1]
      const sysId = data[i + 3]
      const compId = data[i + 4]
      const msgId = data[i + 5]
      if (msgId === MSG_HEARTBEAT && payloadLen >= 9) {
        return {
          mavType: data[i + 10],
          autopilot: data[i + 11],
          systemId: sysId,
          componentId: compId,
        }
      }
    }
  }
  return null
}

/**
 * Classify an MSP `FC_VARIANT` identifier into a firmware family.
 *
 * Returns `null` for an EMPTY identifier: an `API_VERSION` reply confirms the
 * transport speaks MSP but names no variant, so the caller must keep waiting
 * for the real `FC_VARIANT` reply rather than defaulting — this is what stops
 * an iNav board whose `API_VERSION` arrives first from being mislabeled
 * Betaflight. A recognized identifier maps to its family; any other non-empty
 * identifier is a confirmed-but-unmodeled MSP FC (`'unknown'`), driven over MSP
 * without a false family claim.
 */
export function classifyMspVariant(variant: string): FirmwareType | null {
  const v = variant.trim().toUpperCase()
  if (v === 'INAV') return 'inav'
  if (v === 'BTFL') return 'betaflight'
  if (v.length > 0) return 'unknown'
  return null
}

/**
 * Try to parse an MSP response from incoming data.
 * Handles both MSPv1 ("$M>") and MSPv2 ("$X>") response frames.
 * Returns the FC variant string if found.
 */
function parseMspResponse(data: Uint8Array): { variant: string } | null {
  for (let i = 0; i < data.length - 3; i++) {
    // MSPv1 response: "$M>" (0x24 0x4d 0x3e) + size + command + data + checksum
    if (data[i] === 0x24 && data[i + 1] === 0x4d && data[i + 2] === 0x3e) {
      const size = data[i + 3]
      const command = data[i + 4]
      // FC_VARIANT response contains 4-byte ASCII identifier
      if (command === MSP_FC_VARIANT && size >= 4 && i + 5 + size < data.length) {
        const variant = String.fromCharCode(
          data[i + 5],
          data[i + 6],
          data[i + 7],
          data[i + 8],
        )
        return { variant: variant.trim() }
      }
      // API_VERSION response — confirms MSP is active
      if (command === MSP_API_VERSION) {
        return { variant: '' } // Unknown variant, but MSP confirmed
      }
    }

    // MSPv2 response: "$X>" (0x24 0x58 0x3e) + flags(1) + cmd(2 LE) + len(2 LE) + data + crc8
    if (data[i] === 0x24 && data[i + 1] === 0x58 && data[i + 2] === 0x3e) {
      if (i + 8 > data.length) continue
      // const flags = data[i + 3]
      const cmd = data[i + 4] | (data[i + 5] << 8)
      const len = data[i + 6] | (data[i + 7] << 8)
      if (i + 8 + len >= data.length) continue

      if (cmd === MSP_FC_VARIANT && len >= 4) {
        const variant = String.fromCharCode(
          data[i + 8],
          data[i + 9],
          data[i + 10],
          data[i + 11],
        )
        return { variant: variant.trim() }
      }
      if (cmd === MSP_API_VERSION) {
        return { variant: '' }
      }
    }
  }
  return null
}

// ---------------------------------------------------------------------------
// Main detector
// ---------------------------------------------------------------------------

/**
 * Probe a transport to detect the protocol and firmware.
 *
 * Sends a MAVLink HEARTBEAT first (3s timeout). If no response,
 * tries MSP API_VERSION + FC_VARIANT (2s timeout). Returns detection
 * result with protocol type and firmware identification.
 *
 * @param sendFn   Send raw bytes to the transport
 * @param onData   Subscribe to incoming data; returns an unsubscribe fn
 */
export async function detectProtocol(
  sendFn: (data: Uint8Array) => void,
  onData: (handler: (data: Uint8Array) => void) => () => void,
): Promise<DetectionResult> {
  // --- MAVLink probe (3s timeout) ---
  const mavResult = await new Promise<DetectionResult | null>((resolve) => {
    const timeout = setTimeout(() => {
      unsub()
      resolve(null)
    }, 3000)

    const unsub = onData((data) => {
      const hb = parseMavlinkHeartbeat(data)
      if (!hb) return

      clearTimeout(timeout)
      unsub()

      let firmwareType: FirmwareType
      if (hb.autopilot === MAV_AUTOPILOT_ARDUPILOTMEGA) {
        firmwareType = classifyArduPilotType(hb.mavType)
      } else if (hb.autopilot === MAV_AUTOPILOT_PX4) {
        firmwareType = 'px4'
      } else {
        firmwareType = 'unknown'
      }

      resolve({
        protocol: 'mavlink',
        firmwareType,
        systemId: hb.systemId,
        componentId: hb.componentId,
        mavType: hb.mavType,
      })
    })

    // Send heartbeat probe
    sendFn(buildMavlinkHeartbeat())
  })

  if (mavResult) return mavResult

  // --- MSP probe (2s timeout) ---
  const mspResult = await new Promise<DetectionResult | null>((resolve) => {
    // Set once any parseable MSP frame arrives (API_VERSION or FC_VARIANT).
    // Confirms the transport speaks MSP even before the variant is known.
    let mspConfirmed = false

    const timeout = setTimeout(() => {
      unsub()
      // We heard MSP frames but never a recognizable FC_VARIANT (e.g. only
      // API_VERSION answered): honest unknown-MSP, never a Betaflight guess.
      resolve(mspConfirmed ? { protocol: 'msp', firmwareType: 'unknown' } : null)
    }, 2000)

    const unsub = onData((data) => {
      const resp = parseMspResponse(data)
      if (!resp) return

      // Any MSP frame confirms the protocol; the variant may still be unknown.
      mspConfirmed = true

      // Only commit a firmware family on a POSITIVE FC_VARIANT identifier. An
      // API_VERSION reply carries no variant (classifyMspVariant → null) — keep
      // listening rather than defaulting, so an iNav board whose API_VERSION
      // arrives before its FC_VARIANT is not mislabeled Betaflight.
      const firmwareType = classifyMspVariant(resp.variant)
      if (firmwareType === null) return

      clearTimeout(timeout)
      unsub()
      resolve({ protocol: 'msp', firmwareType })
    })

    // Send both MSP requests
    sendFn(buildMspRequest(MSP_API_VERSION))
    sendFn(buildMspRequest(MSP_FC_VARIANT))
  })

  if (mspResult) return mspResult

  // --- No response ---
  return {
    protocol: 'unknown',
    firmwareType: 'unknown',
  }
}
