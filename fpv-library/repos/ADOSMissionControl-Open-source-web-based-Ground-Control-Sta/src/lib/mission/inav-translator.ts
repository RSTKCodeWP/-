/**
 * Translation between MissionItem (MAVLink wire format) and INavWaypoint (MSP format).
 *
 * MissionItem uses MAV_CMD command codes with x/y/z for lat*1e7/lon*1e7/alt-meters.
 * INavWaypoint uses iNav action codes with lat/lon as float degrees and altitude in cm.
 *
 * @module mission/inav-translator
 */

import type { MissionItem } from '@/lib/protocol/types'
import {
  INAV_WP_ACTION,
  INAV_WP_FLAG_LAST,
  type INavWaypoint,
} from '@/lib/protocol/msp/msp-decoders-inav'

// MAV_CMD constants used in translation
const MAV_CMD_NAV_WAYPOINT     = 16
const MAV_CMD_NAV_RETURN_TO_LAUNCH = 20
const MAV_CMD_NAV_LAND         = 21
const MAV_CMD_NAV_LOITER_UNLIM = 17
const MAV_CMD_NAV_LOITER_TIME  = 19
const MAV_CMD_DO_JUMP          = 177
const MAV_CMD_DO_SET_ROI       = 201
const MAV_CMD_CONDITION_YAW    = 115

/** Translate a MAV_CMD to the corresponding iNav action code. Returns WAYPOINT for unknowns. */
function mavCmdToInavAction(command: number): number {
  switch (command) {
    case MAV_CMD_NAV_WAYPOINT:      return INAV_WP_ACTION.WAYPOINT
    case MAV_CMD_NAV_RETURN_TO_LAUNCH: return INAV_WP_ACTION.RTH
    case MAV_CMD_NAV_LAND:          return INAV_WP_ACTION.LAND
    case MAV_CMD_NAV_LOITER_UNLIM:  return INAV_WP_ACTION.POSHOLD_UNLIM
    case MAV_CMD_NAV_LOITER_TIME:   return INAV_WP_ACTION.POSHOLD_TIME
    case MAV_CMD_DO_JUMP:           return INAV_WP_ACTION.JUMP
    case MAV_CMD_DO_SET_ROI:        return INAV_WP_ACTION.SET_POI
    case MAV_CMD_CONDITION_YAW:     return INAV_WP_ACTION.SET_HEAD
    default:                        return INAV_WP_ACTION.WAYPOINT
  }
}

/** Translate an iNav action code back to a MAV_CMD. */
export function inavActionToMavCmd(action: number): number {
  switch (action) {
    case INAV_WP_ACTION.WAYPOINT:      return MAV_CMD_NAV_WAYPOINT
    case INAV_WP_ACTION.RTH:           return MAV_CMD_NAV_RETURN_TO_LAUNCH
    case INAV_WP_ACTION.LAND:          return MAV_CMD_NAV_LAND
    case INAV_WP_ACTION.POSHOLD_UNLIM: return MAV_CMD_NAV_LOITER_UNLIM
    case INAV_WP_ACTION.POSHOLD_TIME:  return MAV_CMD_NAV_LOITER_TIME
    case INAV_WP_ACTION.JUMP:          return MAV_CMD_DO_JUMP
    case INAV_WP_ACTION.SET_POI:       return MAV_CMD_DO_SET_ROI
    case INAV_WP_ACTION.SET_HEAD:      return MAV_CMD_CONDITION_YAW
    default:                           return MAV_CMD_NAV_WAYPOINT
  }
}

/** iNav firmware hard limit on waypoints per mission. */
export const INAV_MAX_WAYPOINTS = 60

/**
 * Convert an array of MissionItems into iNav waypoints.
 *
 * The last waypoint in the array is flagged with INAV_WP_FLAG_LAST (0xA5).
 * Index numbers are 1-based per the iNav MSP_WP protocol.
 *
 * Altitude: MissionItem.z is in meters. INavWaypoint.altitude is in cm.
 * Position: MissionItem.x/y are lat*1e7/lon*1e7. INavWaypoint.lat/lon are float degrees.
 *
 * JUMP indexing: MAVLink DO_JUMP param1 is a 0-based mission sequence.
 * iNav JUMP p1 is a 1-based waypoint number. The target is adjusted by +1 here.
 *
 * Throws if items.length exceeds INAV_MAX_WAYPOINTS (60).
 */
export function translateToInavWaypoints(items: MissionItem[]): INavWaypoint[] {
  if (items.length > INAV_MAX_WAYPOINTS) {
    throw new Error(`iNav mission limit exceeded: ${items.length} waypoints, maximum is ${INAV_MAX_WAYPOINTS}.`)
  }
  return items.map((item, idx) => {
    const isLast = idx === items.length - 1
    const action = mavCmdToInavAction(item.command)
    // For JUMP, MAVLink uses 0-based target, iNav uses 1-based. Adjust only for JUMP.
    const p1 = action === INAV_WP_ACTION.JUMP
      ? Math.round(item.param1) + 1
      : Math.round(item.param1)
    return {
      number: idx + 1,
      action,
      lat: item.x / 1e7,
      lon: item.y / 1e7,
      altitude: Math.round(item.z * 100), // meters to cm
      // p1: jump target (1-based wp number) for JUMP; loiter time for POSHOLD_TIME; heading for SET_HEAD
      p1,
      // p2: jump repeat count for JUMP; speed override for WAYPOINT
      p2: Math.round(item.param2),
      p3: Math.round(item.param3),
      flag: isLast ? INAV_WP_FLAG_LAST : 0,
    }
  })
}

/**
 * Convert iNav waypoints into MissionItems.
 *
 * Altitude: INavWaypoint.altitude is cm, MissionItem.z is meters.
 * Position: INavWaypoint.lat/lon are float degrees, MissionItem.x/y are lat*1e7/lon*1e7.
 */
export function translateFromInavWaypoints(wps: INavWaypoint[]): MissionItem[] {
  // MAV_FRAME_GLOBAL_RELATIVE_ALT = 3
  const frame = 3
  return wps.map((wp, idx) => {
    // For JUMP, iNav is 1-based and MAVLink is 0-based; subtract 1 on reverse translation.
    const param1 = wp.action === INAV_WP_ACTION.JUMP
      ? wp.p1 - 1
      : wp.p1
    return {
      seq: idx,
      frame,
      command: inavActionToMavCmd(wp.action),
      current: idx === 0 ? 1 : 0,
      autocontinue: 1,
      param1,
      param2: wp.p2,
      param3: wp.p3,
      param4: 0,
      x: Math.round(wp.lat * 1e7),
      y: Math.round(wp.lon * 1e7),
      z: wp.altitude / 100, // cm to meters
    }
  })
}
