import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('backend URL resolver', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('apiUrl returns relative path in browser mode', async () => {
    vi.stubGlobal('window', { location: { protocol: 'http:', host: 'localhost:5173' } });
    const { apiUrl, API_BASE } = await import('./backend');
    expect(API_BASE).toBe('');
    expect(apiUrl('/api/ports')).toBe('/api/ports');
  });

  it('getWsUrl uses correct protocol for http', async () => {
    vi.stubGlobal('window', { location: { protocol: 'http:', host: 'localhost:5173' } });
    const { getWsUrl } = await import('./backend');
    const url = getWsUrl();
    expect(url).toBe('ws://localhost:5173/ws');
  });

  it('getWsUrl uses wss for https', async () => {
    vi.stubGlobal('window', { location: { protocol: 'https:', host: 'gcs.example.com' } });
    const { getWsUrl } = await import('./backend');
    const url = getWsUrl();
    expect(url).toBe('wss://gcs.example.com/ws');
  });

  it('detects Tauri mode via __TAURI_INTERNALS__', async () => {
    vi.stubGlobal('window', {
      __TAURI_INTERNALS__: {},
      location: { protocol: 'https:', host: 'tauri.localhost' },
    });
    const { isTauri, API_BASE, getWsUrl } = await import('./backend');
    expect(isTauri).toBe(true);
    expect(API_BASE).toBe('http://127.0.0.1:8100');
    expect(getWsUrl()).toBe('ws://127.0.0.1:8100/ws');
  });

  it('apiUrl resolves full URL in Tauri mode', async () => {
    vi.stubGlobal('window', {
      __TAURI_INTERNALS__: {},
      location: { protocol: 'https:', host: 'tauri.localhost' },
    });
    const { apiUrl } = await import('./backend');
    expect(apiUrl('/api/ports')).toBe('http://127.0.0.1:8100/api/ports');
    expect(apiUrl('/api/connect')).toBe('http://127.0.0.1:8100/api/connect');
  });

  it('isTauri is false when __TAURI_INTERNALS__ absent', async () => {
    vi.stubGlobal('window', { location: { protocol: 'http:', host: 'localhost:8100' } });
    const { isTauri } = await import('./backend');
    expect(isTauri).toBe(false);
  });

  it('getWsUrl with non-standard port', async () => {
    vi.stubGlobal('window', { location: { protocol: 'http:', host: 'myhost:8100' } });
    const { getWsUrl } = await import('./backend');
    expect(getWsUrl()).toBe('ws://myhost:8100/ws');
  });

  it('apiUrl works with nested paths', async () => {
    vi.stubGlobal('window', { location: { protocol: 'http:', host: 'localhost:5173' } });
    const { apiUrl } = await import('./backend');
    expect(apiUrl('/api/v2/mission/upload')).toBe('/api/v2/mission/upload');
  });
});
