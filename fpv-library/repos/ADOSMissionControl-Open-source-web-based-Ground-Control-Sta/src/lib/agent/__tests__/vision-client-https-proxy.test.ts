/**
 * Tests the HTTPS-LAN-safe READ path of `VisionAgentClient`. On an HTTPS
 * origin the model-registry reads (list / download / status) must route
 * through Mission Control's own `/api/lan-pair/vision-models` proxy (the
 * browser blocks a direct fetch to the plain-HTTP LAN agent under mixed
 * content), symmetric with the write seam; on an HTTP origin they stay direct.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { VisionAgentClient } from "@/lib/agent/vision-client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Override window.location.protocol for the constructor's origin check. */
function setProtocol(protocol: "http:" | "https:") {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...window.location, protocol },
  });
}

describe("VisionAgentClient HTTPS read proxy", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  const realLocation = window.location;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: realLocation,
    });
  });

  it("listModels routes through the proxy with op=list on an HTTPS origin", async () => {
    setProtocol("https:");
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        registry: [],
        installed: [],
        custom: [],
        active: null,
        cache: { used_bytes: 0, max_bytes: 0, used_mb: 0, max_mb: 0 },
      }),
    );
    const client = new VisionAgentClient("http://drone.local:8080", "k");
    await client.listModels();

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/lan-pair/vision-models");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      host: "http://drone.local:8080",
      apiKey: "k",
      op: "list",
      modelId: undefined,
    });
  });

  it("download routes through the proxy carrying op=download + the model id", async () => {
    setProtocol("https:");
    fetchMock.mockResolvedValueOnce(jsonResponse({ status: "ok" }));
    const client = new VisionAgentClient("http://drone.local:8080", "k");
    await client.download("yolov8n");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/lan-pair/vision-models");
    expect(JSON.parse(init.body as string)).toMatchObject({
      op: "download",
      modelId: "yolov8n",
    });
  });

  it("modelStatus routes through the proxy carrying op=status + the model id", async () => {
    setProtocol("https:");
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ installed: true, download: null }),
    );
    const client = new VisionAgentClient("http://drone.local:8080", "k");
    const res = await client.modelStatus("yolov8n");
    expect(res.installed).toBe(true);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/lan-pair/vision-models");
    expect(JSON.parse(init.body as string)).toMatchObject({
      op: "status",
      modelId: "yolov8n",
    });
  });

  it("stays on the direct LAN fetch on an HTTP origin (no proxy)", async () => {
    setProtocol("http:");
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        registry: [],
        installed: [],
        cache: { used_bytes: 0, max_bytes: 0, used_mb: 0, max_mb: 0 },
      }),
    );
    const client = new VisionAgentClient("http://drone.local:8080", "k");
    await client.listModels();

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://drone.local:8080/api/vision/models");
  });
});
