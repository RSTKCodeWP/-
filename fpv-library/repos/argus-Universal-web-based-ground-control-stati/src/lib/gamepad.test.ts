import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock dependencies before importing module
vi.mock('./transport', () => ({ dispatch: vi.fn() }));
vi.mock('./stores.svelte', () => ({
  app: { drone: { connected: false, armed: false } },
}));

import { gamepad, loadGamepadMap, saveGamepadMap, startGamepad, stopGamepad } from './gamepad.svelte';
import { dispatch } from './transport';
import { app } from './stores.svelte';

function makeStorage(): Storage {
  const store = new Map<string, string>();
  return {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => {
      store.set(k, v);
    },
    removeItem: (k: string) => {
      store.delete(k);
    },
    clear: () => store.clear(),
    get length() {
      return store.size;
    },
    key: (i: number) => [...store.keys()][i] ?? null,
  };
}

beforeEach(() => {
  vi.stubGlobal('localStorage', makeStorage());
  vi.stubGlobal('window', {
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  });
  vi.stubGlobal('requestAnimationFrame', vi.fn());
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  vi.stubGlobal('navigator', { getGamepads: vi.fn(() => []) });
  // Reset gamepad state
  gamepad.connected = false;
  gamepad.name = '';
  gamepad.axes = [0, 0, 0, 0];
  gamepad.buttons = [];
  gamepad.enabled = false;
  gamepad.deadzone = 0.08;
  gamepad.channelMap = {
    roll: 0,
    pitch: 1,
    throttle: 3,
    yaw: 2,
    invertRoll: false,
    invertPitch: true,
    invertThrottle: true,
    invertYaw: false,
  };
});

describe('gamepad default state', () => {
  it('has sensible defaults', () => {
    expect(gamepad.connected).toBe(false);
    expect(gamepad.enabled).toBe(false);
    expect(gamepad.deadzone).toBe(0.08);
    expect(gamepad.axes).toEqual([0, 0, 0, 0]);
  });

  it('has default channel map', () => {
    expect(gamepad.channelMap.roll).toBe(0);
    expect(gamepad.channelMap.pitch).toBe(1);
    expect(gamepad.channelMap.yaw).toBe(2);
    expect(gamepad.channelMap.throttle).toBe(3);
    expect(gamepad.channelMap.invertPitch).toBe(true);
    expect(gamepad.channelMap.invertThrottle).toBe(true);
    expect(gamepad.channelMap.invertRoll).toBe(false);
    expect(gamepad.channelMap.invertYaw).toBe(false);
  });
});

describe('loadGamepadMap', () => {
  it('loads saved channel map from localStorage', () => {
    const custom = {
      roll: 1,
      pitch: 0,
      throttle: 2,
      yaw: 3,
      invertRoll: true,
      invertPitch: false,
      invertThrottle: false,
      invertYaw: true,
    };
    localStorage.setItem('argus_gamepad_map', JSON.stringify(custom));
    loadGamepadMap();
    expect(gamepad.channelMap.roll).toBe(1);
    expect(gamepad.channelMap.pitch).toBe(0);
    expect(gamepad.channelMap.invertRoll).toBe(true);
    expect(gamepad.channelMap.invertYaw).toBe(true);
  });

  it('keeps defaults when localStorage is empty', () => {
    loadGamepadMap();
    expect(gamepad.channelMap.roll).toBe(0);
    expect(gamepad.channelMap.pitch).toBe(1);
  });

  it('handles corrupted JSON gracefully', () => {
    localStorage.setItem('argus_gamepad_map', '{broken');
    loadGamepadMap();
    // Should not crash; defaults remain
    expect(gamepad.channelMap.roll).toBe(0);
  });

  it('merges partial saved config with defaults', () => {
    localStorage.setItem('argus_gamepad_map', JSON.stringify({ roll: 3 }));
    loadGamepadMap();
    expect(gamepad.channelMap.roll).toBe(3);
    expect(gamepad.channelMap.pitch).toBe(1); // default preserved
  });

  it('ignores saved config without roll key', () => {
    localStorage.setItem('argus_gamepad_map', JSON.stringify({ customField: 'test' }));
    loadGamepadMap();
    expect(gamepad.channelMap.roll).toBe(0); // default preserved
  });
});

