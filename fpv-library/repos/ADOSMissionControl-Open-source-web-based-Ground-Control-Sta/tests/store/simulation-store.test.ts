import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Mock cesium before importing the store
vi.mock('cesium', () => {
  class JulianDate {
    static clone = vi.fn((d: any) => d ?? new JulianDate());
    static addSeconds = vi.fn((_d: any, _s: number, result: any) => result ?? new JulianDate());
    static secondsDifference = vi.fn(() => 0);
  }
  return { JulianDate, Viewer: vi.fn() };
});

import {
  useSimulationStore,
  bindSimViewer,
  unbindSimViewer,
  type SimViewerBridge,
} from '@/stores/simulation-store';

/**
 * A fake clock bridge whose elapsed advances on `tick()`. Lets the store's
 * clock-delegation be asserted without a CesiumJS viewer.
 */
function makeFakeBridge() {
  let elapsed = 0;
  let animate = false;
  let multiplier = 1;
  let alive = true;
  const viewer = {};

  const bridge: SimViewerBridge = {
    seekClock: (s) => { elapsed = s; },
    requestRender: vi.fn(),
    setAnimate: (a) => { animate = a; },
    setMultiplier: (m) => { multiplier = m; },
    setStopTime: vi.fn(),
    getElapsed: () => elapsed,
    getShouldAnimate: () => animate,
    isAlive: () => alive,
  };

  return {
    viewer,
    bridge,
    /** Advance the clock by `dt` seconds (only while animating). */
    tick: (dt: number) => { if (animate) elapsed += dt; },
    /** Force the clock's elapsed (e.g. simulate landing exactly at stop). */
    setElapsed: (s: number) => { elapsed = s; },
    /** Simulate CesiumJS CLAMPED auto-stop at the end of the timeline. */
    autoStopAtEnd: (total: number) => { elapsed = total; animate = false; },
    getAnimate: () => animate,
    getMultiplier: () => multiplier,
    getElapsed: () => elapsed,
    kill: () => { alive = false; },
  };
}

