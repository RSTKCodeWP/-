/**
 * Flight Controller abstraction interface.
 *
 * This allows the GCS to work with both ArduPilot and PX4
 * through a unified API regardless of differences in mode numbering,
 * parameter names, and MAVLink usage.
 */

export type FcType = 'ardupilot' | 'px4' | 'unknown';

export interface FlightMode {
  id: number;
  name: string;
  category: 'manual' | 'assisted' | 'auto' | 'emergency';
}

export interface FcAdapter {
  type: FcType;

  /** Detect FC type from HEARTBEAT autopilot field */
  matches(autopilot: number): boolean;

  /** Resolve mode name from custom_mode field */
  modeName(customMode: number, isPlane: boolean): string;

  /** Get mode list for quick-switch buttons */
  modeButtons(isPlane: boolean): [number, string][];

  /** Get all available flight modes */
  allModes(isPlane: boolean): FlightMode[];

  /** ARM base_mode value to send in SET_MODE */
  armBaseMode(): number;

  /** RTL mode ID */
  rtlModeId(isPlane: boolean): number;

  /** Loiter/Hold mode ID */
  holdModeId(isPlane: boolean): number;

  /** Auto mode ID */
  autoModeId(isPlane: boolean): number;

  /** Vehicle type name from MAV_TYPE */
  vehicleTypeName(mavType: number): string;
}
