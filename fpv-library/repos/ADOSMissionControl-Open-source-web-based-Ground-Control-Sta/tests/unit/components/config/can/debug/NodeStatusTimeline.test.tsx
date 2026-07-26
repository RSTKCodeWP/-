/**
 * Smoke tests for NodeStatusTimeline. Verifies the empty state, lane
 * rendering, and restart-tick detection.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "../../../../../helpers/intl-wrapper";
import { useDroneCanNodeStore } from "@/stores/dronecan/node-store";

import { NodeStatusTimeline } from "@/components/config/can/debug/NodeStatusTimeline";

describe("NodeStatusTimeline", () => {
  beforeEach(() => {
    useDroneCanNodeStore.setState({ nodes: new Map(), _version: 0 } as never);
  });

  it("renders the waiting hint when no history exists", () => {
    renderWithIntl(<NodeStatusTimeline nodeId={11} />);
    expect(screen.getByText(/Waiting for NodeStatus/i)).toBeDefined();
  });

  it("renders the lanes when history is seeded", () => {
    const store = useDroneCanNodeStore.getState();
    for (let i = 0; i < 5; i++) {
      store.upsertStatus(11, {
        uptime_sec: 10 + i,
        health: 0,
        mode: 0,
        vendor_specific_status_code: 0,
      } as never);
    }
    renderWithIntl(<NodeStatusTimeline nodeId={11} />);
    expect(screen.getByText("OPERATIONAL")).toBeDefined();
    expect(screen.getByText("INITIALIZATION")).toBeDefined();
    expect(screen.getByText("SOFTWARE_UPDATE")).toBeDefined();
    expect(screen.getByTestId("node-status-timeline-body")).toBeDefined();
  });

  it("marks a restart tick when uptime decreases", () => {
    const store = useDroneCanNodeStore.getState();
    store.upsertStatus(11, {
      uptime_sec: 100,
      health: 0,
      mode: 0,
      vendor_specific_status_code: 0,
    } as never);
    store.upsertStatus(11, {
      uptime_sec: 1,
      health: 0,
      mode: 0,
      vendor_specific_status_code: 0,
    } as never);
    renderWithIntl(<NodeStatusTimeline nodeId={11} />);
    const restartRow = screen.getByTestId("node-status-timeline-restart-row");
    const ticks = restartRow.querySelectorAll('[data-restart="true"]');
    expect(ticks.length).toBeGreaterThanOrEqual(1);
  });
});
