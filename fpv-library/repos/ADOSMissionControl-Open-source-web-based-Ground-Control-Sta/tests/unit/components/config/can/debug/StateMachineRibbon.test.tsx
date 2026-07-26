/**
 * @module StateMachineRibbon.test
 * @description Pill ordering, active highlight, IDLE collapse, and failed
 * inline reason.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl } from "../../../../../helpers/intl-wrapper";
import { StateMachineRibbon } from "@/components/config/can/debug/StateMachineRibbon";
import { useDroneCanFlashStore } from "@/stores/dronecan";

beforeEach(() => {
  useDroneCanFlashStore.getState().reset();
});

describe("StateMachineRibbon", () => {
  it("collapses to a single sentence in IDLE", () => {
    renderWithIntl(<StateMachineRibbon />);
    expect(screen.getByText(/no flash in progress/i)).toBeDefined();
    expect(screen.queryByText("Arm")).toBeNull();
  });

  it("renders all six pills when not IDLE", () => {
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
    renderWithIntl(<StateMachineRibbon />);
    for (const name of ["Arm", "Begin", "Transfer", "Reboot", "Verify", "Done"]) {
      expect(screen.getByText(name)).toBeDefined();
    }
  });

  it("highlights the current step", () => {
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
    renderWithIntl(<StateMachineRibbon />);
    const active = document.querySelector('[data-step="transfer"][data-active="true"]');
    expect(active).not.toBeNull();
  });

  it("renders failure reason when FAILED", () => {
    useDroneCanFlashStore.getState().setSnapshot({
      state: "FAILED",
      percent: 40,
      bytesSent: 0,
      bytesTotal: 0,
      lastOffset: 0,
      lastChunkLen: 0,
      retries: 0,
      timeouts: 0,
      transitionLog: [],
      rpcTrace: [],
      errorCode: "TIMEOUT",
      errorMessage: "Node went silent",
    });
    renderWithIntl(<StateMachineRibbon />);
    expect(screen.getByText(/Node went silent/)).toBeDefined();
  });
});
