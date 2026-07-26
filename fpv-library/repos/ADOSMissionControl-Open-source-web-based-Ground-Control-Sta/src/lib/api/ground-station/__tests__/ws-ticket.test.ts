/**
 * @license GPL-3.0-only
 *
 * Unit tests for the one-shot WebSocket ticket mint shared by every
 * authenticated WS dial: an unpaired context returns null (open
 * posture, no ticket), a paired context POSTs the pairing key + scope
 * and returns the ticket, and a non-OK or malformed response throws so
 * the caller can fall through to a legacy / relayed path.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mintWsTicket, WS_TICKET_PROTOCOL } from "../ws-ticket";
import type { RequestContext } from "../request";

describe("mintWsTicket", () => {
  const origFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = origFetch;
  });

  it("returns null without calling fetch when the context has no key", async () => {
    const fetchSpy = vi.fn();
    globalThis.fetch = fetchSpy as unknown as typeof fetch;
    const ctx: RequestContext = { baseUrl: "http://drone.local:8080", apiKey: null };

    const ticket = await mintWsTicket(ctx, "gs.mavlink_ws");

    expect(ticket).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("POSTs the pairing key + scope and returns the minted ticket", async () => {
    const fetchSpy = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        ok: true,
        ticket: "tok-123",
        scope: "gs.mavlink_ws",
        expires_at: 9999,
      }),
    }));
    globalThis.fetch = fetchSpy as unknown as typeof fetch;
    const ctx: RequestContext = {
      baseUrl: "http://drone.local:8080/",
      apiKey: "key-abc",
    };

    const ticket = await mintWsTicket(ctx, "gs.mavlink_ws");

    expect(ticket).toBe("tok-123");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    // Trailing slash on baseUrl is stripped before appending the route.
    expect(url).toBe("http://drone.local:8080/api/_ws/ticket");
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers["X-ADOS-Key"]).toBe("key-abc");
    expect(JSON.parse(init.body as string)).toEqual({ scope: "gs.mavlink_ws" });
  });

  it("throws on a non-OK mint response", async () => {
    const fetchSpy = vi.fn(async () => ({
      ok: false,
      status: 403,
      json: async () => ({}),
    }));
    globalThis.fetch = fetchSpy as unknown as typeof fetch;
    const ctx: RequestContext = { baseUrl: "http://drone.local:8080", apiKey: "k" };

    await expect(mintWsTicket(ctx, "gs.mavlink_ws")).rejects.toThrow(/HTTP 403/);
  });

  it("throws when the response omits the ticket", async () => {
    const fetchSpy = vi.fn(async () => ({
      ok: true,
      json: async () => ({ ok: true, scope: "gs.mavlink_ws", expires_at: 1 }),
    }));
    globalThis.fetch = fetchSpy as unknown as typeof fetch;
    const ctx: RequestContext = { baseUrl: "http://drone.local:8080", apiKey: "k" };

    await expect(mintWsTicket(ctx, "gs.mavlink_ws")).rejects.toThrow(/missing ticket/);
  });

  it("exposes the subprotocol marker the agent echoes back", () => {
    expect(WS_TICKET_PROTOCOL).toBe("ados-ws-ticket");
  });
});
