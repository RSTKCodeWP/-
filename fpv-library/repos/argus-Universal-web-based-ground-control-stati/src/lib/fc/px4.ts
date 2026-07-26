import type { FcAdapter, FcType, FlightMode } from './interface';

/**
 * PX4 custom_mode is a 32-bit value where:
 * - bits [16..23] = main mode
 * - bits [24..31] = sub mode
 */
function mainMode(customMode: number): number {
  return (customMode >> 16) & 0xff;
}
function subMode(customMode: number): number {
  return (customMode >> 24) & 0xff;
}

const PX4_MAIN_MANUAL = 1;
const PX4_MAIN_ALTCTL = 2;
const PX4_MAIN_POSCTL = 3;
const PX4_MAIN_AUTO = 4;
const PX4_MAIN_ACRO = 5;
const PX4_MAIN_OFFBOARD = 6;
const PX4_MAIN_STABILIZED = 7;
const PX4_MAIN_RATTITUDE = 8;

const PX4_AUTO_TAKEOFF = 2;
const PX4_AUTO_LOITER = 3;
const PX4_AUTO_MISSION = 4;
const PX4_AUTO_RTL = 5;
const PX4_AUTO_LAND = 6;
const PX4_AUTO_FOLLOW = 8;
const PX4_AUTO_PRECLAND = 9;

function px4ModeId(main: number, sub: number = 0): number {
  return (sub << 24) | (main << 16);
}

const MODES: Record<string, { main: number; sub: number; name: string; category: FlightMode['category'] }> = {
  manual: { main: PX4_MAIN_MANUAL, sub: 0, name: 'Manual', category: 'manual' },
  stabilized: { main: PX4_MAIN_STABILIZED, sub: 0, name: 'Stabilized', category: 'manual' },
  acro: { main: PX4_MAIN_ACRO, sub: 0, name: 'Acro', category: 'manual' },
  rattitude: { main: PX4_MAIN_RATTITUDE, sub: 0, name: 'Rattitude', category: 'manual' },
  altctl: { main: PX4_MAIN_ALTCTL, sub: 0, name: 'Altitude', category: 'assisted' },
  posctl: { main: PX4_MAIN_POSCTL, sub: 0, name: 'Position', category: 'assisted' },
  offboard: { main: PX4_MAIN_OFFBOARD, sub: 0, name: 'Offboard', category: 'auto' },
  mission: { main: PX4_MAIN_AUTO, sub: PX4_AUTO_MISSION, name: 'Mission', category: 'auto' },
  hold: { main: PX4_MAIN_AUTO, sub: PX4_AUTO_LOITER, name: 'Hold', category: 'auto' },
  rtl: { main: PX4_MAIN_AUTO, sub: PX4_AUTO_RTL, name: 'Return', category: 'emergency' },
  takeoff: { main: PX4_MAIN_AUTO, sub: PX4_AUTO_TAKEOFF, name: 'Takeoff', category: 'auto' },
  land: { main: PX4_MAIN_AUTO, sub: PX4_AUTO_LAND, name: 'Land', category: 'emergency' },
  follow: { main: PX4_MAIN_AUTO, sub: PX4_AUTO_FOLLOW, name: 'Follow', category: 'auto' },
  precland: { main: PX4_MAIN_AUTO, sub: PX4_AUTO_PRECLAND, name: 'Precision Land', category: 'auto' },
};

const PX4_BTNS: [number, string][] = [
  [px4ModeId(PX4_MAIN_POSCTL), 'Position'],
  [px4ModeId(PX4_MAIN_AUTO, PX4_AUTO_MISSION), 'Mission'],
  [px4ModeId(PX4_MAIN_AUTO, PX4_AUTO_RTL), 'Return'],
  [px4ModeId(PX4_MAIN_AUTO, PX4_AUTO_LOITER), 'Hold'],
  [px4ModeId(PX4_MAIN_ALTCTL), 'Altitude'],
  [px4ModeId(PX4_MAIN_STABILIZED), 'Stabilized'],
  [px4ModeId(PX4_MAIN_AUTO, PX4_AUTO_LAND), 'Land'],
  [px4ModeId(PX4_MAIN_MANUAL), 'Manual'],
];

export const px4Adapter: FcAdapter = {
  type: 'px4' as FcType,

  matches(autopilot: number): boolean {
    return autopilot === 12; // MAV_AUTOPILOT_PX4
  },

  modeName(customMode: number): string {
    const main = mainMode(customMode);
    const sub = subMode(customMode);
    for (const m of Object.values(MODES)) {
      if (m.main === main && m.sub === sub) return m.name;
    }
    if (main === PX4_MAIN_AUTO) return `Auto(${sub})`;
    return `PX4_${main}_${sub}`;
  },

  modeButtons(): [number, string][] {
    return PX4_BTNS;
  },

  allModes(): FlightMode[] {
    return Object.values(MODES).map((m) => ({
      id: px4ModeId(m.main, m.sub),
      name: m.name,
      category: m.category,
    }));
  },

  armBaseMode(): number {
    return 209;
  },
  rtlModeId(): number {
    return px4ModeId(PX4_MAIN_AUTO, PX4_AUTO_RTL);
  },
  holdModeId(): number {
    return px4ModeId(PX4_MAIN_AUTO, PX4_AUTO_LOITER);
  },
  autoModeId(): number {
    return px4ModeId(PX4_MAIN_AUTO, PX4_AUTO_MISSION);
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
      22: 'VTOL Standard',
    };
    return map[mavType] || `Type ${mavType}`;
  },
};
