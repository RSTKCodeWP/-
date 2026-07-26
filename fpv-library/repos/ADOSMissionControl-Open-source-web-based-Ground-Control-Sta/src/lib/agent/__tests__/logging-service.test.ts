/**
 * @module logging-service.test
 * @description Unit tests for the durable-store reader's three-tier
 * transport resolution (LAN-direct → proxy → legacy), envelope
 * normalisation, legacy shape mapping, keyset pagination, hard-error
 * non-cascade, and streamed export.
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { LoggingService } from "../agent-client/logging";
import type { RequestContext } from "../agent-client/transport";

const CTX: RequestContext = {
  baseUrl: "http://drone.local:8080",
  apiKey: "test-key",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function envelope(data: unknown[], next: string | null = null, source = "logd") {
  return {
    data,
    page: { next_cursor: next, count: data.length },
    meta: { source, v: 1, ts: "2026-06-02T10:00:00+05:30", db_lag_ms: 7 },
  };
}

const LOGD_ROW = {
  ts: "2026-06-02T10:00:00+05:30",
  ts_us: 1_780_000_000_000_000,
  id: "row-1",
  level: "info",
  message: "video started",
  source: "ados-video",
};

describe("LoggingService transport resolution", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("serves from the LAN-direct tier and reports source=logd", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(envelope([LOGD_ROW])));
    const svc = new LoggingService(CTX);
    const res = await svc.query();
    expect(res.meta.source).toBe("logd");
    expect(res.data).toHaveLength(1);
    expect(res.meta.db_lag_ms).toBe(7);
    // Direct tier means :8090/v1.
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain(":8090/v1/query");
    // Auth header carried.
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-ADOS-Key"]).toBe("test-key");
  });

  it("falls back to the proxy tier on a 404 from direct", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ error: "not found" }, 404))
      .mockResolvedValueOnce(jsonResponse(envelope([LOGD_ROW], null, "proxy")));
    const svc = new LoggingService(CTX);
    const res = await svc.query();
    expect(res.meta.source).toBe("proxy");
    const proxyUrl = fetchMock.mock.calls[1][0] as string;
    expect(proxyUrl).toContain(":8080/api/v2/observability/v1/query");
  });

  it("falls back to the legacy tier and normalises the flat array", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ error: "x" }, 404)) // direct
      .mockResolvedValueOnce(jsonResponse({ error: "x" }, 502)) // proxy
      .mockResolvedValueOnce(
        jsonResponse([
          { timestamp: "2026-06-02T09:59:00+05:30", level: "warn", logger: "api", msg: "slow" },
        ]),
      );
    const svc = new LoggingService(CTX);
    const res = await svc.query();
    expect(res.meta.source).toBe("legacy");
    expect(res.data).toHaveLength(1);
    const row = res.data[0];
    expect(row.level).toBe("warning"); // warn → warning
    expect(row.message).toBe("slow");
    expect(row.source).toBe("api"); // logger → source
    expect(typeof row.ts_us).toBe("number");
    const legacyUrl = fetchMock.mock.calls[2][0] as string;
    expect(legacyUrl).toContain(":8080/api/logs");
  });

  it("throws (does not cascade) on a hard 401 from the direct tier", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ error: "unauth" }, 401));
    const svc = new LoggingService(CTX);
    await expect(svc.query()).rejects.toThrow(/401/);
    // Only one call — no cascade past a hard error.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("throws when every tier is unavailable", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({}, 503))
      .mockResolvedValueOnce(jsonResponse({}, 503))
      .mockResolvedValueOnce(jsonResponse({}, 503));
    const svc = new LoggingService(CTX);
    await expect(svc.query()).rejects.toThrow(/logd unavailable/);
  });

  it("cascades on a network error (rejected fetch)", async () => {
    fetchMock
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(jsonResponse(envelope([LOGD_ROW], null, "proxy")));
    const svc = new LoggingService(CTX);
    const res = await svc.query();
    expect(res.meta.source).toBe("proxy");
  });

  it("re-probes the direct tier first even after settling on proxy", async () => {
    // First call settles on proxy.
    fetchMock
      .mockResolvedValueOnce(jsonResponse({}, 404))
      .mockResolvedValueOnce(jsonResponse(envelope([LOGD_ROW], null, "proxy")));
    const svc = new LoggingService(CTX);
    await svc.query();
    // Second call: direct is back up.
    fetchMock.mockResolvedValueOnce(jsonResponse(envelope([LOGD_ROW])));
    const res = await svc.query();
    expect(res.meta.source).toBe("logd");
    const lastUrl = fetchMock.mock.calls[fetchMock.mock.calls.length - 1][0] as string;
    expect(lastUrl).toContain(":8090/v1/query");
  });
});

describe("LoggingService pagination + aggregate + export", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("walks every page of queryAll until the cursor is null", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(envelope([{ ...LOGD_ROW, id: "a" }], "cur1")))
      .mockResolvedValueOnce(jsonResponse(envelope([{ ...LOGD_ROW, id: "b" }], null)));
    const svc = new LoggingService(CTX);
    const ids: string[] = [];
    for await (const row of svc.queryAll()) ids.push(row.id);
    expect(ids).toEqual(["a", "b"]);
    // Second page carried the cursor.
    const secondUrl = fetchMock.mock.calls[1][0] as string;
    expect(secondUrl).toContain("cursor=cur1");
  });

  it("builds the aggregate query with repeated metric params", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        envelope([
          { ts: "t", ts_us: 1, metric: "system.cpu_percent", value: 33 },
        ]),
      ),
    );
    const svc = new LoggingService(CTX);
    const res = await svc.aggregate({
      metric: ["system.cpu_percent", "system.memory_percent"],
      bucket: "1m",
      agg: "avg",
    });
    expect(res.data).toHaveLength(1);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("metric=system.cpu_percent");
    expect(url).toContain("metric=system.memory_percent");
    expect(url).toContain("bucket=1m");
    expect(url).toContain("agg=avg");
  });

  it("returns an empty aggregate on a legacy agent rather than throwing", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({}, 404)) // direct
      .mockResolvedValueOnce(jsonResponse({}, 404)) // proxy
      .mockResolvedValueOnce(jsonResponse([])); // legacy
    const svc = new LoggingService(CTX);
    const res = await svc.aggregate({ metric: ["system.cpu_percent"] });
    expect(res.data).toEqual([]);
    expect(res.meta.source).toBe("legacy");
  });

  it("streams an export with the format suffix and never hits legacy", async () => {
    const body = '{"id":"x"}\n';
    fetchMock.mockResolvedValueOnce(
      new Response(body, { status: 200 }),
    );
    const svc = new LoggingService(CTX);
    const { stream, format } = await svc.export({ format: "jsonl" });
    expect(format).toBe("jsonl");
    const text = await new Response(stream).text();
    expect(text).toBe(body);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain(":8090/v1/export");
    expect(url).toContain("format=jsonl");
  });

  it("throws export unavailable when no streaming tier answers", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({}, 404)) // direct
      .mockResolvedValueOnce(jsonResponse({}, 503)); // proxy
    const svc = new LoggingService(CTX);
    await expect(svc.export()).rejects.toThrow(/export unavailable/);
  });
});

describe("LoggingService stats + healthz", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("coerces a partial stats body with safe defaults", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        envelopeStats({
          db: { file_size_mb: 12.5, row_counts: { logs: 100 } },
          ingest: { rows_per_sec: 9 },
        }),
      ),
    );
    const svc = new LoggingService(CTX);
    const stats = await svc.stats();
    expect(stats.db.file_size_mb).toBe(12.5);
    expect(stats.db.wal_size_mb).toBe(0);
    expect(stats.db.row_counts.logs).toBe(100);
    expect(stats.ingest.rows_per_sec).toBe(9);
    expect(stats.ingest.queue_depth).toBe(0);
    expect(stats.sync.synced_rows).toBe(0);
    expect(stats.source).toBe("logd");
  });

  it("returns ok=false from healthz when no tier answers instead of throwing", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({}, 503))
      .mockResolvedValueOnce(jsonResponse({}, 503))
      .mockResolvedValueOnce(jsonResponse({}, 503));
    const svc = new LoggingService(CTX);
    const health = await svc.healthz();
    expect(health.ok).toBe(false);
  });
});

// stats is not wrapped in the {data,page,meta} envelope, so build a raw body.
function envelopeStats(body: Record<string, unknown>): Record<string, unknown> {
  return body;
}
