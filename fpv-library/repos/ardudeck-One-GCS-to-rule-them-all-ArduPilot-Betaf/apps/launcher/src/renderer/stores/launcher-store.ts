import { create } from 'zustand';
import type {
  GameLogLine,
  GameStatus,
  LauncherInfo,
  RegionListResult,
} from '../../shared/ipc-channels.js';
import { DEFAULT_FPV_UPTILT_DEG } from '../../shared/launch-config.js';
import type { RegionSummary } from '../../shared/region.js';

export type StepId = 'region' | 'conditions' | 'vehicle';

const MAX_LOG_LINES = 400;

const IDLE_STATUS: GameStatus = {
  state: 'idle',
  pid: null,
  exitCode: null,
  signal: null,
  error: null,
  configPath: null,
  regionName: null,
  startedAt: null,
};

interface LauncherStore {
  info: LauncherInfo | null;
  regions: RegionSummary[];
  regionSourceLabel: string;
  regionErrors: string[];
  regionsLoading: boolean;

  step: StepId;
  selectedRegion: string | null;
  fpvUptiltDeg: number;

  gameStatus: GameStatus;
  gameLog: GameLogLine[];
  launchError: string | null;

  init(): Promise<void>;
  refreshRegions(): Promise<void>;
  setStep(step: StepId): void;
  selectRegion(name: string): void;
  setUptilt(deg: number): void;
  launch(): Promise<void>;
  stop(): Promise<void>;
}

export const useLauncherStore = create<LauncherStore>((set, get) => ({
  info: null,
  regions: [],
  regionSourceLabel: '',
  regionErrors: [],
  regionsLoading: false,

  step: 'region',
  selectedRegion: null,
  fpvUptiltDeg: DEFAULT_FPV_UPTILT_DEG,

  gameStatus: IDLE_STATUS,
  gameLog: [],
  launchError: null,

  async init() {
    window.launcher.onGameStatus((gameStatus) => set({ gameStatus }));
    window.launcher.onGameLog((line) =>
      set((s) => ({ gameLog: [...s.gameLog, line].slice(-MAX_LOG_LINES) })),
    );

    const [info, prefs] = await Promise.all([window.launcher.getInfo(), window.launcher.getPrefs()]);
    set({ info, fpvUptiltDeg: prefs.fpvUptiltDeg });
    await get().refreshRegions();

    // Re-selecting last time's region only makes sense if it is still on disk.
    const { regions } = get();
    const remembered = regions.find((r) => r.name === prefs.lastRegion);
    set({ selectedRegion: remembered?.name ?? regions[0]?.name ?? null });
  },

  async refreshRegions() {
    set({ regionsLoading: true });
    try {
      const result: RegionListResult = await window.launcher.listRegions();
      set({
        regions: result.regions,
        regionSourceLabel: result.sourceLabel,
        regionErrors: result.errors,
      });
      // A selection that vanished (region deleted between refreshes) must not survive.
      const { selectedRegion } = get();
      if (selectedRegion && !result.regions.some((r) => r.name === selectedRegion)) {
        set({ selectedRegion: result.regions[0]?.name ?? null });
      }
    } finally {
      set({ regionsLoading: false });
    }
  },

  setStep(step) {
    set({ step });
  },

  selectRegion(name) {
    set({ selectedRegion: name, launchError: null });
  },

  setUptilt(deg) {
    set({ fpvUptiltDeg: deg });
    void window.launcher.setPrefs({ fpvUptiltDeg: deg });
  },

  async launch() {
    const { selectedRegion, fpvUptiltDeg } = get();
    if (!selectedRegion) {
      set({ launchError: 'Pick a region first' });
      return;
    }
    set({ launchError: null, gameLog: [] });
    const result = await window.launcher.launch({ regionName: selectedRegion, fpvUptiltDeg });
    if (!result.ok) set({ launchError: result.error ?? 'Launch failed' });
  },

  async stop() {
    await window.launcher.stopGame();
  },
}));
