import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('./stores.svelte', () => ({
  app: { drone: { armed: false, mode: 'STABILIZE' }, waypoints: [{ lat: 34, lon: 108, alt: 50 }] },
  addToast: vi.fn(),
}));
vi.mock('./ws', () => ({
  sendCommand: vi.fn(),
}));

// Minimal document stub for createElement/element.remove
const createEl = (tag: string) => {
  const el: any = {
    tagName: tag.toUpperCase(),
    textContent: '',
    remove: vi.fn(),
    appendChild: vi.fn(),
  };
  return el;
};

vi.stubGlobal('document', { createElement: vi.fn(createEl) });

import { getPlugins, getPanels, createPluginAPI, loadPlugin, unloadPlugin, emitPluginEvent } from './plugins';
import { sendCommand } from './ws';
import { addToast } from './stores.svelte';

describe('plugins', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Stub window for CustomEvent dispatch
    vi.stubGlobal('window', {
      addEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    });
    vi.stubGlobal('document', { createElement: vi.fn(createEl) });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('getPlugins returns an array', () => {
    const plugins = getPlugins();
    expect(Array.isArray(plugins)).toBe(true);
  });

  it('getPanels returns an array', () => {
    const panels = getPanels();
    expect(Array.isArray(panels)).toBe(true);
  });

  describe('createPluginAPI()', () => {
    it('returns an object with version and all methods', () => {
      const api = createPluginAPI();
      expect(api.version).toBe('3.5.0');
      expect(typeof api.getDroneState).toBe('function');
      expect(typeof api.getWaypoints).toBe('function');
      expect(typeof api.sendCommand).toBe('function');
      expect(typeof api.subscribe).toBe('function');
      expect(typeof api.emit).toBe('function');
      expect(typeof api.addPanel).toBe('function');
      expect(typeof api.removePanel).toBe('function');
      expect(typeof api.showToast).toBe('function');
    });

    it('getDroneState returns a copy of drone state', () => {
      const api = createPluginAPI();
      const state = api.getDroneState();
      expect(state).toEqual({ armed: false, mode: 'STABILIZE' });
    });

    it('getWaypoints returns a copy of waypoints', () => {
      const api = createPluginAPI();
      const wps = api.getWaypoints();
      expect(wps).toEqual([{ lat: 34, lon: 108, alt: 50 }]);
    });

    it('sendCommand delegates to ws.sendCommand', () => {
      const api = createPluginAPI();
      api.sendCommand('arm', { force: true });
      expect(sendCommand).toHaveBeenCalledWith('arm', undefined, { force: true });
    });

    it('subscribe and emit roundtrip works', () => {
      const api = createPluginAPI();
      let received: unknown = null;
      const unsub = api.subscribe('test-event', (data) => {
        received = data;
      });
      api.emit('test-event', { value: 42 });
      expect(received).toEqual({ value: 42 });

      // Also dispatches a CustomEvent on window
      expect(window.dispatchEvent).toHaveBeenCalled();

      // Unsubscribe and verify no longer called
      received = null;
      unsub();
      api.emit('test-event', { value: 99 });
      expect(received).toBeNull();
    });

    it('emit does not throw if listener throws', () => {
      const api = createPluginAPI();
      api.subscribe('crash-event', () => {
        throw new Error('boom');
      });
      expect(() => api.emit('crash-event', {})).not.toThrow();
    });

    it('addPanel adds element to panel container', () => {
      const api = createPluginAPI();
      const el = createEl('div') as unknown as HTMLElement;
      const before = getPanels().length;
      api.addPanel(el);
      expect(getPanels().length).toBe(before + 1);
      expect(getPanels()).toContain(el);
      // Clean up
      api.removePanel(el);
    });

    it('removePanel removes element from panel container', () => {
      const api = createPluginAPI();
      const el = createEl('div') as unknown as HTMLElement;
      api.addPanel(el);
      const before = getPanels().length;
      api.removePanel(el);
      expect(getPanels().length).toBe(before - 1);
      expect(getPanels()).not.toContain(el);
    });

    it('removePanel does nothing for element not in container', () => {
      const api = createPluginAPI();
      const el = createEl('div') as unknown as HTMLElement;
      const before = getPanels().length;
      api.removePanel(el);
      expect(getPanels().length).toBe(before);
    });

    it('showToast calls addToast via dynamic import', async () => {
      const api = createPluginAPI();
      api.showToast('Hello!', 'warn');
      // showToast is async (dynamic import) — wait for it
      await vi.waitFor(() => {
        expect(addToast).toHaveBeenCalledWith('Hello!', 'warn');
      });
    });

    it('showToast defaults level to info', async () => {
      const api = createPluginAPI();
      api.showToast('Default level');
      await vi.waitFor(() => {
        expect(addToast).toHaveBeenCalledWith('Default level', 'info');
      });
    });
  });

  describe('loadPlugin()', () => {
    it('fetches plugin code from the given URL', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        text: () => Promise.resolve('// plugin code'),
      });
      vi.stubGlobal('fetch', mockFetch);

      // loadPlugin will fail at Blob/URL/import in Node, but fetch should be called
      try {
        await loadPlugin('http://example.com/plugin.js');
      } catch {
        // Expected: Blob/URL/import not available in this test env
      }

      expect(mockFetch).toHaveBeenCalledWith('http://example.com/plugin.js');
    });

    it('propagates fetch errors', async () => {
      vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network failure')));

      await expect(loadPlugin('http://example.com/fail.js')).rejects.toThrow('Network failure');
    });
  });

  describe('unloadPlugin()', () => {
    it('on a non-existent name does not throw', () => {
      expect(() => unloadPlugin('nonexistent_plugin_xyz')).not.toThrow();
    });

    it('calls destroy and unmount on plugin module, removes element', () => {
      // Manually push a fake plugin into the internal _plugins array
      const destroyFn = vi.fn();
      const unmountFn = vi.fn();
      const el = createEl('div') as unknown as HTMLElement;

      // Access internal state by loading a plugin-like entry
      const plugins = getPlugins();
      const panels = getPanels();
      plugins.push({
        manifest: { name: 'FakeForUnload', version: '1.0.0', entrypoint: 'fake.js' },
        module: { destroy: destroyFn, unmount: unmountFn },
        element: el,
        active: true,
      });
      panels.push(el);

      const panelsBefore = panels.length;
      unloadPlugin('FakeForUnload');

      expect(destroyFn).toHaveBeenCalled();
      expect(unmountFn).toHaveBeenCalled();
      expect((el as any).remove).toHaveBeenCalled();
      expect(panels.length).toBe(panelsBefore - 1);
      expect(plugins.find((p) => p.manifest.name === 'FakeForUnload')).toBeUndefined();
    });

    it('handles plugin without element or destroy/unmount', () => {
      const plugins = getPlugins();
      plugins.push({
        manifest: { name: 'MinimalPlugin', version: '0.1.0', entrypoint: 'min.js' },
        module: {},
        active: true,
      });

      expect(() => unloadPlugin('MinimalPlugin')).not.toThrow();
      expect(plugins.find((p) => p.manifest.name === 'MinimalPlugin')).toBeUndefined();
    });
  });

  describe('emit/subscribe edge cases', () => {
    it('emit to event with no subscribers does not throw', () => {
      const api = createPluginAPI();
      expect(() => api.emit('no-subs-event', { data: 1 })).not.toThrow();
    });

    it('multiple subscribers receive same event', () => {
      const api = createPluginAPI();
      const results: unknown[] = [];
      api.subscribe('multi', (d) => results.push(d));
      api.subscribe('multi', (d) => results.push(d));
      api.emit('multi', 'hello');
      expect(results).toEqual(['hello', 'hello']);
    });
  });

  describe('emitPluginEvent()', () => {
    it('calls registered listeners for the event', () => {
      const api = createPluginAPI();
      let received: unknown = null;
      api.subscribe('plugin-ev', (d) => {
        received = d;
      });
      emitPluginEvent('plugin-ev', { x: 1 });
      expect(received).toEqual({ x: 1 });
    });

    it('does not throw when no listeners registered', () => {
      expect(() => emitPluginEvent('unregistered-ev', 'data')).not.toThrow();
    });

    it('swallows errors from listeners', () => {
      const api = createPluginAPI();
      api.subscribe('error-ev', () => {
        throw new Error('kaboom');
      });
      expect(() => emitPluginEvent('error-ev', null)).not.toThrow();
    });
  });
});
