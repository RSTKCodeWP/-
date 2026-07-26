// apps/desktop/src/main/testing/mcp-server.test.ts
import { describe, it, expect, afterEach, vi } from 'vitest';

// tools.ts (transitively imported by mcp-server) pulls in electron at module load.
vi.mock('electron', () => ({
  BrowserWindow: class {},
  ipcMain: { on: () => {}, removeListener: () => {} },
  app: { on: () => {} },
}));

import { startMcpServer, stopMcpServer } from './mcp-server';

afterEach(() => {
  stopMcpServer();
});

/**
 * Open an SSE connection and read until the `endpoint` event arrives,
 * returning the HTTP status, the session-scoped POST path, and the live
 * reader so the caller can keep consuming `message` events.
 */
async function openSse(baseUrl: string): Promise<{
  status: number;
  endpointPath: string | null;
  next: () => Promise<string | null>;
}> {
  const res = await fetch(`${baseUrl}/sse`, { headers: { Accept: 'text/event-stream' } });
  if (!res.ok || !res.body) {
    return { status: res.status, endpointPath: null, next: async () => null };
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  // Pull SSE events as (eventType, data) until a predicate matches.
  async function readEvent(): Promise<{ event: string; data: string } | null> {
    while (true) {
      const sep = buffer.indexOf('\n\n');
      if (sep !== -1) {
        const raw = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        let event = 'message';
        let data = '';
        for (const line of raw.split('\n')) {
          if (line.startsWith('event: ')) event = line.slice(7).trim();
          else if (line.startsWith('data: ')) data += line.slice(6);
        }
        return { event, data };
      }
      const { done, value } = await reader.read();
      if (done) return null;
      buffer += decoder.decode(value, { stream: true });
    }
  }

  let endpointPath: string | null = null;
  while (true) {
    const evt = await readEvent();
    if (!evt) break;
    if (evt.event === 'endpoint') {
      endpointPath = evt.data;
      break;
    }
  }

  return {
    status: res.status,
    endpointPath,
    next: async () => {
      const evt = await readEvent();
      return evt?.event === 'message' ? evt.data : evt ? '' : null;
    },
  };
}

const INIT = (id: number) =>
  JSON.stringify({
    jsonrpc: '2.0',
    id,
    method: 'initialize',
    params: {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: { name: `client-${id}`, version: '1.0.0' },
    },
  });

describe('mcp-server multi-session', () => {
  it('accepts two concurrent SSE clients and routes each independently', async () => {
    const { port } = await startMcpServer();
    const base = `http://127.0.0.1:${port}`;

    const a = await openSse(base);
    const b = await openSse(base);

    // Both clients must connect (the old single-client server 409'd the second).
    expect(a.status).toBe(200);
    expect(b.status).toBe(200);
    expect(a.endpointPath).toBeTruthy();
    expect(b.endpointPath).toBeTruthy();

    // Each client gets its own distinct session.
    const sidA = new URLSearchParams(a.endpointPath!.split('?')[1]).get('sessionId');
    const sidB = new URLSearchParams(b.endpointPath!.split('?')[1]).get('sessionId');
    expect(sidA).toBeTruthy();
    expect(sidB).toBeTruthy();
    expect(sidA).not.toBe(sidB);

    // initialize over each session; the JSON-RPC reply comes back on that
    // session's SSE stream, proving messages route to the right transport.
    const postA = await fetch(`${base}${a.endpointPath}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: INIT(101),
    });
    const postB = await fetch(`${base}${b.endpointPath}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: INIT(202),
    });
    expect(postA.status).toBe(202);
    expect(postB.status).toBe(202);

    const replyA = JSON.parse((await a.next())!);
    const replyB = JSON.parse((await b.next())!);
    expect(replyA.id).toBe(101);
    expect(replyB.id).toBe(202);
    expect(replyA.result?.serverInfo?.name).toBe('ardudeck');
    expect(replyB.result?.serverInfo?.name).toBe('ardudeck');
  });
});
