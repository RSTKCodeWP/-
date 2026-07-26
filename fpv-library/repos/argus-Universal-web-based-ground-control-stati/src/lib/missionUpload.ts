/**
 * Mission-item builder shared between WebSocket and WebSerial upload paths.
 *
 * Mirrors backend/commands/_mission.py:_upload_mission so that an upload
 * issued over WebSerial produces an identical mission layout on the FC as
 * one issued via the Python backend.
 *
 * Mission layout:
 *   seq 0  HOME (cmd 16, lat=lon=alt=0)
 *   seq 1  TAKEOFF (cmd 22, alt=takeoff_alt)
 *   seq N+ optional attachments per waypoint, in order:
 *            DO_CHANGE_SPEED (cmd 178, when speed > 0)
 *            NAV waypoint (cmd 16/18/19/82 by type)
 *            DO_SET_SERVO (cmd 183) if cmd_servo
 *            DO_SET_ROI (cmd 201) if cmd_roi
 *            DO_SET_CAM_TRIGG_DIST (cmd 206) if cmd_cam_trig
 *            CONDITION_YAW (cmd 115) if cmd_yaw
 *            DO_VTOL_TRANSITION (cmd 3000) if cmd_vtol
 *            DO_SET_RELAY (cmd 181) if drop
 *   last   RTL (cmd 20)
 */

import type { Waypoint } from './types';

export interface MissionItem {
  seq: number;
  command: number; // MAV_CMD value
  frame: number; // MAV_FRAME (3 = GLOBAL_RELATIVE_ALT_INT, 2 = MISSION)
  current: number; // 1 on seq 0, else 0
  autocontinue: number;
  p1: number;
  p2: number;
  p3: number;
  p4: number;
  x: number; // lat scaled by 1e7 (int32)
  y: number; // lon scaled by 1e7 (int32)
  z: number; // alt (float)
}

const NAV_FRAME_CMDS = new Set([16, 18, 19, 21, 22, 82]);

function navCmdFor(wpType: Waypoint['type']): { cmd: number; p1Source: 'loiter_param' | 'delay'; defaultP1: number } {
  if (wpType === 'loiter_turns') return { cmd: 18, p1Source: 'loiter_param', defaultP1: 3 };
  if (wpType === 'loiter_time') return { cmd: 19, p1Source: 'loiter_param', defaultP1: 10 };
  if (wpType === 'spline') return { cmd: 82, p1Source: 'delay', defaultP1: 0 };
  return { cmd: 16, p1Source: 'delay', defaultP1: 0 };
}

export function buildMissionItems(waypoints: Waypoint[], takeoffAlt: number): MissionItem[] {
  const items: MissionItem[] = [];
  const push = (cmd: number, p1: number, p2: number, p3: number, p4: number, lat: number, lon: number, alt: number) => {
    const seq = items.length;
    const frame = NAV_FRAME_CMDS.has(cmd) ? 3 : 2;
    items.push({
      seq,
      command: cmd,
      frame,
      current: seq === 0 ? 1 : 0,
      autocontinue: 1,
      p1,
      p2,
      p3,
      p4,
      // Match backend's int(float(lat) * 1e7) (truncate toward zero) for
      // byte-exact parity with backend/commands/_helpers.py:send_mission_item_int.
      x: Math.trunc(lat * 1e7),
      y: Math.trunc(lon * 1e7),
      z: alt,
    });
  };

  push(16, 0, 0, 0, 0, 0, 0, 0); // HOME
  push(22, 0, 0, 0, 0, 0, 0, takeoffAlt); // TAKEOFF

  for (const wp of waypoints) {
    const speed = Number(wp.speed) || 0;
    if (speed > 0) {
      push(178, 1, speed, 0, 0, 0, 0, 0); // DO_CHANGE_SPEED
    }
    const { cmd: navCmd, p1Source, defaultP1 } = navCmdFor(wp.type);
    const navP1 = p1Source === 'loiter_param' ? Number(wp.loiter_param ?? defaultP1) : Number(wp.delay ?? 0);
    push(navCmd, navP1, 0, 0, 0, wp.lat, wp.lon, wp.alt ?? takeoffAlt);

    if (wp.cmd_servo) {
      push(183, Number(wp.cmd_servo.num ?? 1), Number(wp.cmd_servo.pwm ?? 1500), 0, 0, 0, 0, 0);
    }
    if (wp.cmd_roi) {
      push(201, 0, 0, 0, 0, Number(wp.cmd_roi.lat ?? 0), Number(wp.cmd_roi.lon ?? 0), Number(wp.cmd_roi.alt ?? 0));
    }
    if (wp.cmd_cam_trig) {
      push(206, Number(wp.cmd_cam_trig.dist ?? 0), 0, 0, 0, 0, 0, 0);
    }
    if (wp.cmd_yaw) {
      push(115, Number(wp.cmd_yaw.deg ?? 0), 0, Number(wp.cmd_yaw.dir ?? 1), 0, 0, 0, 0);
    }
    if (wp.cmd_vtol) {
      push(3000, Number(wp.cmd_vtol.mode ?? 4), 0, 0, 0, 0, 0, 0);
    }
    if (wp.drop) {
      push(181, 0, 0, 0, 0, 0, 0, 0); // DO_SET_RELAY (relay 0 ON)
    }
  }

  push(20, 0, 0, 0, 0, 0, 0, 0); // RTL

  return items;
}

