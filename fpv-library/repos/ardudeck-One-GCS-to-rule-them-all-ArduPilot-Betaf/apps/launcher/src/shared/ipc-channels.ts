import type { RegionSummary } from './region.js';
import type { LaunchConfig } from './launch-config.js';

export const IPC = {
  launcherInfo: 'launcher:info',
  prefsGet: 'launcher:prefs:get',
  prefsSet: 'launcher:prefs:set',
  regionsList: 'regions:list',
  gameLaunch: 'game:launch',
  gameStop: 'game:stop',
  gameStatus: 'game:status',
  gameLog: 'game:log',
  openPath: 'launcher:open-path',
} as const;

export interface LauncherInfo {
  appVersion: string;
  /** Where the launcher writes the config the game reads. */
  configPath: string;
  /** Directories scanned for baked regions, in order. */
  regionRoots: string[];
  game: GameTarget | null;
  /** Why no game was found, when `game` is null. */
  gameError: string | null;
}

/** How the launcher will start the game. */
export interface GameTarget {
  /** Executable to spawn. */
  command: string;
  /** Fixed arguments, before the config argument. */
  args: string[];
  /**
   * Working directory for the child. Not `dirname(command)`: a Godot binary lives in
   * /opt/homebrew/bin, which is neither writable nor anything to do with the game.
   */
  cwd: string;
  /** Human label for the UI, for example "Godot (project source)". */
  label: string;
  /** True when this is a Godot binary running the project from source. */
  dev: boolean;
}

export interface LauncherPrefs {
  /** Last region flown, so the launcher opens where the player left off. */
  lastRegion: string | null;
  fpvUptiltDeg: number;
}

export interface RegionListResult {
  sourceId: string;
  sourceLabel: string;
  regions: RegionSummary[];
  /** Source-level problems, for example "no region directory found". */
  errors: string[];
}

export interface LaunchRequest {
  regionName: string;
  fpvUptiltDeg: number;
}

export interface LaunchResult {
  ok: boolean;
  error?: string;
  configPath?: string;
  config?: LaunchConfig;
  pid?: number;
}

export type GameState = 'idle' | 'preparing' | 'starting' | 'running' | 'exited' | 'failed';

export interface GameStatus {
  state: GameState;
  pid: number | null;
  exitCode: number | null;
  signal: string | null;
  error: string | null;
  configPath: string | null;
  regionName: string | null;
  /** Epoch ms, for a session timer. */
  startedAt: number | null;
}

export interface GameLogLine {
  stream: 'stdout' | 'stderr';
  line: string;
}

/** The surface the preload exposes on `window.launcher`. */
export interface LauncherApi {
  getInfo(): Promise<LauncherInfo>;
  getPrefs(): Promise<LauncherPrefs>;
  setPrefs(patch: Partial<LauncherPrefs>): Promise<LauncherPrefs>;
  listRegions(): Promise<RegionListResult>;
  launch(request: LaunchRequest): Promise<LaunchResult>;
  stopGame(): Promise<void>;
  openPath(target: string): Promise<void>;
  onGameStatus(cb: (status: GameStatus) => void): () => void;
  onGameLog(cb: (line: GameLogLine) => void): () => void;
}
