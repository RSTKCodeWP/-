/**
 * Component tests for the Flash Tool debug panel: rendering log entries,
 * level filtering, the empty state, and copy-to-clipboard.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, act } from "@testing-library/react";
import { renderWithIntl } from "../../helpers/intl-wrapper";

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

vi.mock("lucide-react", () => {
  const Stub = (name: string) => (props: Record<string, unknown>) =>
    <span data-testid={`icon-${name}`} {...props} />;
  return {
    Terminal: Stub("Terminal"),
    Copy: Stub("Copy"),
    Download: Stub("Download"),
    Trash2: Stub("Trash2"),
    Binary: Stub("Binary"),
    ChevronDown: Stub("ChevronDown"),
    ChevronRight: Stub("ChevronRight"),
    ArrowDown: Stub("ArrowDown"),
  };
});

import { FirmwareDebugPanel } from "@/components/fc/firmware/FirmwareDebugPanel";
import { useFlashLogStore } from "@/stores/flash-log-store";

function seed() {
  const log = useFlashLogStore.getState().log;
  log("info", "manager", "opening serial port");
  log("error", "px4", "Board ID mismatch boom");
}

describe("FirmwareDebugPanel", () => {
  beforeEach(() => {
    useFlashLogStore.getState().clear();
  });

  it("shows the empty state when there are no entries", () => {
    renderWithIntl(<FirmwareDebugPanel isFlashing={false} defaultOpen />);
    expect(screen.getByText("No flash activity yet.")).toBeTruthy();
  });

  it("renders log lines and filters by level", () => {
    seed();
    renderWithIntl(<FirmwareDebugPanel isFlashing={false} defaultOpen />);
    expect(screen.getByText("opening serial port")).toBeTruthy();
    expect(screen.getByText("Board ID mismatch boom")).toBeTruthy();

    // Filter to errors only.
    fireEvent.click(screen.getByText("Errors"));
    expect(screen.queryByText("opening serial port")).toBeNull();
    expect(screen.getByText("Board ID mismatch boom")).toBeTruthy();
  });

  it("copies the log to the clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    seed();
    renderWithIntl(<FirmwareDebugPanel isFlashing={false} defaultOpen />);
    await act(async () => {
      fireEvent.click(screen.getByTitle("Copy log"));
    });
    expect(writeText).toHaveBeenCalledOnce();
    expect(writeText.mock.calls[0][0]).toContain("Board ID mismatch boom");
  });
});
