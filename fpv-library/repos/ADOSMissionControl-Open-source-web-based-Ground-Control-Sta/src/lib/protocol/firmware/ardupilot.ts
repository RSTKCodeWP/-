/**
 * ArduPilot firmware handlers for Altnautica Command GCS.
 *
 * Provides flight-mode encoding/decoding and capability reporting
 * for ArduPlane and ArduCopter firmware variants.
 *
 * @module firmware/ardupilot
 */

import type {
  FirmwareType,
  FirmwareHandler,
  UnifiedFlightMode,
  VehicleClass,
  ProtocolCapabilities,
} from '../types'
import { px4Handler, createPX4Handler, px4VehicleClassFromMavType } from './px4'
import { betaflightHandler } from './betaflight'
import { inavHandler } from './inav'
import { GenericHandler } from './generic-handler'
import { MAV_AUTOPILOT, MAV_TYPE, ARDUPILOT_CAPABILITIES } from './ardupilot-capabilities'

// Re-export for consumers that import from this module
export { MAV_AUTOPILOT, MAV_TYPE, ARDUPILOT_CAPABILITIES } from './ardupilot-capabilities'

// ---------------------------------------------------------------------------
// Mode tables — custom_mode ↔ UnifiedFlightMode
// ---------------------------------------------------------------------------

/** ArduPlane custom_mode → UnifiedFlightMode mapping */
const ARDUPLANE_MODES: ReadonlyArray<[number, UnifiedFlightMode]> = [
  [0, 'MANUAL'],
  [1, 'CIRCLE'],
  [2, 'STABILIZE'],
  [3, 'TRAINING'],
  [4, 'ACRO'],
  [5, 'FBWA'],
  [6, 'FBWB'],
  [7, 'CRUISE'],
  [8, 'AUTOTUNE'],
  [10, 'AUTO'],
  [11, 'RTL'],
  [12, 'LOITER'],
  [14, 'AVOID_ADSB'],
  [15, 'GUIDED'],
  [17, 'QSTABILIZE'],
  [18, 'QHOVER'],
  [19, 'QLOITER'],
  [20, 'QLAND'],
  [21, 'QRTL'],
  [22, 'QAUTOTUNE'],
  [23, 'QACRO'],
  [24, 'THERMAL'],
  [13, 'TAKEOFF'],
  [25, 'LOITER_TO_QLAND'],
  [26, 'AUTOLAND'],
]

/**
 * ArduRover custom_mode → UnifiedFlightMode mapping.
 * Rover mode numbers per the ArduPilot Rover mode set. `INITIALISING`(16) is
 * intentionally omitted (a transient boot state, never a selectable mode) and
 * decodes to UNKNOWN.
 */
const ARDUROVER_MODES: ReadonlyArray<[number, UnifiedFlightMode]> = [
  [0, 'MANUAL'],
  [1, 'ACRO'],
  [3, 'STEERING'],
  [4, 'HOLD'],
  [5, 'LOITER'],
  [6, 'FOLLOW'],
  [7, 'SIMPLE'],
  [8, 'DOCK'],
  [9, 'CIRCLE'],
  [10, 'AUTO'],
  [11, 'RTL'],
  [12, 'SMART_RTL'],
  [15, 'GUIDED'],
]

/**
 * ArduSub custom_mode → UnifiedFlightMode mapping.
 * Sub mode numbers per the ArduPilot Sub mode set.
 */
const ARDUSUB_MODES: ReadonlyArray<[number, UnifiedFlightMode]> = [
  [0, 'STABILIZE'],
  [1, 'ACRO'],
  [2, 'ALT_HOLD'],
  [3, 'AUTO'],
  [4, 'GUIDED'],
  [7, 'CIRCLE'],
  [9, 'SURFACE'],
  [16, 'POSHOLD'],
  [19, 'MANUAL'],
  [20, 'MOTOR_DETECT'],
  [21, 'SURFTRAK'],
]

/** ArduCopter custom_mode → UnifiedFlightMode mapping */
const ARDUCOPTER_MODES: ReadonlyArray<[number, UnifiedFlightMode]> = [
  [0, 'STABILIZE'],
  [1, 'ACRO'],
  [2, 'ALT_HOLD'],
  [3, 'AUTO'],
  [4, 'GUIDED'],
  [5, 'LOITER'],
  [6, 'RTL'],
  [7, 'CIRCLE'],
  [9, 'LAND'],
  [11, 'DRIFT'],
  [13, 'SPORT'],
  [14, 'FLIP'],
  [15, 'AUTOTUNE'],
  [16, 'POSHOLD'],
  [17, 'BRAKE'],
  [18, 'THROW'],
  [19, 'AVOID_ADSB'],
  [21, 'SMART_RTL'],
  [22, 'FLOWHOLD'],
  [23, 'FOLLOW'],
  [24, 'ZIGZAG'],
  [25, 'SYSTEMID'],
  [26, 'HELI_AUTOROTATE'],
  [27, 'AUTO_RTL'],
  [20, 'GUIDED_NOGPS'],
  [28, 'TURTLE'],
]

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function buildMaps(
  table: ReadonlyArray<[number, UnifiedFlightMode]>,
): {
  modeToCustom: Map<UnifiedFlightMode, number>
  customToMode: Map<number, UnifiedFlightMode>
} {
  const modeToCustom = new Map<UnifiedFlightMode, number>()
  const customToMode = new Map<number, UnifiedFlightMode>()
  for (const [custom, mode] of table) {
    customToMode.set(custom, mode)
    // First occurrence wins — some modes may alias
    if (!modeToCustom.has(mode)) {
      modeToCustom.set(mode, custom)
    }
  }
  return { modeToCustom, customToMode }
}

