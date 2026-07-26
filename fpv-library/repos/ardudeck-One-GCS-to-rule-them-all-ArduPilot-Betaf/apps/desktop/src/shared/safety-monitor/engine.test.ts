import { describe, it, expect, beforeEach } from 'vitest';
import { SafetyMonitorEngine } from './engine';
import {
  DEFAULT_PROFILE,
  ABORT_ACTION,
  type MonitorFrame,
  type MonitorContext,
  type PidSample,
} from './types';

const PID_AVAILABLE: MonitorContext = {
  imaxRoll: 0.5,
  imaxPitch: 0.5,
  ahrsTrimX: 0,
  ahrsTrimY: 0,
  pidStreamingAvailable: true,
};

function pid(over: Partial<PidSample> = {}): PidSample {
  return { desired: 0, achieved: 0, p: 0, i: 0, d: 0, ff: 0, ...over };
}

function frame(over: Partial<MonitorFrame> & { t: number }): MonitorFrame {
  return {
    armed: true,
    landedState: 'on-ground',
    roll: 0,
    pitch: 0,
    rollSpeed: 0,
    pitchSpeed: 0,
    throttle: 0,
    climb: 0,
    servoOutputs: [1100, 1100, 1100, 1100],
    ...over,
  };
}

/** Feed the same frame repeatedly past the debounce window. */
function hold(engine: SafetyMonitorEngine, base: Partial<MonitorFrame>, fromT: number, durationMs: number, stepMs = 50) {
  let last = engine.getState();
  for (let t = fromT; t <= fromT + durationMs; t += stepMs) {
    last = engine.update(frame({ ...base, t }));
  }
  return last;
}

function signal(state: ReturnType<SafetyMonitorEngine['getState']>, id: string) {
  const s = state.signals.find((x) => x.id === id);
  if (!s) throw new Error(`no signal ${id}`);
  return s;
}

