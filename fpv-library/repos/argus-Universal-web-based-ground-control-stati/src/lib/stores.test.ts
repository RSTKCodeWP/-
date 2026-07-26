import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  app,
  updateState,
  isPlane,
  setWsConnected,
  addEvent,
  clearEvents,
  addWaypoint,
  deleteWaypoint,
  clearWaypoints,
  undo,
  generateCircle,
  addToast,
  dismissToast,
  showConfirm,
  resolveConfirm,
  confirmState,
  showSlide,
  completeSlide,
  cancelSlide,
  slideState,
  loadDownloadedMission,
} from './stores.svelte';

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

describe('updateState', () => {
  beforeEach(() => {
    app.activeTransport = 'none';
  });

  it('merges partial state', () => {
    updateState({ connected: true, roll: 15.5 } as any);
    expect(app.drone.connected).toBe(true);
    expect(app.drone.roll).toBe(15.5);
  });

  it('preserves unchanged fields', () => {
    app.drone = { ...app.drone, voltage: 12.0 } as any;
    updateState({ roll: 5 } as any);
    expect(app.drone.voltage).toBe(12.0);
  });

  it('rejects updates when serial transport is active', () => {
    // WebSerial owns drone fields; stale WS state must not race.
    app.drone = { ...app.drone, roll: 1.0, voltage: 11.1 } as any;
    app.activeTransport = 'serial';
    updateState({ roll: 999, voltage: 99.9 } as any);
    expect(app.drone.roll).toBe(1.0);
    expect(app.drone.voltage).toBe(11.1);
  });

  it('allows updates when ws transport is active', () => {
    app.activeTransport = 'ws';
    updateState({ roll: 42 } as any);
    expect(app.drone.roll).toBe(42);
  });

  it('releases ws lock when backend reports disconnected', () => {
    app.activeTransport = 'ws';
    updateState({ connected: false } as any);
    expect(app.activeTransport).toBe('none');
  });

  it('does NOT release lock on transient state without connected field', () => {
    app.activeTransport = 'ws';
    updateState({ roll: 10 } as any);
    expect(app.activeTransport).toBe('ws');
  });
});

describe('isPlane', () => {
  it('returns false for copter (vtype_raw=2)', () => {
    app.drone = { ...app.drone, vtype_raw: 2 } as any;
    expect(isPlane()).toBe(false);
  });

  it('returns true for plane (vtype_raw=1)', () => {
    app.drone = { ...app.drone, vtype_raw: 1 } as any;
    expect(isPlane()).toBe(true);
  });

  it('returns true for VTOL types', () => {
    for (const vt of [19, 20, 21, 22, 23, 24, 25]) {
      app.drone = { ...app.drone, vtype_raw: vt } as any;
      expect(isPlane()).toBe(true);
    }
  });
});

describe('setWsConnected', () => {
  it('updates wsConnected', () => {
    setWsConnected(true);
    expect(app.wsConnected).toBe(true);
    setWsConnected(false);
    expect(app.wsConnected).toBe(false);
  });
});

describe('events', () => {
  it('addEvent pushes event', () => {
    addEvent({ type: 'event', time: '12:00', text: 'test', event_type: 'info' });
    expect(app.events.length).toBe(1);
  });

  it('trims at 200', () => {
    for (let i = 0; i < 210; i++) {
      addEvent({ type: 'event', time: '12:00', text: `e${i}`, event_type: '' });
    }
    expect(app.events.length).toBeLessThanOrEqual(200);
  });

  it('clearEvents empties', () => {
    addEvent({ type: 'event', time: '12:00', text: 'test', event_type: '' });
    clearEvents();
    expect(app.events.length).toBe(0);
  });
});

describe('waypoints + undo', () => {
  it('addWaypoint appends and saves undo', () => {
    addWaypoint({ lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 });
    expect(app.waypoints.length).toBe(1);
    expect(app.undoStack.length).toBe(1);
  });

  it('deleteWaypoint removes by index', () => {
    addWaypoint({ lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 });
    addWaypoint({ lat: 31, lon: 121, alt: 60, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 });
    deleteWaypoint(0);
    expect(app.waypoints.length).toBe(1);
    expect(app.waypoints[0].lat).toBe(31);
  });

  it('clearWaypoints empties', () => {
    addWaypoint({ lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 });
    clearWaypoints();
    expect(app.waypoints.length).toBe(0);
  });

  it('undo restores previous state', () => {
    addWaypoint({ lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 });
    addWaypoint({ lat: 31, lon: 121, alt: 60, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 });
    undo();
    expect(app.waypoints.length).toBe(1);
  });

  it('undo on empty stack does nothing', () => {
    app.undoStack = [];
    app.waypoints = [{ lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 }];
    undo();
    expect(app.waypoints.length).toBe(1);
  });
});