describe('saveGamepadMap', () => {
  it('persists current channel map to localStorage', () => {
    gamepad.channelMap.roll = 2;
    gamepad.channelMap.invertYaw = true;
    saveGamepadMap();
    const saved = JSON.parse(localStorage.getItem('argus_gamepad_map')!);
    expect(saved.roll).toBe(2);
    expect(saved.invertYaw).toBe(true);
  });

  it('roundtrips through save and load', () => {
    gamepad.channelMap = {
      roll: 3,
      pitch: 2,
      throttle: 1,
      yaw: 0,
      invertRoll: true,
      invertPitch: false,
      invertThrottle: false,
      invertYaw: true,
    };
    saveGamepadMap();
    // Reset to defaults
    gamepad.channelMap = {
      roll: 0,
      pitch: 1,
      throttle: 3,
      yaw: 2,
      invertRoll: false,
      invertPitch: true,
      invertThrottle: true,
      invertYaw: false,
    };
    loadGamepadMap();
    expect(gamepad.channelMap.roll).toBe(3);
    expect(gamepad.channelMap.yaw).toBe(0);
    expect(gamepad.channelMap.invertRoll).toBe(true);
  });
});

describe('startGamepad / stopGamepad', () => {
  it('startGamepad enables and registers listeners', () => {
    startGamepad();
    expect(gamepad.enabled).toBe(true);
    expect(window.addEventListener).toHaveBeenCalledWith('gamepadconnected', expect.any(Function));
    expect(window.addEventListener).toHaveBeenCalledWith('gamepaddisconnected', expect.any(Function));
  });

  it('stopGamepad disables and removes listeners', () => {
    startGamepad();
    stopGamepad();
    expect(gamepad.enabled).toBe(false);
    expect(gamepad.connected).toBe(false);
    expect(window.removeEventListener).toHaveBeenCalledWith('gamepadconnected', expect.any(Function));
    expect(window.removeEventListener).toHaveBeenCalledWith('gamepaddisconnected', expect.any(Function));
  });
});

describe('onConnect / onDisconnect handlers', () => {
  it('onConnect sets connected state and name', () => {
    startGamepad();
    const addEventCalls = (window.addEventListener as ReturnType<typeof vi.fn>).mock.calls;
    const connectHandler = addEventCalls.find((c: unknown[]) => c[0] === 'gamepadconnected')![1] as (
      e: GamepadEvent,
    ) => void;
    connectHandler({
      gamepad: { index: 0, id: 'Xbox Wireless Controller (Long Name Truncated Here)' },
    } as unknown as GamepadEvent);

    expect(gamepad.connected).toBe(true);
    expect(gamepad.name.length).toBeLessThanOrEqual(40);
    expect(gamepad.name).toBe('Xbox Wireless Controller (Long Name Trun');
  });

  it('onDisconnect resets all gamepad state', () => {
    startGamepad();
    const addEventCalls = (window.addEventListener as ReturnType<typeof vi.fn>).mock.calls;
    const connectHandler = addEventCalls.find((c: unknown[]) => c[0] === 'gamepadconnected')![1] as (
      e: GamepadEvent,
    ) => void;
    const disconnectHandler = addEventCalls.find((c: unknown[]) => c[0] === 'gamepaddisconnected')![1] as () => void;

    // Connect first
    connectHandler({ gamepad: { index: 0, id: 'Test Controller' } } as unknown as GamepadEvent);
    expect(gamepad.connected).toBe(true);

    // Then disconnect
    disconnectHandler();
    expect(gamepad.connected).toBe(false);
    expect(gamepad.name).toBe('');
    expect(gamepad.axes).toEqual([0, 0, 0, 0]);
  });
});

