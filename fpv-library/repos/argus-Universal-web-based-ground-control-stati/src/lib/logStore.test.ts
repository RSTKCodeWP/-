import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  logState,
  setLogList,
  startDownload,
  updateDownloadProgress,
  cancelDownload,
  completeDownload,
  appendLogChunk,
} from './logStore.svelte';

describe('logStore', () => {
  it('setLogList replaces list', () => {
    setLogList([{ id: 1, size: 1024, time_utc: 1000 }]);
    expect(logState.list.length).toBe(1);
    expect(logState.list[0].id).toBe(1);
    setLogList([]);
    expect(logState.list.length).toBe(0);
  });

  it('setLogList with multiple entries', () => {
    setLogList([
      { id: 1, size: 1024, time_utc: 1000 },
      { id: 2, size: 2048, time_utc: 2000 },
      { id: 3, size: 4096, time_utc: 3000 },
    ]);
    expect(logState.list.length).toBe(3);
    expect(logState.list[2].size).toBe(4096);
  });

  it('startDownload sets state', () => {
    startDownload(5, 2048);
    expect(logState.downloading).toBe(true);
    expect(logState.downloadId).toBe(5);
    expect(logState.progress).toBe(0);
  });

  it('startDownload resets speed tracking fields', () => {
    startDownload(1, 1000);
    expect(logState.downloadedBytes).toBe(0);
    expect(logState.downloadSpeed).toBe('');
    expect(logState._lastSpeedTime).toBe(0);
    expect(logState._lastSpeedBytes).toBe(0);
  });

  it('updateDownloadProgress calculates percentage', () => {
    startDownload(1, 1000);
    updateDownloadProgress(500, 1000);
    expect(logState.progress).toBe(50);
  });

  it('updateDownloadProgress handles zero total gracefully', () => {
    startDownload(1, 0);
    updateDownloadProgress(100, 0);
    expect(logState.progress).toBe(0);
    expect(logState.downloadedBytes).toBe(100);
  });

  it('updateDownloadProgress rounds to integer', () => {
    startDownload(1, 1000);
    updateDownloadProgress(333, 1000);
    expect(logState.progress).toBe(33);
  });

  it('updateDownloadProgress initializes speed tracking on first call', () => {
    startDownload(1, 1000);
    // First call sets baseline, no speed computed
    updateDownloadProgress(100, 1000);
    expect(logState._lastSpeedTime).toBeGreaterThan(0);
    expect(logState._lastSpeedBytes).toBe(100);
    expect(logState.downloadSpeed).toBe('');
  });

  it('cancelDownload resets state', () => {
    startDownload(1, 1000);
    cancelDownload();
    expect(logState.downloading).toBe(false);
    expect(logState.downloadId).toBe(-1);
    expect(logState.progress).toBe(0);
  });

  it('cancelDownload clears speed string', () => {
    startDownload(1, 1000);
    cancelDownload();
    expect(logState.downloadSpeed).toBe('');
  });
});

describe('completeDownload', () => {
  beforeEach(() => {
    // Mock DOM APIs needed by completeDownload
    vi.stubGlobal('atob', (s: string) => Buffer.from(s, 'base64').toString('binary'));
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:mock-url'),
      revokeObjectURL: vi.fn(),
    });
    vi.stubGlobal(
      'Blob',
      class MockBlob {
        constructor(
          public parts: any[],
          public options: any,
        ) {}
      },
    );
    vi.stubGlobal('document', {
      createElement: vi.fn(() => ({
        href: '',
        download: '',
        click: vi.fn(),
      })),
    });
  });

  it('resets download state', () => {
    startDownload(7, 1024);
    completeDownload(7, btoa('test'), 4);
    expect(logState.downloading).toBe(false);
    expect(logState.downloadId).toBe(-1);
    expect(logState.progress).toBe(100);
    expect(logState.downloadSpeed).toBe('');
  });

  it('creates a download link with correct filename', () => {
    startDownload(42, 100);
    completeDownload(42, btoa('data'), 4);
    const anchor = (document.createElement as ReturnType<typeof vi.fn>).mock.results[0].value;
    expect(anchor.download).toBe('log_42.bin');
    expect(anchor.href).toBe('blob:mock-url');
    expect(anchor.click).toHaveBeenCalled();
  });

  it('revokes object URL after download', () => {
    startDownload(1, 100);
    completeDownload(1, btoa('x'), 1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
  });

  it('streaming path: appendLogChunk + completeDownload reassembles', () => {
    startDownload(99, 6);
    appendLogChunk(99, 0, btoa('abc'));
    appendLogChunk(99, 3, btoa('def'));
    // Streaming completion has no inline data
    completeDownload(99, undefined, 6);
    expect(logState.downloading).toBe(false);
    expect(logState._chunks.length).toBe(0);
  });

  it('appendLogChunk ignores chunks for other downloads', () => {
    startDownload(99, 6);
    appendLogChunk(7, 0, btoa('xxx')); // wrong id — should be dropped
    expect(logState._chunks.length).toBe(0);
  });

  it('cancelDownload clears accumulated chunks', () => {
    startDownload(99, 100);
    appendLogChunk(99, 0, btoa('abcd'));
    expect(logState._chunks.length).toBe(1);
    cancelDownload();
    expect(logState._chunks.length).toBe(0);
  });
});
