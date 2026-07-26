import { describe, it, expect } from 'vitest';
import {
  buildMissionItems,
  validateMissionWaypoints,
  missionItemsToWaypoints,
  buildFenceItems,
  validateFencePolygon,
} from './missionUpload';
import type { RawMissionItem } from './missionUpload';
import type { Waypoint } from './types';

const baseWp = (over: Partial<Waypoint> = {}): Waypoint => ({
  lat: 30,
  lon: 120,
  alt: 50,
  drop: false,
  delay: 0,
  speed: 0,
  type: 'wp',
  loiter_param: 0,
  ...over,
});

describe('buildMissionItems', () => {
  it('produces HOME + TAKEOFF + WP + RTL for a single waypoint', () => {
    const items = buildMissionItems([baseWp()], 30);
    expect(items.length).toBe(4);
    expect(items[0].command).toBe(16); // HOME (NAV_WAYPOINT, lat=lon=alt=0)
    expect(items[0].current).toBe(1);
    expect(items[0].x).toBe(0);
    expect(items[1].command).toBe(22); // TAKEOFF
    expect(items[1].z).toBe(30); // takeoff alt
    expect(items[2].command).toBe(16); // WP
    expect(items[2].x).toBe(300000000);
    expect(items[2].y).toBe(1200000000);
    expect(items[3].command).toBe(20); // RTL
  });

  it('inserts DO_CHANGE_SPEED before nav waypoint when speed > 0', () => {
    const items = buildMissionItems([baseWp({ speed: 12 })], 30);
    // [HOME, TAKEOFF, CHANGE_SPEED, NAV_WP, RTL]
    expect(items.length).toBe(5);
    expect(items[2].command).toBe(178); // DO_CHANGE_SPEED
    expect(items[2].p1).toBe(1); // groundspeed
    expect(items[2].p2).toBe(12);
    expect(items[3].command).toBe(16);
  });

  it('uses NAV_SPLINE_WAYPOINT cmd=82 for spline type', () => {
    const items = buildMissionItems([baseWp({ type: 'spline', delay: 5 })], 30);
    expect(items[2].command).toBe(82);
    expect(items[2].p1).toBe(5); // delay (spline takes delay as p1)
  });

  it('uses LOITER_TURNS cmd=18 with loiter_param as p1', () => {
    const items = buildMissionItems([baseWp({ type: 'loiter_turns', loiter_param: 7 })], 30);
    expect(items[2].command).toBe(18);
    expect(items[2].p1).toBe(7);
  });

  it('uses LOITER_TIME cmd=19 with loiter_param as p1', () => {
    const items = buildMissionItems([baseWp({ type: 'loiter_time', loiter_param: 15 })], 30);
    expect(items[2].command).toBe(19);
    expect(items[2].p1).toBe(15);
  });

  it('inserts DO_SET_RELAY (181) after WP when drop=true', () => {
    const items = buildMissionItems([baseWp({ drop: true })], 30);
    // [HOME, TAKEOFF, WP, RELAY, RTL]
    expect(items.length).toBe(5);
    expect(items[3].command).toBe(181);
  });

  it('preserves WP order across multiple waypoints', () => {
    const items = buildMissionItems([baseWp({ lat: 30, lon: 120 }), baseWp({ lat: 31, lon: 121 })], 30);
    // HOME + TAKEOFF + WP1 + WP2 + RTL
    expect(items.length).toBe(5);
    expect(items[2].x).toBe(300000000);
    expect(items[3].x).toBe(310000000);
  });

  it('NAV cmds use frame=3 (REL_ALT) and DO_* / RTL use frame=2 (MISSION)', () => {
    // Backend rule (send_mission_item_int): frame=3 only for cmd in
    // (16, 18, 19, 21, 22, 82). RTL (20) is NOT in that set — it gets frame=2.
    const items = buildMissionItems([baseWp({ speed: 5, drop: true })], 30);
    // HOME(16)=3, TAKEOFF(22)=3, CHG_SPEED(178)=2, WP(16)=3, RELAY(181)=2, RTL(20)=2
    expect(items[0].frame).toBe(3);
    expect(items[1].frame).toBe(3);
    expect(items[2].frame).toBe(2); // DO_CHANGE_SPEED
    expect(items[3].frame).toBe(3);
    expect(items[4].frame).toBe(2); // DO_SET_RELAY
    expect(items[5].frame).toBe(2); // RTL
  });

  it('seq is contiguous from 0 to N-1', () => {
    const items = buildMissionItems([baseWp({ speed: 3 }), baseWp({ drop: true })], 30);
    items.forEach((item, idx) => {
      expect(item.seq).toBe(idx);
    });
  });

  it('only seq 0 has current=1', () => {
    const items = buildMissionItems([baseWp(), baseWp({ lat: 31 })], 30);
    expect(items[0].current).toBe(1);
    items.slice(1).forEach((item) => expect(item.current).toBe(0));
  });

  it('handles attachments in the documented order', () => {
    const items = buildMissionItems(
      [
        baseWp({
          cmd_servo: { num: 5, pwm: 1800 },
          cmd_roi: { lat: 32, lon: 122, alt: 100 },
          cmd_cam_trig: { dist: 50 },
          cmd_yaw: { deg: 90, dir: 1 },
        }),
      ],
      30,
    );
    // [HOME, TAKEOFF, WP, SERVO, ROI, CAM_TRIG, YAW, RTL]
    expect(items.length).toBe(8);
    expect(items[3].command).toBe(183); // DO_SET_SERVO
    expect(items[3].p1).toBe(5);
    expect(items[3].p2).toBe(1800);
    expect(items[4].command).toBe(201); // DO_SET_ROI
    expect(items[4].x).toBe(320000000);
    expect(items[5].command).toBe(206); // DO_SET_CAM_TRIGG_DIST
    expect(items[6].command).toBe(115); // CONDITION_YAW
    expect(items[6].p1).toBe(90);
  });
});

