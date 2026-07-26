/**
 * traffic-ipc-handlers — wires the TrafficService to Electron: a config store,
 * the existing encrypted secret store, the renderer push channel, and the
 * renderer->main control channels (viewport, enable, config get/set).
 */

import { ipcMain, BrowserWindow } from 'electron';
import Store from 'electron-store';
import { IPC_CHANNELS } from '../../shared/ipc-channels.js';
import {
  DEFAULT_TRAFFIC_CONFIG,
  type TrafficBatch,
  type TrafficConfig,
  type TrafficSource,
  type ViewportBbox,
} from '../../shared/traffic-types.js';
import { getApiKey } from '../overlays/overlay-ipc-handlers.js';
import { TrafficService } from './traffic-service.js';

interface TrafficStoreSchema {
  config: TrafficConfig;
}

const configStore = new Store<TrafficStoreSchema>({
  name: 'traffic',
  defaults: { config: DEFAULT_TRAFFIC_CONFIG },
});

/** Merge persisted config over defaults so new fields appear after upgrades. */
function loadConfig(): TrafficConfig {
  const stored = configStore.get('config');
  return {
    ...DEFAULT_TRAFFIC_CONFIG,
    ...stored,
    localAdsb: { ...DEFAULT_TRAFFIC_CONFIG.localAdsb, ...stored?.localAdsb },
    adsbApi: { ...DEFAULT_TRAFFIC_CONFIG.adsbApi, ...stored?.adsbApi },
    openSky: { ...DEFAULT_TRAFFIC_CONFIG.openSky, ...stored?.openSky },
    ogn: { ...DEFAULT_TRAFFIC_CONFIG.ogn, ...stored?.ogn },
    proximity: { ...DEFAULT_TRAFFIC_CONFIG.proximity, ...stored?.proximity },
    altitudeFilter: { ...DEFAULT_TRAFFIC_CONFIG.altitudeFilter, ...stored?.altitudeFilter },
  };
}

let service: TrafficService | null = null;

export function setupTrafficHandlers(_mainWindow: BrowserWindow): void {
  service = new TrafficService({
    getConfig: loadConfig,
    saveConfig: (cfg) => configStore.set('config', cfg),
    getSecret: getApiKey,
    // Broadcast to every window so the Area Editor (a separate BrowserWindow)
    // receives contacts too, not just the main window.
    push: (batch: TrafficBatch) => {
      for (const win of BrowserWindow.getAllWindows()) {
        if (!win.isDestroyed()) win.webContents.send(IPC_CHANNELS.TRAFFIC_UPDATE, batch);
      }
    },
  });
  service.start();

  ipcMain.handle(IPC_CHANNELS.TRAFFIC_GET_CONFIG, async () => loadConfig());

  ipcMain.handle(IPC_CHANNELS.TRAFFIC_SET_CONFIG, async (_e, cfg: TrafficConfig) => {
    service?.setConfig(cfg);
    return { success: true };
  });

  ipcMain.on(IPC_CHANNELS.TRAFFIC_SET_VIEWPORT, (_e, v: ViewportBbox) => {
    service?.setViewport(v);
  });

  ipcMain.on(IPC_CHANNELS.TRAFFIC_SET_ENABLED, (_e, payload: { source: TrafficSource; enabled: boolean }) => {
    service?.setEnabled(payload.source, payload.enabled);
  });
}

export function disposeTrafficHandlers(): void {
  service?.dispose();
  service = null;
}