/** Firmware handler for ArduPlane. */
export class ArduPlaneHandler implements FirmwareHandler {
  readonly firmwareType: FirmwareType = 'ardupilot-plane'
  readonly vehicleClass: VehicleClass = 'plane'

  private modeToCustom: Map<UnifiedFlightMode, number>
  private customToMode: Map<number, UnifiedFlightMode>

  constructor() {
    const maps = buildMaps(ARDUPLANE_MODES)
    this.modeToCustom = maps.modeToCustom
    this.customToMode = maps.customToMode
  }

  encodeFlightMode(mode: UnifiedFlightMode): { baseMode: number; customMode: number } {
    const customMode = this.modeToCustom.get(mode)
    if (customMode === undefined) throw new Error(`Unsupported mode for ArduPlane: ${mode}`)
    return { baseMode: 1, customMode }
  }

  decodeFlightMode(customMode: number): UnifiedFlightMode {
    return this.customToMode.get(customMode) ?? 'UNKNOWN'
  }

  getAvailableModes(): UnifiedFlightMode[] { return ARDUPLANE_MODES.map(([, mode]) => mode) }
  getDefaultMode(): UnifiedFlightMode { return 'MANUAL' }
  getCapabilities(): ProtocolCapabilities { return ARDUPILOT_CAPABILITIES }
  getFirmwareVersion(_params?: Map<string, number>): string { return 'ArduPlane' }
  mapParameterName(canonical: string): string { return canonical }
  reverseMapParameterName(firmwareName: string): string { return firmwareName }
}

/** Firmware handler for ArduCopter. */
export class ArduCopterHandler implements FirmwareHandler {
  readonly firmwareType: FirmwareType = 'ardupilot-copter'
  readonly vehicleClass: VehicleClass = 'copter'

  private modeToCustom: Map<UnifiedFlightMode, number>
  private customToMode: Map<number, UnifiedFlightMode>

  constructor() {
    const maps = buildMaps(ARDUCOPTER_MODES)
    this.modeToCustom = maps.modeToCustom
    this.customToMode = maps.customToMode
  }

  encodeFlightMode(mode: UnifiedFlightMode): { baseMode: number; customMode: number } {
    const customMode = this.modeToCustom.get(mode)
    if (customMode === undefined) throw new Error(`Unsupported mode for ArduCopter: ${mode}`)
    return { baseMode: 1, customMode }
  }

  decodeFlightMode(customMode: number): UnifiedFlightMode {
    return this.customToMode.get(customMode) ?? 'UNKNOWN'
  }

  getAvailableModes(): UnifiedFlightMode[] { return ARDUCOPTER_MODES.map(([, mode]) => mode) }
  getDefaultMode(): UnifiedFlightMode { return 'STABILIZE' }
  getCapabilities(): ProtocolCapabilities { return ARDUPILOT_CAPABILITIES }
  getFirmwareVersion(_params?: Map<string, number>): string { return 'ArduCopter' }
  mapParameterName(canonical: string): string { return canonical }
  reverseMapParameterName(firmwareName: string): string { return firmwareName }
}

/** Firmware handler for ArduRover (ground rover / surface boat). */
export class ArduRoverHandler implements FirmwareHandler {
  readonly firmwareType: FirmwareType = 'ardupilot-rover'
  readonly vehicleClass: VehicleClass = 'rover'

  private modeToCustom: Map<UnifiedFlightMode, number>
  private customToMode: Map<number, UnifiedFlightMode>

  constructor() {
    const maps = buildMaps(ARDUROVER_MODES)
    this.modeToCustom = maps.modeToCustom
    this.customToMode = maps.customToMode
  }

  encodeFlightMode(mode: UnifiedFlightMode): { baseMode: number; customMode: number } {
    const customMode = this.modeToCustom.get(mode)
    if (customMode === undefined) throw new Error(`Unsupported mode for ArduRover: ${mode}`)
    return { baseMode: 1, customMode }
  }

  decodeFlightMode(customMode: number): UnifiedFlightMode {
    return this.customToMode.get(customMode) ?? 'UNKNOWN'
  }