describe('validateMissionWaypoints', () => {
  it('rejects empty waypoint list', () => {
    const r = validateMissionWaypoints([]);
    expect(r.ok).toBe(false);
  });

  it('rejects > 500 waypoints', () => {
    const wps = Array.from({ length: 501 }, () => baseWp({ lat: 30, lon: 120 }));
    const r = validateMissionWaypoints(wps);
    expect(r.ok).toBe(false);
  });

  it('rejects coordinates very close to 0/0', () => {
    const r = validateMissionWaypoints([baseWp({ lat: 0.0001, lon: 120 })]);
    expect(r.ok).toBe(false);
  });

  it('rejects out-of-range latitude', () => {
    const r = validateMissionWaypoints([baseWp({ lat: 91, lon: 120 })]);
    expect(r.ok).toBe(false);
  });

  it('rejects out-of-range altitude', () => {
    const r = validateMissionWaypoints([baseWp({ alt: -1000 })]);
    expect(r.ok).toBe(false);
  });

  it('accepts a normal waypoint', () => {
    const r = validateMissionWaypoints([baseWp()]);
    expect(r.ok).toBe(true);
  });
});

const rawItem = (over: Partial<RawMissionItem> = {}): RawMissionItem => ({
  seq: 0,
  cmd: 16,
  lat: 0,
  lon: 0,
  alt: 0,
  p1: 0,
  p2: 0,
  p3: 0,
  p4: 0,
  frame: 3,
  current: 0,
  autocontinue: 1,
  ...over,
});

