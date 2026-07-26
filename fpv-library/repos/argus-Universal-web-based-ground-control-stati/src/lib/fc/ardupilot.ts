import type { FcAdapter, FcType, FlightMode } from './interface';
import { getModeName, getModeButtons, getAllModes } from '../modeStore';
import type { VehicleType } from '../modeStore';

function _vtype(isPlane: boolean): VehicleType {
  return isPlane ? 'plane' : 'copter';
}

export const ardupilotAdapter: FcAdapter = {
  type: 'ardupilot' as FcType,

  matches(autopilot: number): boolean {
    return autopilot === 3; // MAV_AUTOPILOT_ARDUPILOTMEGA
  },

  modeName(customMode: number, isPlane: boolean): string {
    return getModeName(_vtype(isPlane), customMode);
  },

  modeButtons(isPlane: boolean): [number, string][] {
    return getModeButtons(_vtype(isPlane));
  },

  allModes(isPlane: boolean): FlightMode[] {
    return getAllModes(_vtype(isPlane));
  },

  armBaseMode(): number {
    return 209;
  },
  rtlModeId(isPlane: boolean): number {
    return isPlane ? 11 : 6;
  },
  holdModeId(isPlane: boolean): number {
    return isPlane ? 19 : 5;
  },
  autoModeId(): number {
    return 3;
  },

  vehicleTypeName(mavType: number): string {
    const map: Record<number, string> = {
      1: 'Fixed Wing',
      2: 'Quadrotor',
      3: 'Coaxial',
      4: 'Helicopter',
      10: 'Rover',
      12: 'Submarine',
      13: 'Hexarotor',
      14: 'Octorotor',
      19: 'VTOL Duo',
      20: 'VTOL Quad',
      21: 'VTOL Tilt',
      22: 'VTOL Fixedrotor',
      23: 'VTOL Tailsitter',
      24: 'VTOL Tilt (2)',
      25: 'VTOL Tilt (4)',
    };
    return map[mavType] || `Type ${mavType}`;
  },
};
