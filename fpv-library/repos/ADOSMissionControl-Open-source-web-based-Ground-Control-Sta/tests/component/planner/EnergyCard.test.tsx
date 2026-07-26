/**
 * Render tests for EnergyCard. Verifies the card computes a watt-hour / flight
 * time / battery-swap estimate from the waypoint path, and shows an honest
 * em-dash for every figure when the path has no length yet.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next-intl", () => ({ useTranslations: () => (k: string) => k }));

import { EnergyCard } from "@/components/planner/EnergyCard";

// Two points ~1 degree of longitude apart at the equator (~111 km) so the
// estimate is comfortably non-zero and a swap is implied.
const farPath = [
  { lat: 0, lon: 0 },
  { lat: 0, lon: 1 },
];

describe("EnergyCard", () => {
  it("shows a watt-hour estimate for a real path", () => {
    render(<EnergyCard waypoints={farPath} />);
    // Value cells carry the unit; the estimate is present, not the placeholder.
    expect(screen.getByText(/Wh/)).toBeDefined();
    expect(screen.queryByText("—")).toBeNull();
  });

  it("honours a supplied cruise speed without crashing", () => {
    render(<EnergyCard waypoints={farPath} cruiseSpeedMps={12} />);
    expect(screen.getByText(/Wh/)).toBeDefined();
  });

  it("shows honest em-dashes when there is no path", () => {
    render(<EnergyCard waypoints={[{ lat: 12.97, lon: 77.59 }]} />);
    // A single waypoint has zero path length: every figure is a placeholder.
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByText(/Wh/)).toBeNull();
  });
});
