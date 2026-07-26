/**
 * Performance benchmark tests for frontend modules.
 *
 * These tests set generous thresholds (2-3x expected) so they pass reliably
 * but catch major regressions (10x slower would fail).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { app, updateState, addEvent, addWaypoint, deleteWaypoint, generateCircle, addToast } from './stores.svelte';
import { parseFrames, encodeFrame } from './mavlink/codec';
import { t, i18nState } from './i18n.svelte';

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
  vi.stubGlobal('requestAnimationFrame', (cb: () => void) => cb());
  app.waypoints = [];
  app.undoStack = [];
  app.events = [];
  app.toasts = [];
  app.drone = { ...app.drone, vtype_raw: 0, mode: '', wp: 0, alt_rel: 0 } as any;
});

describe('Store update performance', () => {
  it('10000 updateState calls complete in < 500ms', () => {
    const start = performance.now();
    for (let i = 0; i < 10000; i++) {
      updateState({
        roll: i % 360,
        pitch: i % 90,
        yaw: i % 360,
        lat: 30.0 + i * 0.0001,
        lon: 120.0 + i * 0.0001,
        alt_rel: i,
        gs: i % 30,
        voltage: 11.0 + (i % 10) * 0.1,
      } as any);
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(500);
  });

  it('10000 partial updates (single field) in < 200ms', () => {
    const start = performance.now();
    for (let i = 0; i < 10000; i++) {
      updateState({ roll: i % 360 } as any);
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(200);
  });
});

describe('MAVLink codec throughput', () => {
  it('encode 5000 frames in < 1s', () => {
    const payload = new Uint8Array([0, 0, 0, 0, 6, 8, 0, 0, 3]);

    const start = performance.now();
    for (let i = 0; i < 5000; i++) {
      encodeFrame(0, payload, 255, 190, i & 0xff);
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(1000);
  });

  it('decode 5000 frames in < 1s', () => {
    const payload = new Uint8Array([0, 0, 0, 0, 6, 8, 0, 0, 3]);
    const frame = encodeFrame(0, payload, 255, 190, 0);

    const start = performance.now();
    for (let i = 0; i < 5000; i++) {
      parseFrames(frame);
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(1000);
  });

  it('roundtrip encode+decode 5000 frames in < 2s', () => {
    const payload = new Uint8Array([0, 0, 0, 0, 6, 8, 0, 0, 3]);

    const start = performance.now();
    for (let i = 0; i < 5000; i++) {
      const encoded = encodeFrame(0, payload, 255, 190, i & 0xff);
      const { frames } = parseFrames(encoded);
      expect(frames.length).toBe(1);
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(2000);
  });

  it('parse buffer with 100 concatenated frames in < 100ms', () => {
    const payload = new Uint8Array([0, 0, 0, 0, 6, 8, 0, 0, 3]);
    const single = encodeFrame(0, payload, 1, 1, 0);
    const bigBuf = new Uint8Array(single.length * 100);
    for (let i = 0; i < 100; i++) {
      bigBuf.set(single, i * single.length);
    }

    const start = performance.now();
    for (let i = 0; i < 50; i++) {
      const { frames } = parseFrames(bigBuf);
      expect(frames.length).toBe(100);
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(100);
  });
});

describe('Waypoint operations performance', () => {
  it('add 1000 waypoints in < 2000ms', () => {
    // Each addWaypoint triggers pushUndo (deep clone + localStorage write)
    const start = performance.now();
    for (let i = 0; i < 1000; i++) {
      addWaypoint({
        lat: 30 + i * 0.001,
        lon: 120 + i * 0.001,
        alt: 50,
        drop: false,
        delay: 0,
        speed: 0,
        type: 'wp',
        loiter_param: 0,
      });
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(2000);
    expect(app.waypoints.length).toBe(1000);
  });

  it('delete 1000 waypoints in < 2000ms', () => {
    // Pre-fill without timing
    app.undoStack = [];
    for (let i = 0; i < 1000; i++) {
      app.waypoints.push({
        lat: 30 + i * 0.001,
        lon: 120 + i * 0.001,
        alt: 50,
        drop: false,
        delay: 0,
        speed: 0,
        type: 'wp',
        loiter_param: 0,
      });
    }

    // Each deleteWaypoint triggers pushUndo (deep clone + localStorage write)
    const start = performance.now();
    for (let i = 999; i >= 0; i--) {
      deleteWaypoint(i);
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(2000);
    expect(app.waypoints.length).toBe(0);
  });
});

describe('generateCircle performance', () => {
  it('generate circle with 72 points in < 10ms', () => {
    const start = performance.now();
    generateCircle(30.0, 120.0, 500, 72, 100);
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(10);
    expect(app.waypoints.length).toBe(72);
  });

  it('generate 10 circles of 36 points each in < 50ms', () => {
    const start = performance.now();
    for (let i = 0; i < 10; i++) {
      app.waypoints = [];
      app.undoStack = [];
      generateCircle(30.0 + i * 0.01, 120.0 + i * 0.01, 200, 36, 80);
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(50);
  });
});

describe('Event buffer trimming performance', () => {
  it('add 1000 events with trimming in < 100ms', () => {
    const start = performance.now();
    for (let i = 0; i < 1000; i++) {
      addEvent({
        type: 'event',
        time: '12:00:00',
        text: `Event number ${i} with some description`,
        event_type: 'info',
      });
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(100);
    // Buffer should have trimmed (max 200, trims to 100)
    expect(app.events.length).toBeLessThanOrEqual(200);
  });

  it('repeated trim cycles do not degrade in < 100ms', () => {
    // Fill to near capacity first
    for (let i = 0; i < 190; i++) {
      app.events.push({ type: 'event', time: '12:00', text: `pre-${i}`, event_type: '' });
    }

    const start = performance.now();
    for (let i = 0; i < 1000; i++) {
      addEvent({
        type: 'event',
        time: '12:00:00',
        text: `New event ${i}`,
        event_type: 'test',
      });
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(100);
  });
});

describe('Toast deduplication performance', () => {
  it('1000 addToast calls (duplicate text) in < 200ms', () => {
    const start = performance.now();
    for (let i = 0; i < 1000; i++) {
      addToast('Repeated toast message', 'info', 999999);
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(200);
    // All duplicates should be merged into 1
    expect(app.toasts.length).toBe(1);
    expect(app.toasts[0].count).toBe(1000);
  });

  it('1000 addToast calls (unique text) in < 200ms', () => {
    const start = performance.now();
    for (let i = 0; i < 1000; i++) {
      addToast(`Toast message #${i}`, 'info', 999999);
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(200);
    // Max 5 toasts kept (excess are shifted out)
    expect(app.toasts.length).toBeLessThanOrEqual(5);
  });
});

describe('i18n lookup performance', () => {
  it('10000 t() calls in < 100ms', () => {
    i18nState.locale = 'zh';
    const keys = [
      'app.name',
      'app.subtitle',
      'tab.fly',
      'tab.plan',
      'conn.connect',
      'conn.disconnect',
      'status.armed',
      'ctrl.arm',
      'ctrl.disarm',
      'phase.flying',
    ];

    const start = performance.now();
    for (let i = 0; i < 10000; i++) {
      t(keys[i % keys.length]);
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(100);
  });

  it('10000 t() calls with missing keys in < 100ms', () => {
    i18nState.locale = 'zh';

    const start = performance.now();
    for (let i = 0; i < 10000; i++) {
      t(`nonexistent.key.${i % 50}`);
    }
    const elapsed = performance.now() - start;
    expect(elapsed).toBeLessThan(100);
  });
});
