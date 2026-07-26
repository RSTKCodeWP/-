import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock stores and i18n before import
vi.mock('./stores.svelte', () => ({
  app: {
    audioMuted: false,
    voiceEnabled: false,
    drone: { mode: '', alt_rel: 0, wp: 0, connected: false, armed: false },
  },
}));

vi.mock('./i18n.svelte', () => ({
  i18nState: { locale: 'en' },
  t: (key: string) => {
    const map: Record<string, string> = {
      'audio.modeSwitch': 'Mode: {mode}',
      'audio.waypoint': 'Waypoint {n} reached',
      'audio.meters': '{n} meters',
    };
    return map[key] ?? key;
  },
}));

import { app } from './stores.svelte';
import { beep, speak, checkAlerts } from './audio';

let oscillatorStarted: number[];
let oscillatorStopped: number[];
let utterances: SpeechSynthesisUtterance[];

beforeEach(() => {
  oscillatorStarted = [];
  oscillatorStopped = [];
  utterances = [];

  app.audioMuted = false;
  app.voiceEnabled = false;
  app.drone.mode = '';
  app.drone.alt_rel = 0;
  app.drone.wp = 0;

  const mockOsc = {
    connect: vi.fn(),
    frequency: { value: 0 },
    start: (t: number) => oscillatorStarted.push(t),
    stop: (t: number) => oscillatorStopped.push(t),
  };
  const mockGain = {
    connect: vi.fn(),
    gain: { value: 0 },
  };

  vi.stubGlobal(
    'AudioContext',
    class {
      currentTime = 0;
      destination = {};
      createOscillator() {
        return { ...mockOsc };
      }
      createGain() {
        return { ...mockGain };
      }
    },
  );

  vi.stubGlobal('speechSynthesis', {
    pending: false,
    cancel: vi.fn(),
    speak: vi.fn((u: SpeechSynthesisUtterance) => utterances.push(u)),
  });

  vi.stubGlobal(
    'SpeechSynthesisUtterance',
    class {
      text: string;
      lang = '';
      rate = 1;
      volume = 1;
      constructor(text: string) {
        this.text = text;
      }
    },
  );

  // Reset audio module's internal state by cycling through a "disarmed, disconnected" state
  checkAlerts(false, false, -1, 0);
});

describe('beep', () => {
  it('creates oscillator when not muted', () => {
    beep(880, 200, 1);
    expect(oscillatorStarted.length).toBe(1);
  });

  it('creates multiple oscillators for count > 1', () => {
    beep(880, 200, 3, 100);
    expect(oscillatorStarted.length).toBe(3);
  });

  it('does not beep when muted', () => {
    app.audioMuted = true;
    beep(880, 200, 1);
    expect(oscillatorStarted.length).toBe(0);
  });
});

describe('speak', () => {
  it('does nothing when voice is disabled', () => {
    app.voiceEnabled = false;
    speak('test');
    expect(speechSynthesis.speak).not.toHaveBeenCalled();
  });

  it('speaks when voice is enabled and speechSynthesis available', () => {
    app.voiceEnabled = true;
    // speak() checks 'speechSynthesis' in window, so it must be a property of global window
    (globalThis as any).window = globalThis;
    speak('Armed');
    expect(speechSynthesis.speak).toHaveBeenCalledTimes(1);
  });

  it('cancels pending speech before new utterance', () => {
    app.voiceEnabled = true;
    (speechSynthesis as any).pending = true;
    (globalThis as any).window = globalThis;
    speak('Mode change');
    expect(speechSynthesis.cancel).toHaveBeenCalled();
    expect(speechSynthesis.speak).toHaveBeenCalledTimes(1);
  });
});

describe('checkAlerts — arming', () => {
  it('beeps on arm transition', () => {
    checkAlerts(true, false, -1, 0);
    oscillatorStarted.length = 0;
    checkAlerts(true, true, -1, 0);
    // Armed beep: 880Hz, 200ms, count=2
    expect(oscillatorStarted.length).toBe(2);
  });

  it('beeps on disarm transition', () => {
    checkAlerts(true, true, -1, 0);
    oscillatorStarted.length = 0;
    checkAlerts(true, false, -1, 0);
    // Disarm beep: 440Hz, 300ms, count=1
    expect(oscillatorStarted.length).toBe(1);
  });
});

describe('checkAlerts — connection loss', () => {
  it('beeps when connection lost', () => {
    checkAlerts(true, false, -1, 0);
    oscillatorStarted.length = 0;
    checkAlerts(false, false, -1, 0);
    // Connection lost: 200Hz, 1000ms, count=3
    expect(oscillatorStarted.length).toBe(3);
  });
});

describe('checkAlerts — battery warnings', () => {
  it('warns at 29% battery when armed', () => {
    checkAlerts(true, true, 50, 0);
    oscillatorStarted.length = 0;
    checkAlerts(true, true, 29, 0);
    // Battery 30% warning: 400Hz, 400ms, count=2
    expect(oscillatorStarted.length).toBe(2);
  });

  it('warns at 19% battery', () => {
    // Reset battery state by going to high battery
    checkAlerts(true, true, 50, 0);
    oscillatorStarted.length = 0;
    checkAlerts(true, true, 19, 0);
    // Battery 20% warning: 300Hz, 500ms, count=3
    expect(oscillatorStarted.length).toBe(3);
  });

  it('does not warn when battery is above 30%', () => {
    checkAlerts(true, true, 50, 0);
    oscillatorStarted.length = 0;
    checkAlerts(true, true, 45, 0);
    expect(oscillatorStarted.length).toBe(0);
  });

  it('resets battery warning level when battery above 30', () => {
    checkAlerts(true, true, 29, 0);
    // Go above 30
    checkAlerts(true, true, 35, 0);
    oscillatorStarted.length = 0;
    // Drop below 30 again should re-trigger
    checkAlerts(true, true, 29, 0);
    expect(oscillatorStarted.length).toBeGreaterThan(0);
  });
});

describe('checkAlerts — mode change', () => {
  it('beeps on RTL mode switch', () => {
    app.drone.mode = 'Stabilize';
    checkAlerts(true, true, 50, 0);
    oscillatorStarted.length = 0;
    app.drone.mode = 'RTL';
    checkAlerts(true, true, 50, 0);
    // RTL mode beep: 440Hz, 300ms, count=2
    expect(oscillatorStarted.length).toBe(2);
  });

  it('no beep on non-RTL mode switch', () => {
    app.drone.mode = 'Stabilize';
    checkAlerts(true, true, 50, 0);
    oscillatorStarted.length = 0;
    app.drone.mode = 'Loiter';
    checkAlerts(true, true, 50, 0);
    expect(oscillatorStarted.length).toBe(0);
  });
});
