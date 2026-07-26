/**
 * Component tests for SlcanModeBanner. Exercises the Resume MAVLink
 * button path that the SLCAN flash arbiter wires up via the store's
 * `exitFn` registry. The banner is the only operator-facing exit lever
 * for an active SLCAN session; the 300s `CAN_SLCAN_TIMOUT` watchdog is
 * a backstop, not an exit UX.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SlcanModeBanner } from "@/components/shared/SlcanModeBanner";
import { useSlcanModeStore } from "@/stores/slcan-mode-store";

describe("SlcanModeBanner — Resume MAVLink", () => {
  beforeEach(() => {
    useSlcanModeStore.getState().reset();
  });

  it("renders no banner in IDLE", () => {
    const { container } = render(<SlcanModeBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the Resume MAVLink button when SLCAN_ACTIVE and exitFn is set", () => {
    useSlcanModeStore.getState().beginEntering({
      droneId: "d", bus: 1, bitrate: 1_000_000, timeoutSec: 300,
    });
    useSlcanModeStore.getState().markActive();
    useSlcanModeStore.getState().setExitFn(async () => {});
    render(<SlcanModeBanner />);
    expect(screen.getByTestId("slcan-banner-resume")).toBeDefined();
  });

  it("falls back to passive copy when no exitFn is registered", () => {
    useSlcanModeStore.getState().beginEntering({
      droneId: "d", bus: 1, bitrate: 1_000_000, timeoutSec: 300,
    });
    useSlcanModeStore.getState().markActive();
    render(<SlcanModeBanner />);
    expect(screen.queryByTestId("slcan-banner-resume")).toBeNull();
    expect(
      screen.getByText(/Resume MAVLink when the flash completes/i),
    ).toBeDefined();
  });

  it("invokes the registered exitFn on click", async () => {
    const exitFn = vi.fn().mockResolvedValue(undefined);
    useSlcanModeStore.getState().beginEntering({
      droneId: "d", bus: 1, bitrate: 1_000_000, timeoutSec: 300,
    });
    useSlcanModeStore.getState().markActive();
    useSlcanModeStore.getState().setExitFn(exitFn);
    render(<SlcanModeBanner />);
    fireEvent.click(screen.getByTestId("slcan-banner-resume"));
    await waitFor(() => expect(exitFn).toHaveBeenCalledTimes(1));
  });
});
