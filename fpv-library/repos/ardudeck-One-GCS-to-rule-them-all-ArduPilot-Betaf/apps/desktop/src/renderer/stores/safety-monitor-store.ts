/**
 * Safety Monitor store - holds the latest engine output for the panel to
 * render, plus user-facing settings (profile, audio). The stateful evaluation
 * engine itself lives in safety-monitor/source.ts at module scope; this store
 * only carries its output and the knobs the UI exposes.
 */

import { create } from 'zustand';
import {
  DEFAULT_PROFILE,
  emptyMonitorState,
  type MonitorProfile,
  type MonitorState,
} from '../../shared/safety-monitor/types';

/** Where the on-ground/in-air signal is coming from. */
export type LandedSource = 'mavlink' | 'inferred' | 'none';

interface SafetyMonitorStore {
  /** Latest evaluation output. */
  monitor: MonitorState;
  /** Active threshold profile. */
  profile: MonitorProfile;
  /** True when GCS_PID_MASK has the roll+pitch bits set. */
  pidStreamingAvailable: boolean;
  /** Provenance of the landed-state used by the engine. */
  landedSource: LandedSource;
  /** Audio cue on DANGER entry. */
  audioEnabled: boolean;
  /** Bumped each time DANGER is freshly entered, to drive the screen flash. */
  flashTick: number;

  setMonitor: (m: MonitorState) => void;
  setProfile: (p: MonitorProfile) => void;
  setPidStreamingAvailable: (v: boolean) => void;
  setLandedSource: (v: LandedSource) => void;
  setAudioEnabled: (v: boolean) => void;
  bumpFlash: () => void;
}

const AUDIO_KEY = 'ardudeck.safetyMonitor.audio.v1';

function loadAudioPref(): boolean {
  try {
    const v = localStorage.getItem(AUDIO_KEY);
    return v === null ? true : v === '1';
  } catch {
    return true;
  }
}

export const useSafetyMonitorStore = create<SafetyMonitorStore>((set) => ({
  monitor: emptyMonitorState(),
  profile: DEFAULT_PROFILE,
  pidStreamingAvailable: false,
  landedSource: 'none',
  audioEnabled: loadAudioPref(),
  flashTick: 0,

  setMonitor: (m) => set({ monitor: m }),
  setProfile: (p) => set({ profile: p }),
  setPidStreamingAvailable: (v) => set({ pidStreamingAvailable: v }),
  setLandedSource: (v) => set({ landedSource: v }),
  setAudioEnabled: (v) => {
    try {
      localStorage.setItem(AUDIO_KEY, v ? '1' : '0');
    } catch {
      // ignore persistence failures
    }
    set({ audioEnabled: v });
  },
  bumpFlash: () => set((s) => ({ flashTick: s.flashTick + 1 })),
}));
