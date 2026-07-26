import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('./stores.svelte', () => ({
  app: { drone: {}, events: [] },
  updateState: vi.fn(),
  addEvent: vi.fn(),
  setWsConnected: vi.fn(),
  addToast: vi.fn(),
  loadDownloadedMission: vi.fn(),
}));
vi.mock('./paramStore.svelte', () => ({
  handleParamBatch: vi.fn(),
  handleParamsComplete: vi.fn(),
}));
vi.mock('./logStore.svelte', () => ({
  setLogList: vi.fn(),
  completeDownload: vi.fn(),
  updateDownloadProgress: vi.fn(),
  appendLogChunk: vi.fn(),
}));
vi.mock('./inspectorStore.svelte', () => ({
  updateInspector: vi.fn(),
  appendConsole: vi.fn(),
}));
vi.mock('./flightDb', () => ({
  saveFlightRecord: vi.fn(),
}));
vi.mock('./backend', () => ({
  getWsUrl: () => 'ws://localhost:8100/ws',
}));
vi.mock('./i18n.svelte', () => ({
  onLocaleChange: vi.fn(),
  getLocale: () => 'en',
  t: (k: string) => k,
}));

let mockWs: {
  onopen: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  onclose: (() => void) | null;
  onerror: ((ev: Event) => void) | null;
  send: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
  readyState: number;
};

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockWs = {
    onopen: null,
    onmessage: null,
    onclose: null,
    onerror: null,
    send: vi.fn(),
    close: vi.fn(),
    readyState: 1,
  };
  vi.stubGlobal(
    'WebSocket',
    vi.fn(() => mockWs),
  );
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function freshConnect() {
  vi.resetModules();
  mockWs = {
    onopen: null,
    onmessage: null,
    onclose: null,
    onerror: null,
    send: vi.fn(),
    close: vi.fn(),
    readyState: 1,
  };
  class WsMock {
    static OPEN = 1;
    static CLOSED = 3;
    static CONNECTING = 0;
    static CLOSING = 2;
    constructor() {
      return mockWs as unknown as WsMock;
    }
  }
  vi.stubGlobal('WebSocket', WsMock);
  const mod = await import('./ws');
  mod.connectWs();
  return mod;
}

describe('connectWs', () => {
  it('creates a WebSocket and sets connected on open', async () => {
    await freshConnect();
    mockWs.onopen?.(new Event('open'));
    const { setWsConnected } = await import('./stores.svelte');
    expect(setWsConnected).toHaveBeenCalledWith(true);
  });

  it('sets disconnected on close', async () => {
    await freshConnect();
    mockWs.onopen?.(new Event('open'));
    mockWs.onclose?.();
    const { setWsConnected } = await import('./stores.svelte');
    expect(setWsConnected).toHaveBeenCalledWith(false);
  });

  it('closes on error', async () => {
    await freshConnect();
    mockWs.onerror?.(new Event('error'));
    expect(mockWs.close).toHaveBeenCalled();
  });
});