/**
 * Fence polygon items: MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION (5001).
 * Mirrors backend/commands/_mission.py:cmd_fence_upload and the wire shape
 * built by backend/commands/_helpers.py:send_fence_item_int (frame=3,
 * current=0, autocontinue=1, p1=total vertex count).
 *
 * Only the inclusion-polygon variant is implemented. AP also accepts
 * exclusion polygons (5002) and circular fences (5003/5004) but the
 * existing FencePanel only emits inclusion polygons.
 */
export function buildFenceItems(polygon: { lat: number; lon: number }[]): MissionItem[] {
  const n = polygon.length;
  return polygon.map((pt, i) => ({
    seq: i,
    command: 5001,
    frame: 3,
    current: 0,
    autocontinue: 1,
    p1: n, // total vertex count (read by AP_Fence to size the polygon)
    p2: 0,
    p3: 0,
    p4: 0,
    x: Math.trunc(pt.lat * 1e7),
    y: Math.trunc(pt.lon * 1e7),
    z: 0,
  }));
}

export function validateFencePolygon(
  polygon: { lat: number; lon: number }[],
): { ok: true } | { ok: false; error: string } {
  if (polygon.length < 3) return { ok: false, error: 'Fence needs at least 3 vertices' };
  if (polygon.length > 200) return { ok: false, error: 'Fence too large (max 200 vertices)' };
  for (const p of polygon) {
    const lat = Number(p.lat),
      lon = Number(p.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return { ok: false, error: 'Invalid fence coordinates' };
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return { ok: false, error: 'Invalid fence coordinates' };
  }
  return { ok: true };
}

export function validateMissionWaypoints(waypoints: Waypoint[]): { ok: true } | { ok: false; error: string } {
  if (waypoints.length === 0) return { ok: false, error: 'No waypoints' };
  if (waypoints.length > 500) return { ok: false, error: 'Mission too large (max 500 WP)' };
  for (const wp of waypoints) {
    const lat = Number(wp.lat),
      lon = Number(wp.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return { ok: false, error: 'Invalid coordinates' };
    if (Math.abs(lat) < 0.001) return { ok: false, error: 'Invalid coordinates' };
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return { ok: false, error: 'Invalid coordinates' };
    const alt = Number(wp.alt ?? 0);
    if (!Number.isFinite(alt) || alt < -500 || alt > 100000) return { ok: false, error: 'Invalid coordinates' };
  }
  return { ok: true };
}

/**
 * Raw mission item shape received over the wire — keep the on-FC field
 * structure so the conversion to Waypoint[] can be unit-tested in isolation
 * from the transport state machine.
 */
export interface RawMissionItem {
  seq: number;
  cmd: number;
  lat: number;
  lon: number;
  alt: number;
  p1: number;
  p2: number;
  p3: number;
  p4: number;
  frame: number;
  current: number;
  autocontinue: number;
}

/**
 * Inverse of buildMissionItems: collapse a downloaded mission's raw items
 * back into the operator-visible Waypoint[] the UI works with. Mirrors
 * backend/mavlink_handlers.py:handle_mission_item_int (lines 438-459) byte
 * for byte — same cmd handling, same DO_CHANGE_SPEED carry, same drop-relay
 * coalescing onto the preceding waypoint, same skip rules for HOME / TAKEOFF
 * / RTL / SERVO / ROI / CAM_TRIG / YAW / VTOL.
 */
export function missionItemsToWaypoints(items: RawMissionItem[]): Waypoint[] {
  const wps: Waypoint[] = [];
  let pendingSpeed = 0;
  // Iterate in seq order so DO_CHANGE_SPEED applied before a WP attaches to
  // that WP and not the previous one.
  const sorted = [...items].sort((a, b) => a.seq - b.seq);
  for (const item of sorted) {
    if (item.cmd === 178) {
      pendingSpeed = item.p2;
      continue;
    }
    // The HOME item (seq=0) and the various DO_* / NAV_TAKEOFF / NAV_RTL
    // items don't become Waypoints in the UI. Only the nav-WP family does.
    if ((item.cmd === 16 || item.cmd === 18 || item.cmd === 19 || item.cmd === 82) && item.seq > 0) {
      const wtype: Waypoint['type'] =
        item.cmd === 18 ? 'loiter_turns' : item.cmd === 19 ? 'loiter_time' : item.cmd === 82 ? 'spline' : 'wp';
      wps.push({
        lat: item.lat,
        lon: item.lon,
        alt: item.alt,
        drop: false,
        delay: item.cmd === 16 ? item.p1 : 0,
        speed: pendingSpeed,
        type: wtype,
        loiter_param: item.cmd === 18 || item.cmd === 19 ? item.p1 : 0,
      });
      pendingSpeed = 0;
    } else if (item.cmd === 181 && wps.length > 0) {
      // DO_SET_RELAY immediately after a WP → backend marks that WP's
      // drop=true on download to round-trip the upload-side attachment.
      wps[wps.length - 1].drop = true;
    }
  }
  return wps;
}
