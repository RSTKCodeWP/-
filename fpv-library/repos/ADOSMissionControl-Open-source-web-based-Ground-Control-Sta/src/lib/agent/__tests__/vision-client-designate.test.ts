import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { VisionAgentClient } from "@/lib/agent/vision-client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("VisionAgentClient.designate", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs the designate body with the auth header and parses the result", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ designated: true, track_id: 7, camera_id: "cam-0" }),
    );
    const client = new VisionAgentClient("http://drone.local:8080", "secret-key");

    const res = await client.designate(
      "cam-0",
      { x: 10, y: 20, width: 30, height: 40 },
      { classLabel: "person", confidence: 0.8 },
    );

    expect(res).toEqual({ designated: true, trackId: 7 });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://drone.local:8080/api/vision/designate");
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers["X-ADOS-Key"]).toBe("secret-key");
    expect(headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual({
      camera_id: "cam-0",
      bbox: { x: 10, y: 20, width: 30, height: 40 },
      class_label: "person",
      confidence: 0.8,
    });
  });

  it("omits optional fields + auth header when not given, and reports no lock", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ designated: false, track_id: null }),
    );
    const client = new VisionAgentClient("http://drone.local:8080");

    const res = await client.designate("cam-1", {
      x: 0,
      y: 0,
      width: 5,
      height: 5,
    });

    expect(res).toEqual({ designated: false, trackId: null });
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body.class_label).toBeUndefined();
    expect(body.confidence).toBeUndefined();
    const headers = init.headers as Record<string, string>;
    expect(headers["X-ADOS-Key"]).toBeUndefined();
  });

  it("throws on a non-ok response", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: "vision engine unavailable" }, 503),
    );
    const client = new VisionAgentClient("http://drone.local:8080");
    await expect(
      client.designate("cam-0", { x: 0, y: 0, width: 1, height: 1 }),
    ).rejects.toThrow();
  });
});