describe('message handling', () => {
  async function fire(msg: Record<string, unknown>) {
    await freshConnect();
    mockWs.onopen?.(new Event('open'));
    mockWs.onmessage?.(new MessageEvent('message', { data: JSON.stringify(msg) }));
  }

  it('dispatches state messages', async () => {
    await fire({ type: 'state', connected: true });
    const { updateState } = await import('./stores.svelte');
    expect(updateState).toHaveBeenCalled();
  });

  it('flight_summary from delta uses app.drone fallback for vtype/fw_version', async () => {
    // Delta states omit unchanged fields — vtype and fw_version may be absent.
    // The flight record must still capture the correct vehicle/firmware info.
    const { app } = await import('./stores.svelte');
    app.drone = { ...app.drone, vtype: 'Quadrotor', fw_version: 'v4.3.0', flight_summary: null };
    await freshConnect();
    mockWs.onopen?.(new Event('open'));
    const flightSummary = { duration: 120, max_alt: 50, max_speed: 10, total_dist: 300, bat_used: 20 };
    // Delta: has flight_summary but NOT vtype/fw_version
    mockWs.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({ type: 'state', flight_summary: flightSummary }),
    }));
    const { saveFlightRecord } = await import('./flightDb');
    expect(saveFlightRecord).toHaveBeenCalledWith(
      expect.objectContaining({ vtype: 'Quadrotor', fw: 'v4.3.0' }),
    );
  });

  it('flight_summary prefers msg.vtype/fw_version over app.drone fallback', async () => {
    // Regression guard: if the operands of `??` ever swap, this catches it.
    const { app } = await import('./stores.svelte');
    app.drone = { ...app.drone, vtype: 'OLD', fw_version: 'v0.0.0', flight_summary: null };
    await freshConnect();
    mockWs.onopen?.(new Event('open'));
    const flightSummary = { duration: 120, max_alt: 50, max_speed: 10, total_dist: 300, bat_used: 20 };
    mockWs.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({
        type: 'state',
        flight_summary: flightSummary,
        vtype: 'Plane',
        fw_version: 'v4.5.0',
      }),
    }));
    const { saveFlightRecord } = await import('./flightDb');
    expect(saveFlightRecord).toHaveBeenCalledWith(
      expect.objectContaining({ vtype: 'Plane', fw: 'v4.5.0' }),
    );
  });

  it('dispatches event messages', async () => {
    await fire({ type: 'event', text: 'test', event_type: 'test', time: '00:00:00' });
    const { addEvent } = await import('./stores.svelte');
    expect(addEvent).toHaveBeenCalled();
  });

  it('dispatches armed event with toast', async () => {
    await fire({ type: 'event', text: 'Armed', event_type: 'armed', time: '00:00:00' });
    const { addToast } = await import('./stores.svelte');
    expect(addToast).toHaveBeenCalled();
  });

  it('dispatches param_batch', async () => {
    await fire({ type: 'param_batch', params: [{ name: 'P', value: 1 }] });
    const { handleParamBatch } = await import('./paramStore.svelte');
    expect(handleParamBatch).toHaveBeenCalledWith([{ name: 'P', value: 1 }]);
  });

  it('cmd_result error surfaces as toast', async () => {
    // sendCommand is fire-and-forget; a refused command (e.g. the
    // unsupported-autopilot gate) must not fail invisibly.
    await fire({ type: 'cmd_result', ok: false, error: 'unsupported autopilot (12): ArduPilot only' });
    const { addToast } = await import('./stores.svelte');
    expect(addToast).toHaveBeenCalledWith(
      'unsupported autopilot (12): ArduPilot only', 'error', 6000);
  });

  it('cmd_result success stays silent', async () => {
    await fire({ type: 'cmd_result', ok: true });
    const { addToast } = await import('./stores.svelte');
    expect(addToast).not.toHaveBeenCalled();
  });

  it('dispatches params_complete', async () => {
    await fire({ type: 'params_complete' });
    const { handleParamsComplete } = await import('./paramStore.svelte');
    expect(handleParamsComplete).toHaveBeenCalled();
  });

  it('dispatches mission_downloaded', async () => {
    await fire({ type: 'mission_downloaded', waypoints: [{ lat: 1, lon: 2 }] });
    const { loadDownloadedMission } = await import('./stores.svelte');
    expect(loadDownloadedMission).toHaveBeenCalledWith([{ lat: 1, lon: 2 }]);
  });

  it('dispatches log_list', async () => {
    await fire({ type: 'log_list', logs: [{ id: 1 }] });
    const { setLogList } = await import('./logStore.svelte');
    expect(setLogList).toHaveBeenCalledWith([{ id: 1 }]);
  });

  it('dispatches log_progress', async () => {
    await fire({ type: 'log_progress', received: 100, total: 1000 });
    const { updateDownloadProgress } = await import('./logStore.svelte');
    expect(updateDownloadProgress).toHaveBeenCalledWith(100, 1000);
  });

  it('dispatches log_complete', async () => {
    await fire({ type: 'log_complete', id: 5, data: 'base64data', size: 1024 });
    const { completeDownload } = await import('./logStore.svelte');
    expect(completeDownload).toHaveBeenCalledWith(5, 'base64data', 1024);
    const { addToast } = await import('./stores.svelte');
    expect(vi.mocked(addToast).mock.calls.at(-1)).toEqual(['toast.logDone', 'success']);
  });

  it('log_complete with truncated=true delivers the file but toasts an error, not success', async () => {
    // truncated covers the count==0 EOF sentinel, stall give-up, and detected
    // frame-loss holes — a success toast here would silently bless a
    // corrupted file (the WebSerial path already surfaces the reason).
    await fire({ type: 'log_complete', id: 5, data: 'base64data', size: 1024, truncated: true });
    const { completeDownload } = await import('./logStore.svelte');
    expect(completeDownload).toHaveBeenCalledWith(5, 'base64data', 1024); // partial data still delivered
    const { addToast } = await import('./stores.svelte');
    const last = vi.mocked(addToast).mock.calls.at(-1)!;
    expect(last[0]).toBe('toast.logDoneTrunc');
    expect(last[1]).toBe('error');
  });

  it('dispatches log_chunk to appendLogChunk', async () => {
    await fire({ type: 'log_chunk', id: 5, ofs: 0, data: 'YWJj' });
    const { appendLogChunk } = await import('./logStore.svelte');
    expect(appendLogChunk).toHaveBeenCalledWith(5, 0, 'YWJj');
  });

  it('dispatches inspector', async () => {
    await fire({ type: 'inspector', messages: [{ id: 1 }] });
    const { updateInspector } = await import('./inspectorStore.svelte');
    expect(updateInspector).toHaveBeenCalledWith([{ id: 1 }]);
  });

  it('dispatches console_output', async () => {
    await fire({ type: 'console_output', text: 'hello' });
    const { appendConsole } = await import('./inspectorStore.svelte');
    expect(appendConsole).toHaveBeenCalledWith('hello');
  });

  it('handles malformed JSON gracefully', async () => {
    await freshConnect();
    mockWs.onopen?.(new Event('open'));
    expect(() => {
      mockWs.onmessage?.(new MessageEvent('message', { data: 'not json{{{' }));
    }).not.toThrow();
  });
});

