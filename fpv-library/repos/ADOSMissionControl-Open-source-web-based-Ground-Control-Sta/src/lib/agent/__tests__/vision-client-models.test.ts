import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { VisionAgentClient } from "@/lib/agent/vision-client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("VisionAgentClient model management", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("coerces custom[] and active in listModels, tolerating snake_case + missing fields", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        registry: [
          {
            id: "yolov8n",
            name: "YOLOv8n",
            description: "d",
            task: "detection",
            variants: [{ runtime: "onnx", min_tops: 0 }],
          },
        ],
        installed: [
          { id: "yolov8n", filename: "y.onnx", size_bytes: 10, format: "onnx" },
        ],
        custom: [
          {
            id: "c1",
            name: "Custom 1",
            filename: "c.onnx",
            size_bytes: 20,
            format: "onnx",
            head: "yolov8",
            runtime: "onnx",
            classes: ["person", "car"],
            input_w: 320,
            input_h: 320,
            board_match: ["rpi4b"],
            verified: true,
          },
        ],
        active: "yolov8n",
        cache: { used_bytes: 1, max_bytes: 2, used_mb: 3, max_mb: 4 },
      }),
    );
    const client = new VisionAgentClient("http://drone.local:8080", "k");
    const res = await client.listModels();

    expect(res.active).toBe("yolov8n");
    expect(res.custom).toHaveLength(1);
    expect(res.custom[0]).toEqual({
      id: "c1",
      name: "Custom 1",
      filename: "c.onnx",
      sizeBytes: 20,
      format: "onnx",
      head: "yolov8",
      runtime: "onnx",
      classes: ["person", "car"],
      inputWidth: 320,
      inputHeight: 320,
      boardMatch: ["rpi4b"],
      verified: true,
    });
  });

  it("defaults custom[] to [] and active to null on an older agent", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        registry: [],
        installed: [],
        cache: { used_bytes: 0, max_bytes: 0, used_mb: 0, max_mb: 0 },
      }),
    );
    const client = new VisionAgentClient("http://drone.local:8080");
    const res = await client.listModels();
    expect(res.custom).toEqual([]);
    expect(res.active).toBeNull();
  });

  it("PUTs the detector with model_id and the auth header", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ status: "ok", message: "set", model_id: "yolov8n" }),
    );
    const client = new VisionAgentClient("http://drone.local:8080", "secret");
    const res = await client.setActiveDetector("yolov8n");

    expect(res).toEqual({
      status: "ok",
      message: "set",
      modelId: "yolov8n",
    });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://drone.local:8080/api/vision/detector");
    expect(init.method).toBe("PUT");
    const headers = init.headers as Record<string, string>;
    expect(headers["X-ADOS-Key"]).toBe("secret");
    expect(JSON.parse(init.body as string)).toEqual({ model_id: "yolov8n" });
  });

  it("uploads a model multipart with file + JSON metadata", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        status: "ok",
        message: "uploaded",
        model_id: "custom-7",
        verified: false,
      }),
    );
    const client = new VisionAgentClient("http://drone.local:8080", "secret");
    const file = new File([new Uint8Array([1, 2, 3])], "model.onnx", {
      type: "application/octet-stream",
    });
    const res = await client.uploadModel(file, {
      name: "My model",
      classes: ["person"],
      head: "yolov8",
      inputWidth: 640,
      inputHeight: 640,
      runtime: "onnx",
      boardMatch: ["rpi4b"],
    });

    expect(res).toEqual({
      status: "ok",
      message: "uploaded",
      modelId: "custom-7",
      verified: false,
    });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://drone.local:8080/api/vision/models/upload");
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers["X-ADOS-Key"]).toBe("secret");
    const body = init.body as FormData;
    expect(body.get("file")).toBeInstanceOf(File);
    const meta = JSON.parse(body.get("metadata") as string) as Record<
      string,
      unknown
    >;
    expect(meta).toEqual({
      name: "My model",
      classes: ["person"],
      head: "yolov8",
      input_w: 640,
      input_h: 640,
      runtime: "onnx",
      board_match: ["rpi4b"],
    });
  });

  it("reports status:error when the agent rejects a set-active", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ status: "error", message: "model not installed" }),
    );
    const client = new VisionAgentClient("http://drone.local:8080");
    const res = await client.setActiveDetector("missing");
    expect(res.status).toBe("error");
    expect(res.message).toBe("model not installed");
  });
});
