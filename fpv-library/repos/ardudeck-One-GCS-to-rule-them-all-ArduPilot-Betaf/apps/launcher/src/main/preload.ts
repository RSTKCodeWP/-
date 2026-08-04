import { contextBridge, ipcRenderer } from 'electron';
import {
  IPC,
  type GameLogLine,
  type GameStatus,
  type LauncherApi,
  type LauncherInfo,
  type LauncherPrefs,
  type LaunchRequest,
  type LaunchResult,
  type RegionListResult,
} from '../shared/ipc-channels.js';

const api: LauncherApi = {
  getInfo: () => ipcRenderer.invoke(IPC.launcherInfo) as Promise<LauncherInfo>,
  getPrefs: () => ipcRenderer.invoke(IPC.prefsGet) as Promise<LauncherPrefs>,
  setPrefs: (patch) => ipcRenderer.invoke(IPC.prefsSet, patch) as Promise<LauncherPrefs>,
  listRegions: () => ipcRenderer.invoke(IPC.regionsList) as Promise<RegionListResult>,
  launch: (request: LaunchRequest) => ipcRenderer.invoke(IPC.gameLaunch, request) as Promise<LaunchResult>,
  stopGame: () => ipcRenderer.invoke(IPC.gameStop) as Promise<void>,
  openPath: (target: string) => ipcRenderer.invoke(IPC.openPath, target) as Promise<void>,
  onGameStatus: (cb) => {
    const handler = (_e: unknown, status: GameStatus) => cb(status);
    ipcRenderer.on(IPC.gameStatus, handler);
    return () => ipcRenderer.off(IPC.gameStatus, handler);
  },
  onGameLog: (cb) => {
    const handler = (_e: unknown, line: GameLogLine) => cb(line);
    ipcRenderer.on(IPC.gameLog, handler);
    return () => ipcRenderer.off(IPC.gameLog, handler);
  },
};

contextBridge.exposeInMainWorld('launcher', api);