describe('sendMessage', () => {
  it('sends JSON when socket is open', async () => {
    const mod = await freshConnect();
    mockWs.onopen?.(new Event('open'));
    mod.sendMessage({ type: 'disconnect' });
    expect(mockWs.send).toHaveBeenCalledWith(JSON.stringify({ type: 'disconnect' }));
  });

  it('shows toast for command when disconnected', async () => {
    const mod = await freshConnect();
    mockWs.readyState = 3;
    mod.sendMessage({ type: 'command', cmd: 'arm', param: 1 });
    const { addToast } = await import('./stores.svelte');
    expect(addToast).toHaveBeenCalled();
  });
});

describe('helper functions', () => {
  it('sendConnect sends connect message', async () => {
    const mod = await freshConnect();
    mockWs.onopen?.(new Event('open'));
    mod.sendConnect('udp:14550', 57600, 'standard');
    expect(mockWs.send).toHaveBeenCalledWith(expect.stringContaining('"type":"connect"'));
  });

  it('sendDisconnect sends disconnect message', async () => {
    const mod = await freshConnect();
    mockWs.onopen?.(new Event('open'));
    mod.sendDisconnect();
    expect(mockWs.send).toHaveBeenCalledWith(JSON.stringify({ type: 'disconnect' }));
  });

  it('sendCommand sends command with data', async () => {
    const mod = await freshConnect();
    mockWs.onopen?.(new Event('open'));
    mod.sendCommand('arm', 1, { force: true });
    const lastCall = mockWs.send.mock.calls[mockWs.send.mock.calls.length - 1][0];
    const sent = JSON.parse(lastCall);
    expect(sent.type).toBe('command');
    expect(sent.cmd).toBe('arm');
    expect(sent.param).toBe(1);
    expect(sent.force).toBe(true);
  });
});
