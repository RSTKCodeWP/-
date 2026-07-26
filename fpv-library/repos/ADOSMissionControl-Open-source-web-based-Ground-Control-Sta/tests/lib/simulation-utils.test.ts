import { describe, expect, it } from "vitest";
import type { Waypoint } from "@/lib/types";
import { createSimulationMissionSignature } from "@/lib/simulation-utils";

const baseWaypoints: Waypoint[] = [
  { id: "wp-1", lat: 12.9716, lon: 77.5946, alt: 30, command: "TAKEOFF" },
  { id: "wp-2", lat: 12.972, lon: 77.595, alt: 45, speed: 8 },
];

describe("createSimulationMissionSignature", () => {
  it("stays stable for equivalent simulation inputs", () => {
    expect(createSimulationMissionSignature(baseWaypoints, 6)).toBe(
      createSimulationMissionSignature([...baseWaypoints], 6)
    );
  });

  it("changes when same-count waypoint content changes", () => {
    const changed = [
      baseWaypoints[0],
      { ...baseWaypoints[1], lat: baseWaypoints[1].lat + 0.001 },
    ];

    expect(createSimulationMissionSignature(changed, 6)).not.toBe(
      createSimulationMissionSignature(baseWaypoints, 6)
    );
  });

  it("changes when default speed changes", () => {
    expect(createSimulationMissionSignature(baseWaypoints, 7)).not.toBe(
      createSimulationMissionSignature(baseWaypoints, 6)
    );
  });
});