describe('SafetyMonitorEngine', () => {
  let engine: SafetyMonitorEngine;
  beforeEach(() => {
    engine = new SafetyMonitorEngine(DEFAULT_PROFILE, PID_AVAILABLE);
  });

  it('reports NOMINAL when level, idle and on the ground', () => {
    const s = hold(engine, { throttle: 0, roll: 0.5, pitch: 0.5 }, 0, 600);
    expect(s.overall).toBe('nominal');
    expect(s.action).toBeNull();
    expect(signal(s, 'restingAttitude').severity).toBe('nominal');
  });

  it('does not escalate a transient blip before the debounce window', () => {
    // A single frame in the caution band must not flip the signal immediately.
    const s = engine.update(frame({ t: 0, pitch: 7 }));
    expect(signal(s, 'restingAttitude').severity).toBe('nominal');
  });

  it('escalates resting attitude to caution only after it is sustained', () => {
    const s = hold(engine, { pitch: 7 }, 0, DEFAULT_PROFILE.debounceMs + 100);
    expect(signal(s, 'restingAttitude').severity).toBe('caution');
    // A tilted rest alone is not fatal: overall is caution, not danger.
    expect(s.overall).toBe('caution');
  });

  it('flags a large tilt that AHRS_TRIM does not account for', () => {
    engine.setContext({ ...PID_AVAILABLE, ahrsTrimX: 0, ahrsTrimY: 0 });
    const s = hold(engine, { pitch: 12 }, 0, DEFAULT_PROFILE.debounceMs + 100);
    const rest = signal(s, 'restingAttitude');
    expect(rest.severity).toBe('danger');
    expect(rest.detail).toMatch(/trim/i);
  });

  it('marks integrator and controller-fighting unavailable when PID is not streaming', () => {
    engine.setContext({ pidStreamingAvailable: false });
    const s = engine.update(frame({ t: 0 }));
    expect(signal(s, 'integratorLoad').available).toBe(false);
    expect(signal(s, 'controllerFighting').available).toBe(false);
    // Other signals keep working.
    expect(signal(s, 'restingAttitude').available).toBe(true);
  });

  it('computes integrator load as a percent of IMAX', () => {
    const s = hold(engine, { pidPitch: pid({ i: 0.45 }), pidRoll: pid({ i: 0.1 }) }, 0, 400);
    // 0.45 / 0.5 = 90%
    expect(s.integrator.pitch).toBeCloseTo(90, 0);
    expect(signal(s, 'integratorLoad').severity).toBe('danger');
  });

  it('stays NOMINAL through a healthy takeoff (throttle up WITH positive climb)', () => {
    let s = engine.getState();
    for (let t = 0; t <= 1500; t += 50) {
      const throttle = Math.min(70, 20 + t / 25);
      const climb = t > 400 ? 1.8 : 0.0; // lifts cleanly once spooled
      const landedState = t > 600 ? 'takeoff' : 'on-ground';
      s = engine.update(
        frame({ t, throttle, climb, landedState, pitch: 1.0, roll: 1.0, pidPitch: pid({ i: 0.05, desired: 0.1, achieved: 0.1, p: 0.1 }) }),
      );
    }
    expect(s.overall).not.toBe('danger');
  });

  it('escalates to DANGER on the tip-over precondition pattern before attitude blows past 30deg', () => {
    // Spool-up while resting non-level: integrator winds toward IMAX, throttle
    // climbs with zero climb rate, and the net rate command opposes the demand.
    let s = engine.getState();
    let maxAttitudeAtDanger = 0;
    let dangerT: number | null = null;
    for (let t = 0; t <= 1200; t += 50) {
      const throttle = Math.min(65, 20 + t / 20); // rising spool-up
      const pitch = 6 + t / 200; // resting offset, slowly growing, still < 30
      // integrator winds up against the ground toward IMAX
      const i = Math.min(0.49, 0.1 + t / 2500);
      // wound-up I beats P: net command opposes the demanded rate
      const desired = 0.5; // demanding nose-down recovery
      const achieved = -0.1;
      const pidPitch = pid({ desired, achieved, i: -0.45, p: 0.1, d: 0, ff: 0 });
      s = engine.update(frame({ t, throttle, climb: 0.0, pitch, pidPitch }));
      if (s.overall === 'danger' && dangerT === null) {
        dangerT = t;
        maxAttitudeAtDanger = pitch;
      }
    }
    expect(dangerT).not.toBeNull();
    expect(maxAttitudeAtDanger).toBeLessThan(30);
    expect(s.action).toBe(ABORT_ACTION);
  });

  it('latches DANGER and only a manual clear resets it', () => {
    // Trip danger.
    hold(
      engine,
      {
        throttle: 60,
        climb: 0,
        pitch: 12,
        pidPitch: pid({ desired: 0.5, achieved: -0.1, i: -0.45, p: 0.1 }),
      },
      0,
      600,
    );
    expect(engine.getState().overall).toBe('danger');
    expect(engine.getState().dangerLatchedAt).not.toBeNull();

    // Conditions return to benign - still latched.
    const benign = hold(engine, { throttle: 0, climb: 0, pitch: 0 }, 1000, 600);
    expect(benign.overall).toBe('danger');

    engine.clearLatch(2000);
    const cleared = engine.update(frame({ t: 2050, throttle: 0, pitch: 0 }));
    expect(cleared.overall).toBe('nominal');
    expect(cleared.dangerLatchedAt).toBeNull();
  });

  it('never raises tip-over DANGER while in the air', () => {
    // Same nasty values, but airborne: the tip-over logic must not apply.
    const s = hold(
      engine,
      {
        landedState: 'in-air',
        throttle: 60,
        climb: 0,
        pitch: 12,
        pidPitch: pid({ desired: 0.5, achieved: -0.1, i: -0.45, p: 0.1 }),
      },
      0,
      800,
    );
    expect(s.overall).not.toBe('danger');
    expect(s.tipoverArmed).toBe(false);
  });

  it('never raises tip-over DANGER while disarmed', () => {
    const s = hold(
      engine,
      {
        armed: false,
        throttle: 60,
        climb: 0,
        pitch: 12,
        pidPitch: pid({ desired: 0.5, achieved: -0.1, i: -0.45, p: 0.1 }),
      },
      0,
      800,
    );
    expect(s.overall).not.toBe('danger');
  });

  it('records a crash STATUSTEXT as a timeline event', () => {
    engine.update(frame({ t: 0 }));
    engine.recordStatusText(2, 'Crash: Disarming', 100);
    const evt = engine.getState().events.find((e) => e.kind === 'crash');
    expect(evt).toBeDefined();
    expect(evt?.text).toMatch(/crash/i);
  });

  it('flags a large on-ground motor spread', () => {
    const s = hold(engine, { servoOutputs: [1100, 1100, 1350, 1100] }, 0, 400);
    expect(signal(s, 'motorSpread').value).toBeCloseTo(250, 0);
    expect(signal(s, 'motorSpread').severity).toBe('danger');
  });
});
