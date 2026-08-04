import { describe, it, expect } from 'vitest';
import {
  RC_CHANNEL_COUNT,
  RC_MID,
  applyExpo,
  defaultChannelMap,
  defaultMapping,
  detectMovedControl,
  devicesToChannels,
  looksLikeTransmitter,
  shapeAxis,
  toPwm,
  type ChannelMap,
} from './pseudo-tx';

const dev = (axes: number[], buttons: boolean[] = []) => ({ axes, buttons });

describe('pseudo transmitter shaping', () => {
  it('maps stick ends to the standard RC limits', () => {
    expect(toPwm(0)).toBe(1500);
    expect(toPwm(1)).toBe(2000);
    expect(toPwm(-1)).toBe(1000);
  });

  it('zeroes the deadband without leaving a step at its edge', () => {
    const m: ChannelMap = { ...defaultChannelMap(), deadband: 0.1 };
    expect(shapeAxis(0.05, m)).toBe(0);
    // Just outside the band must emerge from ~0, not jump to 0.1.
    expect(Math.abs(shapeAxis(0.101, m))).toBeLessThan(0.01);
    // Full deflection still reaches the end.
    expect(shapeAxis(1, m)).toBeCloseTo(1, 5);
  });

  it('softens mid-stick with expo but leaves the ends alone', () => {
    const lin: ChannelMap = { ...defaultChannelMap(), deadband: 0, expo: 0 };
    const exp: ChannelMap = { ...defaultChannelMap(), deadband: 0, expo: 0.8 };
    expect(Math.abs(shapeAxis(0.3, exp))).toBeLessThan(Math.abs(shapeAxis(0.3, lin)));
    expect(shapeAxis(1, exp)).toBeCloseTo(shapeAxis(1, lin), 5);
    expect(applyExpo(0, 0.8)).toBe(0);
  });

  it('reverses a channel', () => {
    const m: ChannelMap = { ...defaultChannelMap(), deadband: 0, reverse: true };
    expect(shapeAxis(0.5, m)).toBeCloseTo(-0.5, 5);
  });
});

describe('channel mapping', () => {
  it('always produces a full 16-channel frame', () => {
    const ch = devicesToChannels(dev([0, 0, 0, 0]), defaultMapping());
    expect(ch).toHaveLength(RC_CHANNEL_COUNT);
  });

  it('holds unmapped channels at MID, never at zero', () => {
    // A flight controller reads a channel at zero as a dead receiver, so an unassigned
    // channel has to look neutral rather than broken.
    const ch = devicesToChannels(dev([1, -1, 0, 0]), defaultMapping());
    for (let i = 4; i < RC_CHANNEL_COUNT; i++) expect(ch[i]).toBe(RC_MID);
    expect(ch.every((v) => v >= 1000)).toBe(true);
  });

  it('maps AETR onto the first four axes by default', () => {
    const ch = devicesToChannels(dev([1, -1, 0.5, 0]), defaultMapping());
    expect(ch[0]).toBe(2000);
    expect(ch[1]).toBe(1000);
    expect(ch[2]).toBeGreaterThan(1600);
    expect(ch[3]).toBe(1500);
  });

  it('treats a switch as two hard positions, not a softened gimbal', () => {
    const map = defaultMapping();
    map[4] = { ...defaultChannelMap(), source: { kind: 'button', index: 2 }, deadband: 0.4, expo: 1 };
    expect(devicesToChannels(dev([], [false, false, true]), map)[4]).toBe(2000);
    expect(devicesToChannels(dev([], [false, false, false]), map)[4]).toBe(1000);
  });

  it('supports a three-position switch as a button pair', () => {
    const map = defaultMapping();
    map[5] = { ...defaultChannelMap(), source: { kind: 'button3', low: 0, high: 1 } };
    expect(devicesToChannels(dev([], [true, false]), map)[5]).toBe(1000);
    expect(devicesToChannels(dev([], [false, false]), map)[5]).toBe(1500);
    expect(devicesToChannels(dev([], [false, true]), map)[5]).toBe(2000);
  });

  it('ignores axes that do not exist on the device', () => {
    const map = defaultMapping();
    map[0] = { ...defaultChannelMap(), source: { kind: 'axis', index: 9 } };
    expect(devicesToChannels(dev([0.5]), map)[0]).toBe(RC_MID);
  });
});

describe('learn-by-wiggle assignment', () => {
  it('picks the axis that actually moved', () => {
    const base = dev([0, 0, 0, 0]);
    expect(detectMovedControl(base, dev([0, 0, 0.9, 0]))).toEqual({ kind: 'axis', index: 2 });
  });

  it('ignores noise below the threshold', () => {
    const base = dev([0, 0, 0, 0]);
    expect(detectMovedControl(base, dev([0.05, -0.04, 0.02, 0]))).toBeNull();
  });

  it('falls back to a button when no axis moved', () => {
    const base = dev([0, 0], [false, false, false]);
    expect(detectMovedControl(base, dev([0, 0], [false, false, true]))).toEqual({
      kind: 'button',
      index: 2,
    });
  });

  it('prefers the largest movement when several drift', () => {
    const base = dev([0, 0, 0]);
    expect(detectMovedControl(base, dev([0.4, 0.95, 0.5]))).toEqual({ kind: 'axis', index: 1 });
  });
});

describe('device identification', () => {
  it('recognises handsets by name', () => {
    expect(looksLikeTransmitter('RadioMaster TX16S Joystick', 4)).toBe(true);
    expect(looksLikeTransmitter('OpenTX Taranis', 4)).toBe(true);
    expect(looksLikeTransmitter('EdgeTX Joystick', 4)).toBe(true);
  });

  it('accepts an unknown device with a transmitter-like number of axes', () => {
    expect(looksLikeTransmitter('Unknown HID', 8)).toBe(true);
  });

  it('does not mistake a console pad for a transmitter', () => {
    expect(looksLikeTransmitter('Xbox Wireless Controller', 4)).toBe(false);
  });
});
