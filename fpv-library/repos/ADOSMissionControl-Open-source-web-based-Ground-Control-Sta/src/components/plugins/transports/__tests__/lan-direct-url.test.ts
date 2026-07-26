/**
 * @module lan-direct-url.test
 * @description Unit coverage for the registry-source install transport.
 * Mocks the global `fetch` and the AbortController-based timeouts so
 * the test runs deterministically.
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import {
  installLanDirectFromUrl,
} from "../lan-direct-url";
import { LanDirectError } from "../lan-direct";

const baseInputs = {
  agentUrl: "http://drone.local:8080",
  pairingKey: "test-key",
  url: "https://example.invalid/archive.adosplug",
  expectedSha256: "deadbeef",
  grantedPermissions: ["hardware.usb.uvc"],
  jobId: "job-1",
  pluginId: "test.plugin",
  pluginName: "Test Plugin",
  deviceId: "device-1",
};

describe("installLanDirectFromUrl", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("posts JSON to /api/plugins/install_from_url with the URL and SHA pin", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const body = JSON.parse((init?.body as string) ?? "{}");
      expect(body.url).toBe(baseInputs.url);
      expect(body.expected_sha256).toBe(baseInputs.expectedSha256);
      expect(body.requested_permissions).toEqual(baseInputs.grantedPermissions);
      expect(body.job_id).toBe(baseInputs.jobId);
      expect(body.from_catalog).toBe(false);
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await installLanDirectFromUrl(baseInputs);
    expect(result.transport).toBe("lan");
    expect(result.jobId).toBe(baseInputs.jobId);
    expect(result.pluginId).toBe(baseInputs.pluginId);
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toBe(
      "http://drone.local:8080/api/plugins/install_from_url",
    );
  });

  it("forwards from_catalog=true when the dialog flags a catalog source", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const body = JSON.parse((init?.body as string) ?? "{}");
      expect(body.from_catalog).toBe(true);
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    await installLanDirectFromUrl({ ...baseInputs, fromCatalog: true });
  });

  it("throws LanDirectError with cause=server-4xx on 4xx", async () => {
    const fetchMock = vi.fn(async () =>
      new Response("bad request", { status: 400 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(installLanDirectFromUrl(baseInputs)).rejects.toMatchObject({
      cause: "server-4xx",
    });
  });

  it("throws LanDirectError with cause=server-5xx on 5xx (failover-eligible)", async () => {
    const fetchMock = vi.fn(async () =>
      new Response("upstream busted", { status: 503 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    try {
      await installLanDirectFromUrl(baseInputs);
      throw new Error("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(LanDirectError);
      expect((err as LanDirectError).cause).toBe("server-5xx");
    }
  });

  it("throws LanDirectError with cause=network on TypeError (failover-eligible)", async () => {
    const fetchMock = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    vi.stubGlobal("fetch", fetchMock);
    try {
      await installLanDirectFromUrl(baseInputs);
      throw new Error("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(LanDirectError);
      expect((err as LanDirectError).cause).toBe("network");
    }
  });

  it("throws LanDirectError with cause=timeout on AbortError (failover-eligible)", async () => {
    const fetchMock = vi.fn(async () => {
      throw new DOMException("aborted", "AbortError");
    });
    vi.stubGlobal("fetch", fetchMock);
    try {
      await installLanDirectFromUrl(baseInputs);
      throw new Error("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(LanDirectError);
      expect((err as LanDirectError).cause).toBe("timeout");
    }
  });

  it("throws auth-missing when pairing key is empty", async () => {
    try {
      await installLanDirectFromUrl({ ...baseInputs, pairingKey: "" });
      throw new Error("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(LanDirectError);
      expect((err as LanDirectError).cause).toBe("auth-missing");
    }
  });
});
