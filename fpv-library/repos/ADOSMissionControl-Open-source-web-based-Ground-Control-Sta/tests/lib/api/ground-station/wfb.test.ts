import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setTxPower } from "@/lib/api/ground-station/wfb";
import type { RequestContext } from "@/lib/api/ground-station/request";

describe("setTxPower", () => {
  let originalFetch: typeof fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  function makeCtx(): RequestContext {
    return { baseUrl: "http://gs.test.local", apiKey: "test-key" };
  }

  it("issues PUT with correct URL, method, headers, and JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          requested_dbm: 22,
          effective_dbm: 22,
          tx_power_max_dbm: 30,
        }),
        { status: 200 },
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const result = await setTxPower(makeCtx(), 22);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://gs.test.local/api/wfb/tx-power");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({ tx_power_dbm: 22 });

    const headers = init.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers["X-ADOS-Key"]).toBe("test-key");

    expect(result).toEqual({
      requested_dbm: 22,
      effective_dbm: 22,
      tx_power_max_dbm: 30,
    });
  });

  it("returns a clamped effective value when the agent reports it", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          requested_dbm: 40,
          effective_dbm: 30,
          tx_power_max_dbm: 30,
        }),
        { status: 200 },
      ),
    ) as unknown as typeof fetch;

    const result = await setTxPower(makeCtx(), 40);

    expect(result.effective_dbm).toBe(30);
    expect(result.tx_power_max_dbm).toBe(30);
  });

  it("propagates a null effective value when the radio is absent", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          requested_dbm: 18,
          effective_dbm: null,
          tx_power_max_dbm: 30,
        }),
        { status: 200 },
      ),
    ) as unknown as typeof fetch;

    const result = await setTxPower(makeCtx(), 18);

    expect(result.effective_dbm).toBeNull();
  });

  it("throws a GroundStationApiError on non-2xx response", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response("driver rejected value", { status: 400 }),
    ) as unknown as typeof fetch;

    await expect(setTxPower(makeCtx(), 99)).rejects.toThrowError(
      /Ground station API 400/,
    );
  });

  it("omits the X-ADOS-Key header when no api key is provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          requested_dbm: 10,
          effective_dbm: 10,
          tx_power_max_dbm: 30,
        }),
        { status: 200 },
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await setTxPower({ baseUrl: "http://gs.test.local", apiKey: null }, 10);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["X-ADOS-Key"]).toBeUndefined();
  });
});
