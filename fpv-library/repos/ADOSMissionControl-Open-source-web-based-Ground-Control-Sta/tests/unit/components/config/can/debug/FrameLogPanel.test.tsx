/**
 * @module FrameLogPanel.test
 * @description Pause/resume + empty state + filter narrowing.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { renderWithIntl } from "../../../../../helpers/intl-wrapper";
import { FrameLogPanel } from "@/components/config/can/debug/FrameLogPanel";
import { useDroneCanBusStore, type DecodedFrame } from "@/stores/dronecan";

// Force the virtualizer to emit a row per visible item so we can assert on
// real DOM content in the test environment.
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: (opts: { count: number }) => ({
    getVirtualItems: () =>
      Array.from({ length: opts.count }, (_, i) => ({
        key: i,
        index: i,
        start: i * 26,
        size: 26,
      })),
    getTotalSize: () => opts.count * 26,
  }),
}));

function frame(partial: Partial<DecodedFrame>): DecodedFrame {
  return {
    t: 0,
    dir: "in",
    canId: 0,
    decoded: { kind: "message", dataTypeId: 341, srcNodeId: 10 },
    payload: new Uint8Array([0xde, 0xad, 0xbe, 0xef]),
    ...partial,
  };
}

beforeEach(() => {
  useDroneCanBusStore.getState().clear();
  if (useDroneCanBusStore.getState().paused) {
    useDroneCanBusStore.getState().resume();
  }
});

describe("FrameLogPanel", () => {
  it("shows the empty state when no frames are present", () => {
    renderWithIntl(<FrameLogPanel />);
    expect(screen.getByText(/no frames captured yet/i)).toBeDefined();
  });

  it("toggles pause and resume", () => {
    renderWithIntl(<FrameLogPanel />);
    expect(useDroneCanBusStore.getState().paused).toBe(false);
    fireEvent.click(screen.getByTestId("frame-log-pause-toggle"));
    expect(useDroneCanBusStore.getState().paused).toBe(true);
    fireEvent.click(screen.getByTestId("frame-log-pause-toggle"));
    expect(useDroneCanBusStore.getState().paused).toBe(false);
  });

  it("narrows the visible row list when an errors-only chip is toggled", () => {
    const store = useDroneCanBusStore.getState();
    store.pushFrame(frame({ t: 1000, canId: 0x100, error: false }));
    store.pushFrame(
      frame({ t: 1001, canId: 0x200, error: true, decoded: { kind: "service", dataTypeId: 11, srcNodeId: 10 } }),
    );

    renderWithIntl(<FrameLogPanel />);
    // Both frames render initially
    expect(document.querySelectorAll('[data-frame-row="true"]').length).toBe(2);

    fireEvent.click(screen.getByLabelText(/errors only/i));
    expect(document.querySelectorAll('[data-frame-row="true"]').length).toBe(1);
  });
});