describe('poll() gamepad reading and RC override', () => {
  let pollFn: () => void;

  beforeEach(() => {
    (dispatch as ReturnType<typeof vi.fn>).mockClear();
    // Capture the poll callback passed to requestAnimationFrame
    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn((cb: () => void) => {
        pollFn = cb;
        return 1;
      }),
    );
    vi.stubGlobal('performance', { now: vi.fn(() => 1000) });
  });

  afterEach(() => {
    stopGamepad();
  });

  it('reads axes from gamepad and updates state', () => {
    const mockGamepad = {
      index: 0,
      axes: [0.5, -0.3, 0.8, -0.9],
      buttons: [{ pressed: true }, { pressed: false }],
    };
    vi.stubGlobal('navigator', { getGamepads: vi.fn(() => [mockGamepad]) });

    gamepad.enabled = true;
    gamepad.connected = true;

    // Simulate poll being called (need to set gpIndex via onConnect)
    // Start gamepad and invoke the connect handler
    startGamepad();
    const addEventCalls = (window.addEventListener as ReturnType<typeof vi.fn>).mock.calls;
    const connectHandler = addEventCalls.find((c: unknown[]) => c[0] === 'gamepadconnected')![1] as (
      e: GamepadEvent,
    ) => void;
    connectHandler({ gamepad: { index: 0, id: 'Test Controller' } } as unknown as GamepadEvent);

    // Now call poll via requestAnimationFrame callback
    expect(pollFn).toBeDefined();
    pollFn();

    // Axes should be updated (with deadzone applied)
    expect(gamepad.axes[0]).toBeGreaterThan(0);
    expect(gamepad.axes[1]).toBeLessThan(0);
    expect(gamepad.buttons).toEqual([true, false]);
  });

  it('does not send rc_override when drone is not connected', () => {
    const mockGamepad = {
      index: 0,
      axes: [0.5, -0.3, 0.8, -0.9],
      buttons: [],
    };
    vi.stubGlobal('navigator', { getGamepads: vi.fn(() => [mockGamepad]) });
    vi.stubGlobal('performance', { now: vi.fn(() => 6000) }); // past rate limit

    (app as any).drone.connected = false;
    (app as any).drone.armed = false;

    startGamepad();
    const addEventCalls = (window.addEventListener as ReturnType<typeof vi.fn>).mock.calls;
    const connectHandler = addEventCalls.find((c: unknown[]) => c[0] === 'gamepadconnected')![1] as (
      e: GamepadEvent,
    ) => void;
    connectHandler({ gamepad: { index: 0, id: 'Test Controller' } } as unknown as GamepadEvent);

    pollFn();
    expect(dispatch as ReturnType<typeof vi.fn>).not.toHaveBeenCalled();
  });

  it('does not send rc_override when drone is not armed', () => {
    const mockGamepad = {
      index: 0,
      axes: [0.5, -0.3, 0.8, -0.9],
      buttons: [],
    };
    vi.stubGlobal('navigator', { getGamepads: vi.fn(() => [mockGamepad]) });
    vi.stubGlobal('performance', { now: vi.fn(() => 10000) });

    (app as any).drone.connected = true;
    (app as any).drone.armed = false;

    startGamepad();
    const addEventCalls = (window.addEventListener as ReturnType<typeof vi.fn>).mock.calls;
    const connectHandler = addEventCalls.find((c: unknown[]) => c[0] === 'gamepadconnected')![1] as (
      e: GamepadEvent,
    ) => void;
    connectHandler({ gamepad: { index: 0, id: 'Test Controller' } } as unknown as GamepadEvent);

    pollFn();
    expect(dispatch as ReturnType<typeof vi.fn>).not.toHaveBeenCalled();
  });

  it('sends rc_override when drone is connected and armed', () => {
    const mockGamepad = {
      index: 0,
      axes: [0.5, -0.3, 0.8, -0.9],
      buttons: [],
    };
    vi.stubGlobal('navigator', { getGamepads: vi.fn(() => [mockGamepad]) });
    vi.stubGlobal('performance', { now: vi.fn(() => 20000) }); // well past any prior lastSend

    (app as any).drone.connected = true;
    (app as any).drone.armed = true;

    startGamepad();
    const addEventCalls = (window.addEventListener as ReturnType<typeof vi.fn>).mock.calls;
    const connectHandler = addEventCalls.find((c: unknown[]) => c[0] === 'gamepadconnected')![1] as (
      e: GamepadEvent,
    ) => void;
    connectHandler({ gamepad: { index: 0, id: 'Test Controller' } } as unknown as GamepadEvent);

    pollFn();
    expect(dispatch as ReturnType<typeof vi.fn>).toHaveBeenCalledWith('rc_override', undefined, {
      channels: expect.any(Array),
    });
    const channels = (dispatch as ReturnType<typeof vi.fn>).mock.calls[0][2].channels;
    expect(channels).toHaveLength(8);
    // Last 4 channels should be 0 (unused)
    expect(channels[4]).toBe(0);
    expect(channels[5]).toBe(0);
    expect(channels[6]).toBe(0);
    expect(channels[7]).toBe(0);
  });

  it('applies channel inversion correctly', () => {
    const mockGamepad = {
      index: 0,
      axes: [1.0, 1.0, 1.0, 1.0], // all axes at max
      buttons: [],
    };
    vi.stubGlobal('navigator', { getGamepads: vi.fn(() => [mockGamepad]) });
    vi.stubGlobal('performance', { now: vi.fn(() => 30000) });

    (app as any).drone.connected = true;
    (app as any).drone.armed = true;

    // Default: invertRoll=false, invertPitch=true, invertThrottle=true, invertYaw=false
    // roll axis=0, pitch axis=1, yaw axis=2, throttle axis=3
    startGamepad();
    const addEventCalls = (window.addEventListener as ReturnType<typeof vi.fn>).mock.calls;
    const connectHandler = addEventCalls.find((c: unknown[]) => c[0] === 'gamepadconnected')![1] as (
      e: GamepadEvent,
    ) => void;
    connectHandler({ gamepad: { index: 0, id: 'Test Controller' } } as unknown as GamepadEvent);

    pollFn();
    const channels = (dispatch as ReturnType<typeof vi.fn>).mock.calls[0][2].channels;
    // roll (axis 0, not inverted): 1500 + 500 = 2000
    expect(channels[0]).toBe(2000);
    // pitch (axis 1, inverted): 1500 + (-500) = 1000
    expect(channels[1]).toBe(1000);
    // throttle (axis 3, inverted): 1500 + (-500) = 1000
    expect(channels[2]).toBe(1000);
    // yaw (axis 2, not inverted): 1500 + 500 = 2000
    expect(channels[3]).toBe(2000);
  });

  it('rate-limits RC override to 50ms intervals', () => {
    const mockGamepad = {
      index: 0,
      axes: [0.5, 0.5, 0.5, 0.5],
      buttons: [],
    };
    vi.stubGlobal('navigator', { getGamepads: vi.fn(() => [mockGamepad]) });

    (app as any).drone.connected = true;
    (app as any).drone.armed = true;

    let currentTime = 40000;
    vi.stubGlobal('performance', { now: vi.fn(() => currentTime) });

    startGamepad();
    const addEventCalls = (window.addEventListener as ReturnType<typeof vi.fn>).mock.calls;
    const connectHandler = addEventCalls.find((c: unknown[]) => c[0] === 'gamepadconnected')![1] as (
      e: GamepadEvent,
    ) => void;
    connectHandler({ gamepad: { index: 0, id: 'Test Controller' } } as unknown as GamepadEvent);

    // First poll sends
    pollFn();
    expect(dispatch as ReturnType<typeof vi.fn>).toHaveBeenCalledTimes(1);

    // Second poll 20ms later does NOT send (under 50ms threshold)
    currentTime = 40020;
    pollFn();
    expect(dispatch as ReturnType<typeof vi.fn>).toHaveBeenCalledTimes(1);

    // Third poll 60ms after first DOES send
    currentTime = 40060;
    pollFn();
    expect(dispatch as ReturnType<typeof vi.fn>).toHaveBeenCalledTimes(2);
  });

  it('does nothing when gamepad index is invalid', () => {
    vi.stubGlobal('navigator', { getGamepads: vi.fn(() => [null]) });
    vi.stubGlobal('performance', { now: vi.fn(() => 50000) });

    (app as any).drone.connected = true;
    (app as any).drone.armed = true;

    startGamepad();
    // Don't fire onConnect, so gpIndex remains -1
    pollFn();
    expect(dispatch as ReturnType<typeof vi.fn>).not.toHaveBeenCalled();
    // Axes should stay at default
    expect(gamepad.axes).toEqual([0, 0, 0, 0]);
  });

  it('applies deadzone correctly', () => {
    // Values below deadzone (0.08) should become 0
    const mockGamepad = {
      index: 0,
      axes: [0.05, -0.05, 0.0, 0.5],
      buttons: [],
    };
    vi.stubGlobal('navigator', { getGamepads: vi.fn(() => [mockGamepad]) });
    vi.stubGlobal('performance', { now: vi.fn(() => 60000) });

    (app as any).drone.connected = true;
    (app as any).drone.armed = true;

    startGamepad();
    const addEventCalls = (window.addEventListener as ReturnType<typeof vi.fn>).mock.calls;
    const connectHandler = addEventCalls.find((c: unknown[]) => c[0] === 'gamepadconnected')![1] as (
      e: GamepadEvent,
    ) => void;
    connectHandler({ gamepad: { index: 0, id: 'Test Controller' } } as unknown as GamepadEvent);

    pollFn();
    // Axes below deadzone should be 0
    expect(gamepad.axes[0]).toBe(0);
    expect(gamepad.axes[1]).toBe(0);
    expect(gamepad.axes[2]).toBe(0);
    // Axis 3 (0.5) is above deadzone
    expect(gamepad.axes[3]).toBeGreaterThan(0);
  });
});
