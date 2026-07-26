/**
 * ArduPilot OSD parameter adapter.
 *
 * ArduPilot configures its onboard OSD (analog MAX7456, MSP/DisplayPort, DJI)
 * through ordinary parameters, one trio per panel per screen:
 *
 *   OSD{screen}_{PANEL}_EN   enable flag (0/1)
 *   OSD{screen}_{PANEL}_X    column
 *   OSD{screen}_{PANEL}_Y    row
 *
 * Screens are 1..4. This module maps our editor element IDs to ArduPilot panel
 * suffixes and reads/writes the layout. Crucially, it only ever touches params
 * that actually exist on the connected board (panel sets differ by firmware
 * version and vehicle), so reads and uploads never reference phantom params.
 *
 * Panel names are taken verbatim from ArduPilot (cross-checked against Mission
 * Planner). Where a panel has historical aliases (e.g. BAT_VOLT vs BATVOLT) we
 * list them in preference order and resolve against the live param set.
 */

import type { OsdElementId } from './element-registry';

/** Minimal shape we need from the parameter store. */
export interface OsdParamLike {
  value: number;
  type?: number;
}
export type OsdParamMap = ReadonlyMap<string, OsdParamLike>;

export const AP_OSD_SCREENS = [1, 2, 3, 4] as const;
export type ArdupilotOsdScreen = (typeof AP_OSD_SCREENS)[number];

/**
 * Editor element -> ArduPilot panel suffix candidates (first match wins).
 * Elements with no ArduPilot equivalent are intentionally absent and remain
 * simulator-only.
 */
export const AP_PANEL_BY_ELEMENT: Partial<Record<OsdElementId, string[]>> = {
  // General
  flymode: ['FLTMODE'],
  armed_status: ['ARMING'],
  craft_name: ['CALLSIGN'],
  messages: ['MESSAGE'],
  // Battery & power
  battery_voltage: ['BAT_VOLT', 'BATVOLT'],
  battery_cell_voltage: ['AVGCELLV', 'CELLVOLT'],
  current_draw: ['CURRENT'],
  mah_drawn: ['BATUSED'],
  power_watts: ['POWER'],
  efficiency: ['EFF'],
  // Altitude & vario
  altitude: ['ALTITUDE'],
  vario: ['VSPEED'],
  // Speed & distance
  speed: ['GSPEED'],
  airspeed: ['ASPEED', 'ASPD1'],
  distance: ['HOMEDIST', 'DIST'],
  home_direction: ['HOMEDIR', 'HOME'],
  // GPS
  gps_sats: ['SATS'],
  gps_hdop: ['HDOP'],
  latitude: ['GPSLAT'],
  longitude: ['GPSLONG'],
  // Attitude
  crosshairs: ['CRSSHAIR'],
  artificial_horizon: ['HORIZON'],
  horizon_sidebars: ['SIDEBARS'],
  pitch: ['PITCH'],
  roll: ['ROLL'],
  heading: ['HEADING'],
  heading_graph: ['COMPASS'],
  // Timers
  flight_time: ['FLTIME'],
  rtc_time: ['CLK'],
  // Radio & control
  rssi: ['RSSI'],
  rssi_dbm: ['LINK_Q'],
  throttle: ['THROTTLE'],
  // Sensors
  baro_temp: ['BTEMP'],
  imu_temp: ['TEMP'],
  esc_temp: ['ESCTEMP'],
  esc_rpm: ['ESCRPM', 'BLHRPM'],
  // Mission
  vtx_channel: ['VTX_PWR'],
  wind_horizontal: ['WIND'],
};

const MAV_PARAM_TYPE_REAL32 = 9;

/** Build the parameter name for a panel field on a screen. */
export function apOsdParamName(
  screen: ArdupilotOsdScreen,
  panel: string,
  field: 'EN' | 'X' | 'Y',
): string {
  return `OSD${screen}_${panel}_${field}`;
}

/**
 * Resolve which panel suffix for an element actually exists on the FC for a
 * given screen. Returns the suffix, or null if this element isn't supported.
 */
