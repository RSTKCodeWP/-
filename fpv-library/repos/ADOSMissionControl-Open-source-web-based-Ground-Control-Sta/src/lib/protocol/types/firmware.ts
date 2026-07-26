/**
 * Firmware handler interface.
 *
 * @module protocol/types/firmware
 */

import type { FirmwareType, VehicleClass, UnifiedFlightMode } from './enums';
import type { ProtocolCapabilities } from './core';

/**
 * Firmware-specific behaviour that differs between autopilots.
 *
 * One handler instance per firmware type. The MAVLink protocol
 * implementation delegates mode encoding/decoding and capability
 * queries here.
 */
export interface FirmwareHandler {
  readonly firmwareType: FirmwareType;
  readonly vehicleClass: VehicleClass;

  /** Convert a unified mode name to the baseMode + customMode pair the FC expects. */
  encodeFlightMode(mode: UnifiedFlightMode): { baseMode: number; customMode: number };

  /** Convert a raw customMode from HEARTBEAT into a unified mode name. */
  decodeFlightMode(customMode: number): UnifiedFlightMode;

  /** List of modes the UI should offer for this firmware. */
  getAvailableModes(): UnifiedFlightMode[];

  /** Mode to select when no explicit mode is set. */
  getDefaultMode(): UnifiedFlightMode;

  /** What this firmware can do. */
  getCapabilities(): ProtocolCapabilities;

  /** Human-readable firmware version string (may read from params). */
  getFirmwareVersion(params?: Map<string, number>): string;

  /** Map a canonical param name to the firmware-specific name (e.g., ArduPilot ATC_RAT_RLL_P → PX4 MC_ROLLRATE_P). */
  mapParameterName(canonical: string): string;

  /** Map a firmware-specific param name back to the canonical name. */
  reverseMapParameterName(firmwareName: string): string;

  /** List of supported MAV_CMD IDs for mission items. Optional -- all commands allowed if not implemented. */
  getSupportedMissionCommands?(): number[];
}
