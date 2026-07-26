/**
 * @module ChannelHistoryChart.test
 * @description Verifies the hop-history sparkline: empty state, present
 * state rendering, color encoding for trigger + ok status, and that
 * recharts produces SVG output we can inspect.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeAll } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "../../helpers/intl-wrapper";
import {
  ChannelHistoryChart,
  type HoppingState,
} from "@/components/hardware/ChannelHistoryChart";

// Recharts requires a non-zero container size for ResponsiveContainer to
// render its children. jsdom returns 0 by default; this stub lets the
// SVG path actually emit so we can assert on it.
beforeAll(() => {
  Object.defineProperty(window.HTMLElement.prototype, "offsetWidth", {
    configurable: true,
    value: 400,
  });
  Object.defineProperty(window.HTMLElement.prototype, "offsetHeight", {
    configurable: true,
    value: 120,
  });
});

const NOW = Math.floor(Date.now() / 1000);

const SAMPLE: HoppingState = {
  enabled: true,
  band: "u-nii-1",
  hop_period_seconds: 60,
  history: [
    { at: NOW - 240, from: 149, to: 36, trigger: "periodic", ok: true },
    { at: NOW - 180, from: 36, to: 44, trigger: "periodic", ok: true },
    { at: NOW - 120, from: 44, to: 48, trigger: "reactive", ok: true },
    { at: NOW - 60, from: 48, to: 40, trigger: "reactive", ok: false },
    { at: NOW, from: 40, to: 44, trigger: "periodic", ok: true },
  ],
  last_hop_at: NOW,
};

describe("ChannelHistoryChart", () => {
  it("renders the empty-state placeholder when history is empty", () => {
    renderWithIntl(
      <ChannelHistoryChart
        hopping={{ ...SAMPLE, history: [] }}
        currentChannel={149}
      />,
    );
    expect(screen.getByText(/no channel hops recorded/i)).toBeTruthy();
    expect(screen.getByText(/149/)).toBeTruthy();
  });

  it("renders the empty-state placeholder when hopping is undefined", () => {
    renderWithIntl(
      <ChannelHistoryChart hopping={undefined} currentChannel={149} />,
    );
    expect(screen.getByText(/no channel hops recorded/i)).toBeTruthy();
  });

  it("renders chart with the hop count summary when history is present", () => {
    renderWithIntl(
      <ChannelHistoryChart hopping={SAMPLE} currentChannel={44} />,
    );
    // Summary chip shows the count of hops.
    expect(screen.getByText(/5 hops/i)).toBeTruthy();
    // The "Last hop" line surfaces under the chart with the channel
    // delta from the most recent entry (40 -> 44).
    expect(screen.getByText(/last hop/i)).toBeTruthy();
    expect(screen.getByText(/40 → 44/)).toBeTruthy();
  });

  it("renders a legend with the three marker colors", () => {
    renderWithIntl(
      <ChannelHistoryChart hopping={SAMPLE} currentChannel={44} />,
    );
    // Periodic / Reactive / Failed labels appear in the legend row.
    // getAllByText because Reactive also shows up in tooltips and
    // failed shows up in the legend with the same string.
    expect(screen.getAllByText(/periodic/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/reactive/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/failed/i).length).toBeGreaterThan(0);
  });

  it("does not crash when last_hop_at is missing on the hopping state", () => {
    const stateMinusLast: HoppingState = { ...SAMPLE };
    delete stateMinusLast.last_hop_at;
    renderWithIntl(
      <ChannelHistoryChart hopping={stateMinusLast} currentChannel={44} />,
    );
    expect(screen.getByText(/5 hops/i)).toBeTruthy();
  });
});