export function resolveApPanel(
  elementId: OsdElementId,
  screen: ArdupilotOsdScreen,
  params: OsdParamMap,
): string | null {
  const candidates = AP_PANEL_BY_ELEMENT[elementId];
  if (!candidates) return null;
  for (const panel of candidates) {
    if (params.has(apOsdParamName(screen, panel, 'EN'))) return panel;
  }
  return null;
}

/** True if the connected board exposes any OSD parameters at all. */
export function hasArdupilotOsd(params: OsdParamMap): boolean {
  for (const name of params.keys()) {
    if (/^OSD[1-4]_[A-Z0-9_]+_EN$/.test(name)) return true;
  }
  return false;
}

/** Which OSD screens (1..4) are present/usable on the board. */
export function detectArdupilotOsdScreens(params: OsdParamMap): ArdupilotOsdScreen[] {
  const present = new Set<number>();
  for (const name of params.keys()) {
    const m = /^OSD([1-4])_[A-Z0-9_]+_EN$/.exec(name);
    if (m) present.add(Number(m[1]));
  }
  return AP_OSD_SCREENS.filter((s) => present.has(s));
}

export interface ApOsdPosition {
  x: number;
  y: number;
  enabled: boolean;
}

export interface ApOsdReadResult {
  /** Element layout read from the FC (only elements the board supports). */
  positions: Partial<Record<OsdElementId, ApOsdPosition>>;
  /** Number of elements resolved. */
  resolved: number;
}

/**
 * Read the OSD layout for a screen from the downloaded parameters into our
 * element model. Only elements whose panel exists on the board are returned.
 */
export function readArdupilotOsd(
  params: OsdParamMap,
  screen: ArdupilotOsdScreen,
): ApOsdReadResult {
  const positions: Partial<Record<OsdElementId, ApOsdPosition>> = {};
  let resolved = 0;

  for (const elementId of Object.keys(AP_PANEL_BY_ELEMENT) as OsdElementId[]) {
    const panel = resolveApPanel(elementId, screen, params);
    if (!panel) continue;
    const en = params.get(apOsdParamName(screen, panel, 'EN'));
    const x = params.get(apOsdParamName(screen, panel, 'X'));
    const y = params.get(apOsdParamName(screen, panel, 'Y'));
    if (!en || !x || !y) continue;
    positions[elementId] = {
      x: Math.round(x.value),
      y: Math.round(y.value),
      enabled: en.value >= 0.5,
    };
    resolved++;
  }

  return { positions, resolved };
}

export interface ParamWrite {
  paramId: string;
  value: number;
  type: number;
}

/**
 * Build the parameter writes needed to push an editor layout to a screen.
 * Only elements supported by the board are included, and each field reuses the
 * param's existing on-board type so PARAM_SET confirmations match.
 */
export function buildArdupilotOsdWrites(
  layout: Partial<Record<OsdElementId, ApOsdPosition>>,
  params: OsdParamMap,
  screen: ArdupilotOsdScreen,
): ParamWrite[] {
  const writes: ParamWrite[] = [];

  const push = (name: string, value: number) => {
    const existing = params.get(name);
    if (!existing) return; // never write a param the board doesn't have
    writes.push({ paramId: name, value, type: existing.type ?? MAV_PARAM_TYPE_REAL32 });
  };

  for (const [elementId, pos] of Object.entries(layout) as [OsdElementId, ApOsdPosition][]) {
    const panel = resolveApPanel(elementId, screen, params);
    if (!panel) continue;
    push(apOsdParamName(screen, panel, 'EN'), pos.enabled ? 1 : 0);
    push(apOsdParamName(screen, panel, 'X'), Math.round(pos.x));
    push(apOsdParamName(screen, panel, 'Y'), Math.round(pos.y));
  }

  return writes;
}

/** Elements that this board can actually display (for greying out the rest). */
export function supportedArdupilotElements(
  params: OsdParamMap,
  screen: ArdupilotOsdScreen,
): Set<OsdElementId> {
  const set = new Set<OsdElementId>();
  for (const elementId of Object.keys(AP_PANEL_BY_ELEMENT) as OsdElementId[]) {
    if (resolveApPanel(elementId, screen, params)) set.add(elementId);
  }
  return set;
}
