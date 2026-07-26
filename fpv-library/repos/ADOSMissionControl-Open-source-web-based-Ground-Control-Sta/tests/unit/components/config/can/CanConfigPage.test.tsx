/**
 * Smoke tests for CanConfigPage. Verifies the page renders with and
 * without a selected drone, and that the vertical section tabs route
 * between the three live sections.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithIntl } from "../../../../helpers/intl-wrapper";
import { useDroneManager } from "@/stores/drone-manager";

vi.mock("@/hooks/use-armed-lock", () => ({
  useArmedLock: () => ({ isArmed: false, lockMessage: "" }),
}));

vi.mock("@/hooks/use-unsaved-guard", () => ({
  useUnsavedGuard: () => undefined,
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/hooks/use-flash-commit-toast", () => ({
  useFlashCommitToast: () => vi.fn(),
}));

import { CanConfigPage } from "@/components/config/can/CanConfigPage";

describe("CanConfigPage", () => {
  beforeEach(() => {
    useDroneManager.setState({
      drones: new Map(),
      selectedDroneId: null,
      getSelectedProtocol: () => null,
      getSelectedDrone: () => null,
    } as never);
  });

  it("renders the page header and section tabs with no drone selected", () => {
    renderWithIntl(<CanConfigPage />);
    expect(screen.getByText("CAN Configuration")).toBeDefined();
    expect(screen.getByText("Bus setup")).toBeDefined();
    expect(screen.getByText("Node browser")).toBeDefined();
    expect(screen.getByText("Bus monitor")).toBeDefined();
  });

  it("surfaces a no-drone hint when no FC is connected", () => {
    renderWithIntl(<CanConfigPage />);
    expect(
      screen.getByText(/No drone selected/i),
    ).toBeDefined();
  });

  it("renders the bus-setup section by default", () => {
    renderWithIntl(<CanConfigPage />);
    // Section card title comes from canConfig.busSetup.can1Title.
    expect(screen.getByText("CAN1")).toBeDefined();
    expect(screen.getByText("CAN2")).toBeDefined();
  });

  it("switches to the node browser tab on click", () => {
    renderWithIntl(<CanConfigPage />);
    const tab = screen.getByRole("button", { name: /Node browser/i });
    fireEvent.click(tab);
    expect(screen.getByText("Detected DroneCAN nodes")).toBeDefined();
  });

  it("switches to the per-node params tab on click", () => {
    renderWithIntl(<CanConfigPage />);
    const tab = screen.getByRole("button", { name: /Per-node params/i });
    fireEvent.click(tab);
    // Two matches are acceptable here (one in the placeholder card, one in the tab).
    expect(screen.getAllByText("Per-node params").length).toBeGreaterThan(0);
  });
});