describe('generateCircle', () => {
  it('generates correct number of points', () => {
    generateCircle(30.0, 120.0, 100, 8, 50);
    expect(app.waypoints.length).toBe(8);
  });

  it('all points have correct altitude', () => {
    generateCircle(30.0, 120.0, 100, 4, 80);
    for (const wp of app.waypoints) {
      expect(wp.alt).toBe(80);
    }
  });

  it('points are near center', () => {
    generateCircle(30.0, 120.0, 50, 4, 50);
    for (const wp of app.waypoints) {
      expect(Math.abs(wp.lat - 30.0)).toBeLessThan(0.01);
      expect(Math.abs(wp.lon - 120.0)).toBeLessThan(0.01);
    }
  });
});

describe('toasts', () => {
  it('addToast adds a toast', () => {
    addToast('hello', 'info');
    expect(app.toasts.length).toBe(1);
    expect(app.toasts[0].text).toBe('hello');
  });

  it('duplicate toast increments count', () => {
    addToast('dup', 'info');
    addToast('dup', 'info');
    expect(app.toasts.length).toBe(1);
    expect(app.toasts[0].count).toBe(2);
  });

  it('caps at 5 toasts', () => {
    for (let i = 0; i < 8; i++) {
      addToast(`toast${i}`, 'info');
    }
    expect(app.toasts.length).toBeLessThanOrEqual(5);
  });

  it('dismissToast removes by id', () => {
    addToast('to-dismiss', 'warn');
    const id = app.toasts[0].id;
    dismissToast(id);
    expect(app.toasts.length).toBe(0);
  });
});

describe('confirm dialog', () => {
  it('showConfirm sets state', () => {
    showConfirm('Are you sure?', true);
    expect(confirmState.visible).toBe(true);
    expect(confirmState.message).toBe('Are you sure?');
    expect(confirmState.danger).toBe(true);
  });

  it('resolveConfirm hides and resolves', async () => {
    const promise = showConfirm('test?');
    confirmState.shownAt = Date.now() - 400; // past the input-arming window
    resolveConfirm(true);
    const result = await promise;
    expect(result).toBe(true);
    expect(confirmState.visible).toBe(false);
  });

  it('affirmative inside the arming window is ignored; decline passes', async () => {
    // A dialog appearing under an in-flight Enter/click (scheduler-due
    // confirm) must not be accepted by that same keystroke.
    const promise = showConfirm('dangerous?', true);
    resolveConfirm(true);
    expect(confirmState.visible).toBe(true); // still open — accept ignored
    resolveConfirm(false);
    expect(await promise).toBe(false);
    expect(confirmState.visible).toBe(false);
  });

  it('a second showConfirm declines the first instead of hanging it', async () => {
    const first = showConfirm('first?');
    const second = showConfirm('second?');
    expect(await first).toBe(false); // resolved, not leaked
    confirmState.shownAt = Date.now() - 400;
    resolveConfirm(true);
    expect(await second).toBe(true);
  });
});

describe('slide confirm', () => {
  it('showSlide sets state', () => {
    const fn = vi.fn();
    showSlide('Slide to confirm', 'red', fn);
    expect(slideState.visible).toBe(true);
    expect(slideState.text).toBe('Slide to confirm');
  });

  it('completeSlide calls callback', () => {
    const fn = vi.fn();
    showSlide('test', 'orange', fn);
    completeSlide();
    expect(fn).toHaveBeenCalled();
    expect(slideState.visible).toBe(false);
  });

  it('cancelSlide hides without callback', () => {
    const fn = vi.fn();
    showSlide('test', 'orange', fn);
    cancelSlide();
    expect(fn).not.toHaveBeenCalled();
    expect(slideState.visible).toBe(false);
  });
});

describe('loadDownloadedMission', () => {
  it('replaces waypoints', () => {
    addWaypoint({ lat: 1, lon: 1, alt: 1, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 });
    loadDownloadedMission([
      { lat: 30, lon: 120, alt: 50, drop: true, delay: 5, speed: 3, type: 'wp', loiter_param: 0 },
      { lat: 31, lon: 121, alt: 60, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 },
    ]);
    expect(app.waypoints.length).toBe(2);
    expect(app.waypoints[0].drop).toBe(true);
  });

  it('creates undo point', () => {
    loadDownloadedMission([
      { lat: 30, lon: 120, alt: 50, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 },
    ]);
    expect(app.undoStack.length).toBeGreaterThan(0);
  });
});