describe('missionItemsToWaypoints', () => {
  it('round-trips buildMissionItems output back to the same Waypoint list', () => {
    const input: Waypoint[] = [
      baseWp({ lat: 30, lon: 120 }),
      baseWp({ lat: 31, lon: 121, type: 'loiter_turns', loiter_param: 5 }),
    ];
    const built = buildMissionItems(input, 30);
    // Lift built items into the RawMissionItem shape: backend stores x/y as
    // int32 *1e7, but missionItemsToWaypoints expects lat/lon already in degrees.
    const raw: RawMissionItem[] = built.map((m) => ({
      seq: m.seq,
      cmd: m.command,
      lat: m.x / 1e7,
      lon: m.y / 1e7,
      alt: m.z,
      p1: m.p1,
      p2: m.p2,
      p3: m.p3,
      p4: m.p4,
      frame: m.frame,
      current: m.current,
      autocontinue: m.autocontinue,
    }));
    const out = missionItemsToWaypoints(raw);
    expect(out.length).toBe(2);
    expect(out[0].lat).toBeCloseTo(30, 5);
    expect(out[0].type).toBe('wp');
    expect(out[1].lat).toBeCloseTo(31, 5);
    expect(out[1].type).toBe('loiter_turns');
    expect(out[1].loiter_param).toBe(5);
  });

  it('skips HOME (seq=0 cmd=16) and TAKEOFF (cmd=22) and RTL (cmd=20)', () => {
    const raw: RawMissionItem[] = [
      rawItem({ seq: 0, cmd: 16 }), // HOME — skipped
      rawItem({ seq: 1, cmd: 22, alt: 30 }), // TAKEOFF — skipped (cmd not in nav set)
      rawItem({ seq: 2, cmd: 16, lat: 30, lon: 120, alt: 50 }), // WP
      rawItem({ seq: 3, cmd: 20 }), // RTL — skipped (cmd not in nav set)
    ];
    const out = missionItemsToWaypoints(raw);
    expect(out.length).toBe(1);
    expect(out[0].lat).toBeCloseTo(30, 5);
  });

  it('attaches DO_CHANGE_SPEED to the next nav waypoint, not previous', () => {
    const raw: RawMissionItem[] = [
      rawItem({ seq: 0, cmd: 16 }), // HOME
      rawItem({ seq: 1, cmd: 22, alt: 30 }), // TAKEOFF
      rawItem({ seq: 2, cmd: 16, lat: 30, lon: 120, alt: 50 }), // WP1 (no speed)
      rawItem({ seq: 3, cmd: 178, p1: 1, p2: 12 }), // DO_CHANGE_SPEED 12
      rawItem({ seq: 4, cmd: 16, lat: 31, lon: 121, alt: 50 }), // WP2 (speed=12)
    ];
    const out = missionItemsToWaypoints(raw);
    expect(out.length).toBe(2);
    expect(out[0].speed).toBe(0);
    expect(out[1].speed).toBe(12);
  });

  it('coalesces DO_SET_RELAY (181) immediately after a WP onto wp.drop=true', () => {
    const raw: RawMissionItem[] = [
      rawItem({ seq: 0, cmd: 16 }),
      rawItem({ seq: 1, cmd: 22, alt: 30 }),
      rawItem({ seq: 2, cmd: 16, lat: 30, lon: 120 }),
      rawItem({ seq: 3, cmd: 181 }), // DO_SET_RELAY → drop on previous WP
      rawItem({ seq: 4, cmd: 20 }),
    ];
    const out = missionItemsToWaypoints(raw);
    expect(out.length).toBe(1);
    expect(out[0].drop).toBe(true);
  });

  it('handles out-of-order seq values by sorting first', () => {
    const raw: RawMissionItem[] = [
      rawItem({ seq: 2, cmd: 16, lat: 30, lon: 120 }),
      rawItem({ seq: 0, cmd: 16 }),
      rawItem({ seq: 1, cmd: 22 }),
    ];
    const out = missionItemsToWaypoints(raw);
    expect(out.length).toBe(1);
  });

  it('returns empty list for an empty input', () => {
    expect(missionItemsToWaypoints([])).toEqual([]);
  });
});

describe('buildFenceItems', () => {
  it('produces N items with cmd=5001, frame=3, p1=N, autocontinue=1', () => {
    const poly = [
      { lat: 30, lon: 120 },
      { lat: 31, lon: 120 },
      { lat: 31, lon: 121 },
    ];
    const items = buildFenceItems(poly);
    expect(items.length).toBe(3);
    items.forEach((item, i) => {
      expect(item.command).toBe(5001);
      expect(item.frame).toBe(3);
      expect(item.p1).toBe(3); // total vertex count
      expect(item.autocontinue).toBe(1);
      expect(item.current).toBe(0); // first vertex is NOT current=1 for fence
      expect(item.seq).toBe(i);
    });
    expect(items[0].x).toBe(300000000);
    expect(items[2].y).toBe(1210000000);
  });

  it('returns empty for empty polygon', () => {
    expect(buildFenceItems([])).toEqual([]);
  });
});

describe('validateFencePolygon', () => {
  it('rejects < 3 vertices', () => {
    expect(validateFencePolygon([]).ok).toBe(false);
    expect(
      validateFencePolygon([
        { lat: 30, lon: 120 },
        { lat: 31, lon: 121 },
      ]).ok,
    ).toBe(false);
  });

  it('rejects > 200 vertices', () => {
    const big = Array.from({ length: 201 }, (_, i) => ({ lat: 30 + i * 0.001, lon: 120 }));
    expect(validateFencePolygon(big).ok).toBe(false);
  });

  it('rejects out-of-range coordinates', () => {
    expect(
      validateFencePolygon([
        { lat: 91, lon: 120 },
        { lat: 31, lon: 121 },
        { lat: 32, lon: 122 },
      ]).ok,
    ).toBe(false);
  });

  it('accepts a typical 3-vertex polygon', () => {
    expect(
      validateFencePolygon([
        { lat: 30, lon: 120 },
        { lat: 31, lon: 121 },
        { lat: 30.5, lon: 121.5 },
      ]).ok,
    ).toBe(true);
  });
});
