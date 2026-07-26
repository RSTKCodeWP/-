/**
 * @module FlashByteCounter.test
 * @description Empty state when IDLE, progress bar width when active.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "../../../../../helpers/intl-wrapper";
import { FlashByteCounter } from "@/components/config/can/debug/FlashByteCounter";
import { useDroneCanFlashStore } from "@/stores/dronecan";

beforeEach(() => {
  useDroneCanFlashStore.getState().reset();
});

describe("FlashByteCounter", () => {
  it("renders the empty sentence when IDLE", () => {
    renderWithIntl(<FlashByteCounter />);
    expect(screen.getByText(/no transfer in progress/i)).toBeDefined();
  });

  it("computes percent and renders the bar when transferring", () => {
    useDroneCanFlashStore.getState().setSnapshot({
      state: "TRANSFERRING",
      percent: 50,
      bytesSent: 1024,
      bytesTotal: 2048,
      lastOffset: 1024,
      lastChunkLen: 256,
      retries: 0,
      timeouts: 0,
      transitionLog: [],
      rpcTrace: [],
    });
    renderWithIntl(<FlashByteCounter />);
    const bar = screen.getByTestId("byte-counter-bar") as HTMLElement;
    expect(bar.style.width).toBe("50%");
    // 1024 / 256 = 4 chunks — confirm row by walking from the Chunks label.
    const chunksRow = screen.getByText("Chunks").parentElement!;
    expect(chunksRow.textContent).toContain("4");
  });

  it("shows retries and timeouts when non-zero", () => {
    useDroneCanFlashStore.getState().setSnapshot({
      state: "TRANSFERRING",
      percent: 10,
      bytesSent: 200,
      bytesTotal: 2048,
      lastOffset: 200,
      lastChunkLen: 64,
      retries: 3,
      timeouts: 1,
      transitionLog: [],
      rpcTrace: [],
    });
    renderWithIntl(<FlashByteCounter />);
    const retriesRow = screen.getByText("Retries").parentElement!;
    expect(retriesRow.textContent).toContain("3");
    const timeoutsRow = screen.getByText("Timeouts").parentElement!;
    expect(timeoutsRow.textContent).toContain("1");
  });
});
