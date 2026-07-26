import { afterEach, describe, expect, it, vi } from "vitest";

import { parseJsonMessage } from "./realWsClient";

/* The real-service WS client parses the wire exactly as the Python service emits it
 * (loop.py serve(): JSON channel = model_dump_json() strings, one DetectionMessage then any
 * ContactRecords per frame). parseJsonMessage is the pure, tested boundary — it validates
 * the discriminator + shape so a malformed message fails loudly here, not as a wrong pin. */

afterEach(() => vi.restoreAllMocks());

describe("parseJsonMessage", () => {
  it("parses a DetectionMessage from its JSON text", () => {
    const text = JSON.stringify({
      type: "detection",
      frame_id: 42,
      timestamp: 1.4,
      boxes: [{ box_xyxy: [1, 2, 3, 4], conf: 0.9, cls: "person" }],
    });
    const m = parseJsonMessage(text);
    expect(m?.type).toBe("detection");
    expect(m?.frame_id).toBe(42);
  });

  it("parses a ContactRecord, preserving null lat/lon for a CUE_ONLY fix", () => {
    const text = JSON.stringify({
      type: "contact",
      frame_id: 7,
      track_id: 19,
      lat: null,
      lon: null,
      r95_m: 0,
      actionability_class: "CUE_ONLY",
      semi_major_m: 0,
      semi_minor_m: 0,
      orientation_deg: 0,
      priority_tier: "candidate",
      convergence_state: "CONVERGING",
      heading_limited: true,
      aspect_spread_deg: 0,
      detection_conf: 0.6,
      localization_conf: 0.2,
      mc_reject_fraction: 0,
      moving_suspected: false,
      age_frames: 1,
    });
    const m = parseJsonMessage(text);
    expect(m?.type).toBe("contact");
    if (m?.type === "contact") {
      expect(m.lat).toBeNull();
      expect(m.actionability_class).toBe("CUE_ONLY");
    }
  });

  it("returns null on malformed JSON (fails safe, doesn't throw a wrong coordinate)", () => {
    expect(parseJsonMessage("{not json")).toBeNull();
  });

  it("returns null on an unknown discriminator", () => {
    expect(parseJsonMessage(JSON.stringify({ type: "telemetry", x: 1 }))).toBeNull();
  });

  it("rejects a contact missing required fields", () => {
    expect(parseJsonMessage(JSON.stringify({ type: "contact", frame_id: 1 }))).toBeNull();
  });
});

describe("RealWsClient reconnect", () => {
  it("retries the connection when the socket closes before the service is ready", async () => {
    vi.useFakeTimers();
    const opened: string[] = [];
    // a fake WebSocket that records constructions and lets us drive close events
    const sockets: FakeWs[] = [];
    class FakeWs {
      onopen: (() => void) | null = null;
      onclose: (() => void) | null = null;
      onerror: (() => void) | null = null;
      onmessage: ((e: { data: unknown }) => void) | null = null;
      binaryType = "";
      constructor(public url: string) {
        opened.push(url);
        sockets.push(this);
      }
      close() {}
    }
    vi.stubGlobal("WebSocket", FakeWs as unknown as typeof WebSocket);

    const { RealWsClient } = await import("./realWsClient");
    const client = new RealWsClient(
      { binaryUrl: "ws://x:1", jsonUrl: "ws://x:2" },
      { onFrame: () => {}, onJson: () => {} },
    );
    client.connect();
    const firstCount = opened.length; // 2 (binary + json)
    expect(firstCount).toBe(2);

    // simulate the service not ready: both sockets close immediately
    sockets.forEach((s) => s.onclose?.());
    await vi.advanceTimersByTimeAsync(2000); // past the retry backoff

    expect(opened.length).toBeGreaterThan(firstCount); // it retried

    client.close();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("sendPromote writes a promote command to the JSON socket (operator → service)", async () => {
    const sent: string[] = [];
    class FakeWs {
      static OPEN = 1;
      onopen: (() => void) | null = null;
      onclose: (() => void) | null = null;
      onerror: (() => void) | null = null;
      onmessage: ((e: { data: unknown }) => void) | null = null;
      binaryType = "";
      readyState = 1; // OPEN
      constructor(public url: string) {}
      send(s: string) {
        if (this.url.endsWith(":2")) sent.push(s); // the json url in this test
      }
      close() {}
    }
    vi.stubGlobal("WebSocket", FakeWs as unknown as typeof WebSocket);
    const { RealWsClient } = await import("./realWsClient");
    const client = new RealWsClient(
      { binaryUrl: "ws://x:1", jsonUrl: "ws://x:2" },
      { onFrame: () => {}, onJson: () => {} },
    );
    client.connect();
    client.sendPromote(42);
    expect(sent).toHaveLength(1);
    expect(JSON.parse(sent[0])).toEqual({ type: "promote", track_id: 42 });
    client.close();
    vi.unstubAllGlobals();
  });
});
