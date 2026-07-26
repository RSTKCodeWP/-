import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchWithTimeout } from "@/lib/net/fetch-with-timeout";

describe("fetchWithTimeout", () => {
  let originalFetch: typeof fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("returns the upstream response on success", async () => {
    const response = new Response("ok", { status: 200 });
    globalThis.fetch = vi.fn().mockResolvedValue(response);

    const res = await fetchWithTimeout("https://example.com");
    expect(res.status).toBe(200);
    expect(await res.text()).toBe("ok");
  });

  it("aborts when the timeout fires", async () => {
    globalThis.fetch = vi.fn(
      (_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            const err = new Error("aborted");
            err.name = "AbortError";
            reject(err);
          });
        }),
    );

    await expect(
      fetchWithTimeout("https://example.com", { timeoutMs: 10 }),
    ).rejects.toMatchObject({ name: "AbortError" });
  });

  it("aborts when the upstream signal aborts", async () => {
    const upstream = new AbortController();
    globalThis.fetch = vi.fn(
      (_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            const err = new Error("aborted");
            err.name = "AbortError";
            reject(err);
          });
        }),
    );

    setTimeout(() => upstream.abort(), 5);

    await expect(
      fetchWithTimeout("https://example.com", {
        upstreamSignal: upstream.signal,
        timeoutMs: 10_000,
      }),
    ).rejects.toMatchObject({ name: "AbortError" });
  });

  it("aborts immediately when upstream signal is already aborted", async () => {
    const upstream = new AbortController();
    upstream.abort();

    globalThis.fetch = vi.fn(
      (_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          if (init?.signal?.aborted) {
            const err = new Error("aborted");
            err.name = "AbortError";
            reject(err);
            return;
          }
          init?.signal?.addEventListener("abort", () => {
            const err = new Error("aborted");
            err.name = "AbortError";
            reject(err);
          });
        }),
    );

    await expect(
      fetchWithTimeout("https://example.com", {
        upstreamSignal: upstream.signal,
        timeoutMs: 10_000,
      }),
    ).rejects.toMatchObject({ name: "AbortError" });
  });

  it("clears the timer after a fast successful response", async () => {
    const response = new Response("ok", { status: 200 });
    globalThis.fetch = vi.fn().mockResolvedValue(response);
    const clearSpy = vi.spyOn(globalThis, "clearTimeout");

    await fetchWithTimeout("https://example.com", { timeoutMs: 5_000 });
    expect(clearSpy).toHaveBeenCalled();
    clearSpy.mockRestore();
  });

  it("does not abort upstream signal when the request finishes first", async () => {
    const upstream = new AbortController();
    const response = new Response("ok", { status: 200 });
    globalThis.fetch = vi.fn().mockResolvedValue(response);

    const res = await fetchWithTimeout("https://example.com", {
      upstreamSignal: upstream.signal,
    });

    expect(res.status).toBe(200);
    expect(upstream.signal.aborted).toBe(false);
  });

  it("propagates non-abort fetch errors verbatim", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("network down"));
    await expect(
      fetchWithTimeout("https://example.com"),
    ).rejects.toThrow("network down");
  });
});
