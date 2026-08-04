import { app, ipcMain, shell, type BrowserWindow } from 'electron';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import Store from 'electron-store';
import {
  IPC,
  type GameLogLine,
  type GameStatus,
  type LauncherInfo,
  type LauncherPrefs,
  type LaunchRequest,
  type LaunchResult,
  type RegionListResult,
} from '../shared/ipc-channels.js';
import { buildLaunchConfig, DEFAULT_FPV_UPTILT_DEG, clampUptilt } from '../shared/launch-config.js';
import { buildRegionRoots, findGameRoots } from './regions/region-roots.js';
import { LocalRegionSource } from './regions/local-region-source.js';
import { findGameTarget } from './launch/game-locator.js';
import { GameProcess } from './launch/game-process.js';
import { writeLaunchConfig } from './launch/config-writer.js';

const __dirname_ = dirname(fileURLToPath(import.meta.url));

const prefsStore = new Store<LauncherPrefs>({
  name: 'launcher-prefs',
  defaults: { lastRegion: null, fpvUptiltDeg: DEFAULT_FPV_UPTILT_DEG },
});

let gameProcess: GameProcess | null = null;

/**
 * In dev, `out/main` is two levels under the package root; packaged, `app.getAppPath()` is
 * the asar root. Both resolve to something whose parent chain reaches the monorepo, which is
 * all the game-root walk needs.
 */
function appDir(): string {
  return app.isPackaged ? app.getAppPath() : join(__dirname_, '..', '..');
}

function gameRoots(): string[] {
  return findGameRoots({
    envGameRoot: process.env.ARDUDECK_GAME_ROOT,
    resourcesPath: process.resourcesPath,
    appDir: appDir(),
    isPackaged: app.isPackaged,
    exists: existsSync,
  });
}

function regionRoots(): string[] {
  return buildRegionRoots({
    envRegionDir: process.env.ARDUDECK_REGION_DIR,
    gameRoots: gameRoots(),
    userDataDir: app.getPath('userData'),
  });
}

/** One well-known path, so a bug report can always be asked for the same file. */
function configPath(): string {
  return join(app.getPath('userData'), 'launch-config.json');
}

function locateGame() {
  return findGameTarget({
    envGameBin: process.env.ARDUDECK_GAME_BIN,
    envGodotBin: process.env.ARDUDECK_GODOT_BIN,
    gameRoots: gameRoots(),
    platform: process.platform,
    exists: existsSync,
  });
}

export function setupIpc(getWindow: () => BrowserWindow | null): void {
  const send = (channel: string, payload: unknown): void => {
    const win = getWindow();
    if (win && !win.isDestroyed()) win.webContents.send(channel, payload);
  };

  gameProcess = new GameProcess(
    (status: GameStatus) => send(IPC.gameStatus, status),
    (line: GameLogLine) => send(IPC.gameLog, line),
  );

  ipcMain.handle(IPC.launcherInfo, (): LauncherInfo => {
    const located = locateGame();
    return {
      appVersion: app.getVersion(),
      configPath: configPath(),
      regionRoots: regionRoots(),
      game: located.target,
      gameError: located.error,
    };
  });

  ipcMain.handle(IPC.prefsGet, (): LauncherPrefs => ({
    lastRegion: prefsStore.get('lastRegion'),
    fpvUptiltDeg: prefsStore.get('fpvUptiltDeg'),
  }));

  ipcMain.handle(IPC.prefsSet, (_e, patch: Partial<LauncherPrefs>): LauncherPrefs => {
    if (patch.lastRegion !== undefined) prefsStore.set('lastRegion', patch.lastRegion);
    if (patch.fpvUptiltDeg !== undefined) prefsStore.set('fpvUptiltDeg', clampUptilt(patch.fpvUptiltDeg));
    return { lastRegion: prefsStore.get('lastRegion'), fpvUptiltDeg: prefsStore.get('fpvUptiltDeg') };
  });

  ipcMain.handle(IPC.regionsList, async (): Promise<RegionListResult> => {
    const source = new LocalRegionSource(regionRoots());
    const regions = await source.list();
    return { sourceId: source.id, sourceLabel: source.label, regions, errors: source.errors };
  });

  ipcMain.handle(IPC.gameLaunch, async (_e, request: LaunchRequest): Promise<LaunchResult> => {
    try {
      if (gameProcess?.isRunning()) return { ok: false, error: 'The game is already running' };

      const located = locateGame();
      if (!located.target) return { ok: false, error: located.error ?? 'No game found' };

      const source = new LocalRegionSource(regionRoots());
      const prepared = await source.prepare(request.regionName);

      // The manifest carries no ground elevation or heading at home, so those are left out
      // and the game samples its own terrain, which is the surface that actually exists.
      const config = buildLaunchConfig({
        region: {
          name: prepared.name,
          assetPath: prepared.assetPath,
          home: prepared.home ?? { lat: 0, lon: 0 },
        },
        fpvUptiltDeg: request.fpvUptiltDeg,
        appVersion: app.getVersion(),
      });

      const path = configPath();
      await writeLaunchConfig(path, config);
      prefsStore.set('lastRegion', prepared.name);
      prefsStore.set('fpvUptiltDeg', config.camera.fpvUptiltDeg);

      const pid = gameProcess!.start({
        target: located.target,
        configPath: path,
        regionName: prepared.name,
      });
      return { ok: true, configPath: path, config, pid };
    } catch (err) {
      return { ok: false, error: (err as Error).message };
    }
  });

  ipcMain.handle(IPC.gameStop, (): void => {
    gameProcess?.stop();
  });

  ipcMain.handle(IPC.openPath, async (_e, target: string): Promise<void> => {
    await shell.openPath(target);
  });
}

export function cleanupIpc(): void {
  gameProcess?.dispose();
  gameProcess = null;
}
