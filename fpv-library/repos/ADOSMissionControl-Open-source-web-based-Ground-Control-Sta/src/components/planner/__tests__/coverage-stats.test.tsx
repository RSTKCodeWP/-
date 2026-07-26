/**
 * @license GPL-3.0-only
 * CoverageStats: renders survey coverage figures from the generated waypoints,
 * and stays silent when there is no camera or no survey route.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next-intl", () => ({ useTranslations: () => (k: string) => k }));
vi.mock("@/lib/storage", () => ({
  indexedDBStorage: {
    storage: () => ({
      getItem: vi.fn(async () => null),
      setItem: vi.fn(async () => {}),
      removeItem: vi.fn(async () => {}),
    }),
  },
}));

import { CoverageStats } from "@/components/planner/CoverageStats";
import { usePatternStore } from "@/stores/pattern-store";
import { CAMERA_PROFILES } from "@/lib/patterns/gsd-calculator";
import type { PatternResult, PatternWaypoint } from "@/lib/patterns/types";

const camera = CAMERA_PROFILES.find((c) => c.name === "DJI Mavic 3")!;

function wp(lat: number, lon: number): PatternWaypoint {
  return { lat, lon, alt: 50, speed: 5, command: "WAYPOINT" };
}

function surveyResult(): PatternResult {
  return {
    waypoints: [
      wp(12.9716, 77.5946),
      wp(12.9726, 77.5946),
      wp(12.9726, 77.5948),
      wp(12.9716, 77.5948),
    ],
    stats: { totalDistance: 0, estimatedTime: 0, photoCount: 0, coveredArea: 0, transectCount: 0 },
  };
}

beforeEach(() => {
  usePatternStore.setState({ activePatternType: "survey", patternResult: surveyResult() });
});

describe("CoverageStats", () => {
  it("renders coverage figures for a survey route", () => {
    render(<CoverageStats camera={camera} altitude={50} minSideOverlap={0.6} />);
    expect(screen.getByText("coverage.title")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("renders nothing without a camera", () => {
    const { container } = render(<CoverageStats camera={undefined} altitude={50} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when the active pattern is not a survey", () => {
    usePatternStore.setState({ activePatternType: "orbit" });
    const { container } = render(<CoverageStats camera={camera} altitude={50} />);
    expect(container.firstChild).toBeNull();
  });
});
