import { app } from './stores.svelte';
import { sendCommand } from './ws';

export interface PluginManifest {
  name: string;
  version: string;
  description?: string;
  author?: string;
  entrypoint: string;
}

export interface PluginInstance {
  manifest: PluginManifest;
  module: Record<string, unknown>;
  element?: HTMLElement;
  active: boolean;
}

export interface PluginAPI {
  version: string;
  getDroneState: () => Record<string, unknown>;
  getWaypoints: () => unknown[];
  sendCommand: (cmd: string, data?: Record<string, unknown>) => void;
  subscribe: (event: string, cb: (data: unknown) => void) => () => void;
  emit: (event: string, data: unknown) => void;
  addPanel: (el: HTMLElement) => void;
  removePanel: (el: HTMLElement) => void;
  showToast: (msg: string, level?: string) => void;
}

let _plugins: PluginInstance[] = [];
const _panelContainer: HTMLElement[] = [];
const _listeners = new Map<string, Set<(data: unknown) => void>>();

export function getPlugins(): PluginInstance[] {
  return _plugins;
}
export function getPanels(): HTMLElement[] {
  return _panelContainer;
}

export function createPluginAPI(): PluginAPI {
  return {
    version: '3.5.0',

    getDroneState() {
      return { ...app.drone };
    },

    getWaypoints() {
      return [...app.waypoints];
    },

    sendCommand(cmd: string, data?: Record<string, unknown>) {
      sendCommand(cmd, undefined, data);
    },

    subscribe(event: string, cb: (data: unknown) => void) {
      if (!_listeners.has(event)) _listeners.set(event, new Set());
      _listeners.get(event)!.add(cb);
      return () => {
        _listeners.get(event)?.delete(cb);
      };
    },

    emit(event: string, data: unknown) {
      _listeners.get(event)?.forEach((cb) => {
        try {
          cb(data);
        } catch {}
      });
      window.dispatchEvent(new CustomEvent(`argus:${event}`, { detail: data }));
    },

    addPanel(el: HTMLElement) {
      _panelContainer.push(el);
    },

    removePanel(el: HTMLElement) {
      const idx = _panelContainer.indexOf(el);
      if (idx >= 0) _panelContainer.splice(idx, 1);
    },

    showToast(msg: string, level = 'info') {
      import('./stores.svelte')
        .then((m) => m.addToast(msg, level as 'info' | 'warn' | 'error' | 'success'))
        .catch(() => {});
    },
  };
}

export async function loadPlugin(url: string): Promise<PluginInstance> {
  const resp = await fetch(url);
  const text = await resp.text();
  const blob = new Blob([text], { type: 'application/javascript' });
  const blobUrl = URL.createObjectURL(blob);
  const mod = await import(/* @vite-ignore */ blobUrl);
  URL.revokeObjectURL(blobUrl);
  const manifest: PluginManifest = mod.manifest || { name: 'Unknown', version: '0.0.0', entrypoint: url };
  const instance: PluginInstance = { manifest, module: mod, active: true };
  if (typeof mod.init === 'function') {
    mod.init(createPluginAPI());
  }
  if (typeof mod.mount === 'function') {
    const el = document.createElement('div');
    mod.mount(el);
    instance.element = el;
    _panelContainer.push(el);
  }
  _plugins.push(instance);
  return instance;
}

export function unloadPlugin(name: string) {
  const idx = _plugins.findIndex((p) => p.manifest.name === name);
  if (idx >= 0) {
    const p = _plugins[idx];
    if (typeof p.module.destroy === 'function') (p.module.destroy as () => void)();
    if (typeof p.module.unmount === 'function') (p.module.unmount as () => void)();
    if (p.element) {
      const pi = _panelContainer.indexOf(p.element);
      if (pi >= 0) _panelContainer.splice(pi, 1);
      p.element.remove();
    }
    _plugins.splice(idx, 1);
  }
}

export function emitPluginEvent(event: string, data: unknown) {
  _listeners.get(event)?.forEach((cb) => {
    try {
      cb(data);
    } catch {}
  });
}
