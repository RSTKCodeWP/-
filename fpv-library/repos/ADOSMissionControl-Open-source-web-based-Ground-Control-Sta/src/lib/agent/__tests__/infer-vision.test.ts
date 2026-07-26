/**
 * @module infer-vision.test
 * @description Unit tests for the vision-capability inference path and the
 * cmd_droneStatus → heartbeat-extras → inferred-summary mapping the cloud
 * bridge relies on to render the per-drone Vision tab.
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { inferCapabilities } from "../infer-capabilities";
import type { AgentStatus } from "../types";
import { buildHeartbeatExtras } from "@/components/command/bridges/status-mapper";

function statusWithSoc(soc: string): AgentStatus {
  return {
    version: "0.47.0",
    uptime_seconds: 100,
    board: {
      name: "Test Board",
      model: "",
      tier: 2,
      ram_mb: 8192,
      cpu_cores: 8,
      vendor: "",
      soc,
      arch: "arm64",
      hw_video_codecs: [],
    },
    health: {
      cpu_percent: 5,
      memory_percent: 20,
      disk_percent: 10,
      temperature: 40,
      timestamp: new Date().toISOString(),
    },
    fc_connected: false,
    fc_port: "",
    fc_baud: 0,
  };
}

describe("inferCapabilities vision flag", () => {
  it("sets visionAvailable=true when the agent advertises a backend", () => {
    // A board with no NPU still gets the flag when the agent advertises
    // the vision surface — the advertised surface is authoritative.
    const caps = inferCapabilities(statusWithSoc("BCM2712"), [], {
      visionBackend: "mock",
      visionActiveModel: null,
    });
    expect(caps).not.toBeNull();
    expect(caps!.visionAvailable).toBe(true);
    // engine present but idle → summary exists with a null active model
    expect(caps!.visionSummary).toBeDefined();
    expect(caps!.visionSummary!.backend).toBe("mock");
    expect(caps!.visionSummary!.activeModel).toBeNull();
  });

  it("carries the live summary metrics through when advertised", () => {
    const caps = inferCapabilities(statusWithSoc("RK3588"), [], {
      visionBackend: "rknn",
      visionActiveModel: "com.example.weeds",
      visionDetectionsPerSec: 12.5,
      visionFps: 24,
    });
    expect(caps!.visionAvailable).toBe(true);
    expect(caps!.visionSummary).toEqual({
      activeModel: "com.example.weeds",
      backend: "rknn",
      detectionsPerSec: 12.5,
      fps: 24,
    });
  });

  it("falls back to NPU-bearing SoC when the surface is not advertised", () => {
    // RK3588 has a real NPU; no advertised surface, but the hardware
    // prerequisite is present → vision-capable.
    const caps = inferCapabilities(statusWithSoc("RK3588"), []);
    expect(caps!.compute.npu_available).toBe(true);
    expect(caps!.visionAvailable).toBe(true);
    // No advertised surface → no fabricated summary
    expect(caps!.visionSummary).toBeUndefined();
  });

  it("leaves visionAvailable undefined on a no-real-NPU board with no surface", () => {
    // Pi-class board (NPU TOPS 0) and no advertised vision surface →
    // the tab stays hidden. The Pi entries carry npu_tops 0, so the
    // gate is on TOPS > 0, not the npu_available boolean.
    const caps = inferCapabilities(statusWithSoc("BCM2711"), []);
    expect(caps!.compute.npu_tops).toBe(0);
    expect(caps!.visionAvailable).toBeUndefined();
    expect(caps!.visionSummary).toBeUndefined();
  });
});

describe("cmd_droneStatus vision mapping", () => {
  // No agent path emits the vision-summary fields on the cloud heartbeat
  // today, so the bridge no longer reads visionActiveModel / visionBackend /
  // visionFps / visionDetectionsPerSec off a cloud row — forwarding
  // always-undefined fields would make the contract lie. The inference path
  // still accepts the overrides directly (see the suite above); only the
  // heartbeat-row extraction is gone until a producer ships them on the wire.
  it("does not read vision summary fields off a cloud row", () => {
    const extras = buildHeartbeatExtras({
      visionActiveModel: "com.example.weeds",
      visionBackend: "ort",
      visionDetectionsPerSec: 8,
      visionFps: 15,
    });
    expect(extras.inferOverrides?.visionActiveModel).toBeUndefined();
    expect(extras.inferOverrides?.visionBackend).toBeUndefined();
    expect(extras.inferOverrides?.visionDetectionsPerSec).toBeUndefined();
    expect(extras.inferOverrides?.visionFps).toBeUndefined();
  });

  it("does not fabricate a vision summary from a cloud row", () => {
    // A cloud row carrying vision fields must not light up the Vision tab,
    // because the bridge drops them; only hardware inference (an NPU-bearing
    // SoC) can set visionAvailable absent an advertised surface.
    const extras = buildHeartbeatExtras({
      visionActiveModel: "com.example.people",
      visionBackend: "rknn",
      visionDetectionsPerSec: 30,
      visionFps: 30,
    });
    const caps = inferCapabilities(
      statusWithSoc("BCM2711"),
      [],
      extras.inferOverrides,
    );
    expect(caps!.visionAvailable).toBeUndefined();
    expect(caps!.visionSummary).toBeUndefined();
  });

  it("leaves vision overrides undefined when the row omits them", () => {
    const extras = buildHeartbeatExtras({ version: "0.47.0" });
    expect(extras.inferOverrides?.visionActiveModel).toBeUndefined();
    expect(extras.inferOverrides?.visionBackend).toBeUndefined();
    const caps = inferCapabilities(
      statusWithSoc("BCM2712"),
      [],
      extras.inferOverrides,
    );
    expect(caps!.visionAvailable).toBeUndefined();
    expect(caps!.visionSummary).toBeUndefined();
  });
});
