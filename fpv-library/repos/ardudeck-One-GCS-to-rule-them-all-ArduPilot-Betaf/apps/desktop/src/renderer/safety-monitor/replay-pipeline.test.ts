/**
 * End-to-end acceptance test: raw MAVLink frames → renderer decode → engine.
 *
 * Unlike engine.test.ts (which feeds pre-built frames), this drives the actual
 * decode path used for both live links and .tlog replay, so it also proves the
 * unit conversions (rad→deg, PID axis routing, throttle %) and the
 * EXTENDED_SYS_STATE landed-state handling are correct.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { getMessageInfo } from '@ardudeck/mavlink-ts/registry';
import {
  beginReplay,
  endReplay,
  feedReplayPacket,
  evaluateReplayAt,
  setContext,
} from './source';
import { useSafetyMonitorStore } from '../stores/safety-monitor-store';

function payload(msgid: number, msg: Record<string, unknown>): number[] {
  const info = getMessageInfo(msgid);
  if (!info) throw new Error(`no message info for ${msgid}`);
  return Array.from(info.serialize(msg));
}

const DEG2RAD = Math.PI / 180;

function feed(msgid: number, msg: Record<string, unknown>, t: number) {
  feedReplayPacket({ msgid, sysid: 1, compid: 1, payload: payload(msgid, msg) }, t);
}

function heartbeat(armed: boolean, t: number) {
  feed(0, { customMode: 0, type: 2, autopilot: 3, baseMode: armed ? 0x80 : 0, systemStatus: 4, mavlinkVersion: 3 }, t);
}
function extState(landed: number, t: number) {
  feed(245, { vtolState: 0, landedState: landed }, t);
}
function attitude(pitchDeg: number, t: number) {
  feed(30, { timeBootMs: t, roll: 0, pitch: pitchDeg * DEG2RAD, yaw: 0, rollspeed: 0, pitchspeed: 0, yawspeed: 0 }, t);
}
function vfrHud(throttle: number, climb: number, alt: number, t: number) {
  feed(74, { airspeed: 0, groundspeed: 0, alt, climb, heading: 0, throttle }, t);
}
function pidPitch(desired: number, achieved: number, i: number, p: number, t: number) {
  feed(194, { axis: 2, desired, achieved, ff: 0, p, i, d: 0, srate: 0, pdmod: 0 }, t);
}

describe('replay pipeline (raw MAVLink → engine)', () => {
  beforeEach(() => {
    beginReplay();
    setContext({ pidStreamingAvailable: true, imaxRoll: 0.5, imaxPitch: 0.5, ahrsTrimX: 0, ahrsTrimY: 0 });
  });

  it('escalates to DANGER on a tip-over spool-up before pitch passes 30deg', () => {
    let dangerT: number | null = null;
    let pitchAtDanger = 0;
    for (let t = 0; t <= 1500; t += 50) {
      const pitchDeg = 6 + t / 150; // resting offset, growing, stays < 30
      const throttle = Math.min(65, 20 + t / 20); // spooling up
      heartbeat(true, t);
      extState(1 /* ON_GROUND */, t);
      attitude(pitchDeg, t);
      vfrHud(throttle, 0.0 /* not lifting */, 0.0, t);
      // wound-up I term opposing the demanded recovery
      pidPitch(0.5 /* desired */, -0.1 /* achieved */, -0.45 /* i */, 0.1 /* p */, t);
      evaluateReplayAt(t);

      const overall = useSafetyMonitorStore.getState().monitor.overall;
      if (overall === 'danger' && dangerT === null) {
        dangerT = t;
        pitchAtDanger = pitchDeg;
      }
    }
    endReplay();
    expect(dangerT).not.toBeNull();
    expect(pitchAtDanger).toBeLessThan(30);
  });

  it('stays out of DANGER through a clean takeoff (throttle up WITH climb)', () => {
    let sawDanger = false;
    for (let t = 0; t <= 1500; t += 50) {
      const throttle = Math.min(70, 20 + t / 25);
      const climb = t > 400 ? 1.8 : 0.0;
      heartbeat(true, t);
      extState(t > 600 ? 3 /* TAKEOFF */ : 1 /* ON_GROUND */, t);
      attitude(1.0, t);
      vfrHud(throttle, climb, climb > 0 ? (t - 400) / 100 : 0, t);
      pidPitch(0.1, 0.1, 0.05, 0.1, t); // healthy: small error, low integrator
      evaluateReplayAt(t);
      if (useSafetyMonitorStore.getState().monitor.overall === 'danger') sawDanger = true;
    }
    endReplay();
    expect(sawDanger).toBe(false);
  });
});