  getAvailableModes(): UnifiedFlightMode[] { return ARDUROVER_MODES.map(([, mode]) => mode) }
  getDefaultMode(): UnifiedFlightMode { return 'MANUAL' }
  getCapabilities(): ProtocolCapabilities { return ARDUPILOT_CAPABILITIES }
  getFirmwareVersion(_params?: Map<string, number>): string { return 'ArduRover' }
  mapParameterName(canonical: string): string { return canonical }
  reverseMapParameterName(firmwareName: string): string { return firmwareName }
}

/** Firmware handler for ArduSub. */
export class ArduSubHandler implements FirmwareHandler {
  readonly firmwareType: FirmwareType = 'ardupilot-sub'
  readonly vehicleClass: VehicleClass = 'sub'

  private modeToCustom: Map<UnifiedFlightMode, number>
  private customToMode: Map<number, UnifiedFlightMode>

  constructor() {
    const maps = buildMaps(ARDUSUB_MODES)
    this.modeToCustom = maps.modeToCustom
    this.customToMode = maps.customToMode
  }

  encodeFlightMode(mode: UnifiedFlightMode): { baseMode: number; customMode: number } {
    const customMode = this.modeToCustom.get(mode)
    if (customMode === undefined) throw new Error(`Unsupported mode for ArduSub: ${mode}`)
    return { baseMode: 1, customMode }
  }

  decodeFlightMode(customMode: number): UnifiedFlightMode {
    return this.customToMode.get(customMode) ?? 'UNKNOWN'
  }

  getAvailableModes(): UnifiedFlightMode[] { return ARDUSUB_MODES.map(([, mode]) => mode) }
  getDefaultMode(): UnifiedFlightMode { return 'MANUAL' }
  getCapabilities(): ProtocolCapabilities { return ARDUPILOT_CAPABILITIES }
  getFirmwareVersion(_params?: Map<string, number>): string { return 'ArduSub' }
  mapParameterName(canonical: string): string { return canonical }
  reverseMapParameterName(firmwareName: string): string { return firmwareName }
}

/** MAV_TYPE values for rover/boat/sub (not in the shared MAV_TYPE subset). */
const MAV_TYPE_GROUND_ROVER = 10
const MAV_TYPE_SURFACE_BOAT = 11
const MAV_TYPE_SUBMARINE = 12

/** Create the appropriate firmware handler based on MAVLink HEARTBEAT fields. */
export function createFirmwareHandler(autopilot: number, vehicleType: number): FirmwareHandler {
  // PX4 autopilot. Classify the vehicle from MAV_TYPE so a PX4 plane/VTOL is
  // not treated as a copter (wrong mission-command set + copter-only UI).
  if (autopilot === MAV_AUTOPILOT.PX4) {
    return createPX4Handler(px4VehicleClassFromMavType(vehicleType))
  }

  // ArduPilot — select by vehicle type
  if (autopilot === MAV_AUTOPILOT.ARDUPILOTMEGA) {
    switch (vehicleType) {
      case MAV_TYPE.FIXED_WING:
      // Every VTOL variant runs ArduPlane firmware (QuadPlane): classify as a
      // plane so the fixed-wing mode map + Q_*/TECS surfaces apply.
      case 19:  // VTOL_TAILSITTER_DUOROTOR
      case 20:  // VTOL_TAILSITTER_QUADROTOR
      case 21:  // VTOL_TILTROTOR
      case MAV_TYPE.VTOL_FIXEDROTOR: // 22
      case 23:  // VTOL_TAILSITTER
      case 24:  // VTOL_TILTWING
      case 25:  // VTOL_RESERVED5
        return new ArduPlaneHandler()

      case MAV_TYPE.QUADROTOR:
      case MAV_TYPE.COAXIAL:
      case MAV_TYPE.HELICOPTER:
      case MAV_TYPE.HEXAROTOR:
      case MAV_TYPE.OCTOROTOR:
      case MAV_TYPE.TRICOPTER:
        return new ArduCopterHandler()

      case MAV_TYPE_GROUND_ROVER:
      case MAV_TYPE_SURFACE_BOAT:
        return new ArduRoverHandler()

      case MAV_TYPE_SUBMARINE:
        return new ArduSubHandler()

      // Unrecognized ArduPilot vehicle type — copter is the safe display
      // default; mode encode for a copter-numbered request stays correct for
      // the copter mode set.
      default:
        return new ArduCopterHandler()
    }
  }

  // Unknown autopilot
  return new GenericHandler()
}

/** Create a firmware handler by FirmwareType string. */
export function createFirmwareHandlerByType(firmwareType: FirmwareType): FirmwareHandler {
  switch (firmwareType) {
    case 'ardupilot-copter':
      return new ArduCopterHandler()
    case 'ardupilot-plane':
      return new ArduPlaneHandler()
    case 'ardupilot-rover':
      return new ArduRoverHandler()
    case 'ardupilot-sub':
      return new ArduSubHandler()
    case 'px4':
      return px4Handler
    case 'betaflight':
      return betaflightHandler
    case 'inav':
      return inavHandler
    default:
      return new GenericHandler()
  }
}
