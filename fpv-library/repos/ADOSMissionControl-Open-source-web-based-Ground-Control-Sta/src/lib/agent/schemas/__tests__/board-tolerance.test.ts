/**
 * @license GPL-3.0-only
 *
 * Regression guard: `/api/status/full` must validate for a BOARDLESS node. A
 * compute/workstation node (or any node with no board sidecar) returns
 * `board: {}`, which the drone-shaped schema used to reject — spamming a schema
 * mismatch on every poll tick. The board fields are now optional.
 */

import { describe, it, expect } from "vitest";
import { FullStatusResponseSchema } from "@/lib/agent/schemas/heartbeat";

function baseStatus(board: unknown): Record<string, unknown> {
  return {
    version: "1.0.0",
    uptime_seconds: 12,
    board,
    health: {
      cpu_percent: 3,
      memory_percent: 40,
      disk_percent: 20,
      temperature: null,
      timestamp: "2026-01-01T00:00:00Z",
    },
    fc_connected: false,
    fc_port: "",
    fc_baud: 0,
  };
}

describe("FullStatusResponseSchema board tolerance", () => {
  it("accepts a workstation's empty board object", () => {
    expect(FullStatusResponseSchema.safeParse(baseStatus({})).success).toBe(
      true,
    );
  });

  it("accepts a status with no board field at all", () => {
    const s = baseStatus(undefined);
    delete s.board;
    expect(FullStatusResponseSchema.safeParse(s).success).toBe(true);
  });

  it("still accepts a fully-populated board", () => {
    const full = baseStatus({
      name: "Radxa ROCK 5C",
      model: "rock-5c",
      tier: 3,
      ram_mb: 16384,
      cpu_cores: 8,
      vendor: "Radxa",
      soc: "RK3588S2",
      arch: "aarch64",
      hw_video_codecs: ["h264", "h265"],
    });
    expect(FullStatusResponseSchema.safeParse(full).success).toBe(true);
  });
});