describe('simulation-store', () => {
  beforeEach(() => {
    vi.useRealTimers();
    unbindSimViewer();
    useSimulationStore.getState().reset();
  });

  afterEach(() => {
    unbindSimViewer();
  });

  it('initial state is stopped', () => {
    const state = useSimulationStore.getState();
    expect(state.playbackState).toBe('stopped');
    expect(state.playbackSpeed).toBe(1);
    expect(state.elapsed).toBe(0);
    expect(state.totalDuration).toBe(0);
    expect(state.cameraMode).toBe('orbit');
    expect(state.syncedPosition).toBeNull();
    expect(state.followHeadingLocked).toBe(true);
  });

  it('play() does not transition without a bound viewer', () => {
    // Without a Cesium viewer bound, play() early-returns
    useSimulationStore.getState().play();
    expect(useSimulationStore.getState().playbackState).toBe('stopped');
  });

  it('pause() transitions to paused', () => {
    useSimulationStore.getState().pause();
    expect(useSimulationStore.getState().playbackState).toBe('paused');
  });

  it('stop() transitions to stopped and resets elapsed', () => {
    // Simulate some elapsed time
    useSimulationStore.setState({ playbackState: 'playing', elapsed: 30 });
    useSimulationStore.getState().stop();

    const state = useSimulationStore.getState();
    expect(state.playbackState).toBe('stopped');
    expect(state.elapsed).toBe(0);
  });

  it('seek() clamps to valid range', () => {
    useSimulationStore.setState({ totalDuration: 100 });

    useSimulationStore.getState().seek(50);
    expect(useSimulationStore.getState().elapsed).toBe(50);

    // Clamps to max
    useSimulationStore.getState().seek(200);
    expect(useSimulationStore.getState().elapsed).toBe(100);

    // Clamps to min
    useSimulationStore.getState().seek(-10);
    expect(useSimulationStore.getState().elapsed).toBe(0);
  });

  it('setSpeed() updates playback speed', () => {
    useSimulationStore.getState().setSpeed(2);
    expect(useSimulationStore.getState().playbackSpeed).toBe(2);

    useSimulationStore.getState().setSpeed(0.5);
    expect(useSimulationStore.getState().playbackSpeed).toBe(0.5);
  });

  it('setCameraMode() updates camera mode', () => {
    useSimulationStore.getState().setCameraMode('follow');
    expect(useSimulationStore.getState().cameraMode).toBe('follow');

    useSimulationStore.getState().setCameraMode('orbit');
    expect(useSimulationStore.getState().cameraMode).toBe('orbit');
  });

  it('resetCameraView() bumps the camera view nonce', () => {
    // The nonce is monotonic (reset() deliberately leaves it untouched), so
    // assert relative increments rather than an absolute start value.
    const start = useSimulationStore.getState().cameraViewNonce;
    useSimulationStore.getState().resetCameraView();
    expect(useSimulationStore.getState().cameraViewNonce).toBe(start + 1);
    useSimulationStore.getState().resetCameraView();
    expect(useSimulationStore.getState().cameraViewNonce).toBe(start + 2);
  });

  it('setTotalDuration() updates total duration', () => {
    useSimulationStore.getState().setTotalDuration(300);
    expect(useSimulationStore.getState().totalDuration).toBe(300);
  });

  it('setTotalDuration() does not re-zero a non-zero elapsed', () => {
    // Mid-session: a non-zero elapsed must survive a duration change (a
    // re-time from a sampled-positions change should not silently rewind).
    useSimulationStore.setState({ totalDuration: 200, elapsed: 80 });
    useSimulationStore.getState().setTotalDuration(300);
    expect(useSimulationStore.getState().elapsed).toBe(80);
    expect(useSimulationStore.getState().totalDuration).toBe(300);
  });

  it('setTotalDuration() re-clamps an elapsed past the new shorter end', () => {
    useSimulationStore.setState({ totalDuration: 200, elapsed: 180 });
    useSimulationStore.getState().setTotalDuration(120);
    expect(useSimulationStore.getState().elapsed).toBe(120);
  });

  it('stepForward() advances by 1 second', () => {
    useSimulationStore.setState({ totalDuration: 100, elapsed: 10 });
    useSimulationStore.getState().stepForward();
    expect(useSimulationStore.getState().elapsed).toBe(11);
  });

  it('stepBack() retreats by 1 second', () => {
    useSimulationStore.setState({ totalDuration: 100, elapsed: 10 });
    useSimulationStore.getState().stepBack();
    expect(useSimulationStore.getState().elapsed).toBe(9);
  });

  it('stepForward() does not exceed total duration', () => {
    useSimulationStore.setState({ totalDuration: 10, elapsed: 10 });
    useSimulationStore.getState().stepForward();
    expect(useSimulationStore.getState().elapsed).toBe(10);
  });

  it('stepBack() does not go below zero', () => {
    useSimulationStore.setState({ totalDuration: 100, elapsed: 0 });
    useSimulationStore.getState().stepBack();
    expect(useSimulationStore.getState().elapsed).toBe(0);
  });

  it('syncPosition() stores synced position', () => {
    const pos = { lat: 12.97, lon: 77.59, altAgl: 50, heading: 180, speed: 5, waypointIndex: 2 };
    useSimulationStore.getState().syncPosition(pos);
    expect(useSimulationStore.getState().syncedPosition).toEqual(pos);
  });

  it('syncPosition() throttles high-frequency same-waypoint updates', () => {
    vi.useFakeTimers();
    vi.setSystemTime(1_000);

    const first = { lat: 12.97, lon: 77.59, altAgl: 50, heading: 180, speed: 5, waypointIndex: 2 };
    const second = { lat: 12.971, lon: 77.591, altAgl: 51, heading: 181, speed: 6, waypointIndex: 2 };

    useSimulationStore.getState().syncPosition(first);
    vi.setSystemTime(1_050);
    useSimulationStore.getState().syncPosition(second);
    expect(useSimulationStore.getState().syncedPosition).toEqual(first);

    vi.setSystemTime(1_101);
    useSimulationStore.getState().syncPosition(second);
    expect(useSimulationStore.getState().syncedPosition).toEqual(second);
  });

  it('syncPosition() allows immediate waypoint-index changes', () => {
    vi.useFakeTimers();
    vi.setSystemTime(2_000);

    const first = { lat: 12.97, lon: 77.59, altAgl: 50, heading: 180, speed: 5, waypointIndex: 2 };
    const second = { lat: 12.971, lon: 77.591, altAgl: 51, heading: 181, speed: 6, waypointIndex: 3 };

    useSimulationStore.getState().syncPosition(first);
    vi.setSystemTime(2_001);
    useSimulationStore.getState().syncPosition(second);
    expect(useSimulationStore.getState().syncedPosition).toEqual(second);
  });

  it('toggleFollowHeading() toggles the lock', () => {
    expect(useSimulationStore.getState().followHeadingLocked).toBe(true);
    useSimulationStore.getState().toggleFollowHeading();
    expect(useSimulationStore.getState().followHeadingLocked).toBe(false);
    useSimulationStore.getState().toggleFollowHeading();
    expect(useSimulationStore.getState().followHeadingLocked).toBe(true);
  });

  it('reset() restores all defaults', () => {
    useSimulationStore.setState({
      playbackState: 'playing',
      playbackSpeed: 4,
      elapsed: 55,
      totalDuration: 200,
      cameraMode: 'orbit',
      syncedPosition: { lat: 0, lon: 0, altAgl: 0, heading: 0, speed: 0, waypointIndex: 0 },
      followHeadingLocked: false,
    });

    useSimulationStore.getState().reset();

    const state = useSimulationStore.getState();
    expect(state.playbackState).toBe('stopped');
    expect(state.playbackSpeed).toBe(1);
    expect(state.elapsed).toBe(0);
    expect(state.totalDuration).toBe(0);
    expect(state.cameraMode).toBe('orbit');
    expect(state.syncedPosition).toBeNull();
    expect(state.followHeadingLocked).toBe(true);
  });

  // ── Playback semantics, driven through a fake clock bridge ───────────────

  describe('playback semantics (clock-backed)', () => {
    it('skip-to-start SEEKS to the start and keeps playing', () => {
      const fake = makeFakeBridge();
      bindSimViewer(fake.viewer, fake.bridge);
      useSimulationStore.setState({ totalDuration: 100 });
      useSimulationStore.getState().play();
      fake.tick(40);
      useSimulationStore.getState().syncFromClock();
      expect(useSimulationStore.getState().elapsed).toBe(40);

      useSimulationStore.getState().seekToStart();

      // Seeks to the start but stays in the playing state (does not halt).
      expect(useSimulationStore.getState().elapsed).toBe(0);
      expect(useSimulationStore.getState().playbackState).toBe('playing');
      expect(fake.getAnimate()).toBe(true);
      expect(fake.getElapsed()).toBe(0);
    });

    it('natural completion transitions to stopped (not paused)', () => {
      const fake = makeFakeBridge();
      bindSimViewer(fake.viewer, fake.bridge);
      useSimulationStore.setState({ totalDuration: 100 });
      useSimulationStore.getState().play();

      // CesiumJS CLAMPED clock halts at stopTime — simulate the auto-stop.
      fake.autoStopAtEnd(100);
      useSimulationStore.getState().syncFromClock();

      const state = useSimulationStore.getState();
      expect(state.playbackState).toBe('stopped');
      expect(state.elapsed).toBe(100);
    });

    it('a clock tick does not clobber a step taken while playing', () => {
      const fake = makeFakeBridge();
      bindSimViewer(fake.viewer, fake.bridge);
      useSimulationStore.setState({ totalDuration: 100 });
      useSimulationStore.getState().play();
      fake.tick(10);
      useSimulationStore.getState().syncFromClock();
      expect(useSimulationStore.getState().elapsed).toBe(10);

      // Step forward while still playing — must seek the authoritative clock.
      useSimulationStore.getState().stepForward();
      expect(useSimulationStore.getState().elapsed).toBe(11);
      expect(fake.getElapsed()).toBe(11);

      // The next clock tick resumes FROM the stepped position, not the old 10.
      fake.tick(0.5);
      useSimulationStore.getState().syncFromClock();
      expect(useSimulationStore.getState().elapsed).toBe(11.5);
    });

    it('resetPlayback() rewinds + stops but preserves camera and speed', () => {
      const fake = makeFakeBridge();
      bindSimViewer(fake.viewer, fake.bridge);
      useSimulationStore.setState({
        totalDuration: 100,
        cameraMode: 'follow',
        playbackSpeed: 2,
      });
      useSimulationStore.getState().play();
      fake.tick(45);
      useSimulationStore.getState().syncFromClock();

      useSimulationStore.getState().resetPlayback();

      const state = useSimulationStore.getState();
      expect(state.playbackState).toBe('stopped');
      expect(state.elapsed).toBe(0);
      // The view is NOT reset.
      expect(state.cameraMode).toBe('follow');
      expect(state.playbackSpeed).toBe(2);
      expect(fake.getAnimate()).toBe(false);
      expect(fake.getElapsed()).toBe(0);
    });

    it('play() from the parked end restarts from zero', () => {
      const fake = makeFakeBridge();
      bindSimViewer(fake.viewer, fake.bridge);
      useSimulationStore.setState({ totalDuration: 100, elapsed: 100 });

      useSimulationStore.getState().play();

      expect(useSimulationStore.getState().elapsed).toBe(0);
      expect(useSimulationStore.getState().playbackState).toBe('playing');
      expect(fake.getElapsed()).toBe(0);
    });
  });

  describe('unbind resets module singletons', () => {
    it('clears the bridge so a stale clock can no longer be driven', () => {
      const fake = makeFakeBridge();
      bindSimViewer(fake.viewer, fake.bridge);
      useSimulationStore.setState({ totalDuration: 100 });
      useSimulationStore.getState().play();
      expect(fake.getAnimate()).toBe(true);

      unbindSimViewer(fake.viewer);

      // After unbind, play() can no longer reach the (now-detached) bridge:
      // it early-returns (like having no viewer), so it neither transitions to
      // playing nor re-animates the stale clock.
      useSimulationStore.getState().stop(); // back to a known stopped state
      fake.bridge.setAnimate(false);
      useSimulationStore.getState().play();
      expect(useSimulationStore.getState().playbackState).toBe('stopped');
      expect(fake.getAnimate()).toBe(false);
    });

    it('resets the position-sync throttle timestamp across remount', () => {
      vi.useFakeTimers();
      vi.setSystemTime(5_000);
      const fake = makeFakeBridge();
      bindSimViewer(fake.viewer, fake.bridge);

      const p1 = { lat: 1, lon: 1, altAgl: 10, heading: 0, speed: 5, waypointIndex: 0 };
      useSimulationStore.getState().syncPosition(p1);
      expect(useSimulationStore.getState().syncedPosition).toEqual(p1);

      // Unbind clears _lastPositionSyncAt; a same-waypoint sync at the same
      // wall-clock time is then accepted immediately on the new viewer.
      unbindSimViewer(fake.viewer);
      useSimulationStore.getState().reset();
      const fake2 = makeFakeBridge();
      bindSimViewer(fake2.viewer, fake2.bridge);

      const p2 = { lat: 1.1, lon: 1.1, altAgl: 11, heading: 1, speed: 6, waypointIndex: 0 };
      useSimulationStore.getState().syncPosition(p2);
      expect(useSimulationStore.getState().syncedPosition).toEqual(p2);
    });
  });
});
