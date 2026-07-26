/**
 * @module logging-push.test
 * @description Verifies LoggingService.pushWindow: the single-path write to
 * the agent REST process, the header + body it sends, the canonical ack it
 * parses, the error on a non-2xx response, and the short-circuit on a cloud
 * (https) origin.
 * @license GPL-3.0-only
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoggingService } from "@/lib/agent/agent-client/logging";
import type { RequestContext } from "@/lib/agent/agent-client/transport";

function makeService(baseUrl: string, apiKey: string | null): LoggingService {
  const ctx: RequestContext = { baseUrl, apiKey };
  return new LoggingService(ctx);
}

describe("LoggingService.pushWindow", () => {
  let originalFetch: typeof fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("POSTs to :8080/api/logs/push with the key and the canonical body", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          window_id: "win_1",
          sha256: "abc123",
          bytes: 4096,
          rows: 142,
          deduped: false,
          synced: true,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const svc = makeService("http://skynode.local:8080", "secret-key");
    const result = await svc.pushWindow({
      session: "7",
      level: "warning",
      text: "boom",
      format: "jsonl.zst",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://skynode.local:8080/api/logs/push");
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers["X-ADOS-Key"]).toBe("secret-key");
    expect(headers["Content-Type"]).toBe("application/json");
    const body = JSON.parse(init.body as string);
    expect(body.session).toBe("7");
    expect(body.level).toBe("warning");
    expect(body.text).toBe("boom");
    expect(body.format).toBe("jsonl.zst");

    expect(result).toEqual({
      window_id: "win_1",
      sha256: "abc123",
      bytes: 4096,
      rows: 142,
      deduped: false,
      synced: true,
    });
  });

  it("defaults format to jsonl.zst when omitted", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({ window_id: "w", sha256: "", bytes: 0, rows: 0, deduped: true, synced: true }),
        { status: 200 },
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const svc = makeService("http://10.0.0.5:8080", null);
    const result = await svc.pushWindow({});
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body.format).toBe("jsonl.zst");
    expect(result.deduped).toBe(true);
    // No key configured: the header must be absent.
    const headers = init.headers as Record<string, string>;
    expect(headers["X-ADOS-Key"]).toBeUndefined();
  });

  it("derives the FastAPI port even when the base url uses a different port", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({ window_id: "w", sha256: "", bytes: 0, rows: 0, deduped: false, synced: true }),
        { status: 200 },
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const svc = makeService("http://skynode.local:9999", "k");
    await svc.pushWindow({});
    const [url] = fetchMock.mock.calls[0] as unknown as [string];
    expect(url).toBe("http://skynode.local:8080/api/logs/push");
  });

  it("throws on a non-2xx response and surfaces the status", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ error: { code: "cloud_logs_disabled" } }), {
        status: 409,
      }),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const svc = makeService("http://skynode.local:8080", "k");
    await expect(svc.pushWindow({})).rejects.toThrow(/409/);
  });

  it("short-circuits on a cloud (https) origin without touching fetch", async () => {
    const fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const svc = makeService("https://drone.example.com", "k");
    await expect(svc.pushWindow({})).rejects.toThrow(/push unavailable/);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
