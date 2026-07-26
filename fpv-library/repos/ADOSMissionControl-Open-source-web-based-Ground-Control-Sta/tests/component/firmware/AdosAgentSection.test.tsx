/**
 * Component tests for AdosAgentSection. Covers loading + error states,
 * the curl install panel (command rendering, copy-to-clipboard, setup
 * page hint), the web-flash install panel (image size + missing image
 * URL warning), notes rendering, and the copy-feedback reset on board
 * change.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, act } from "@testing-library/react";
import { renderWithIntl } from "../../helpers/intl-wrapper";
import type {
  AdosAgentBoard,
  AdosAgentInstall,
} from "@/lib/protocol/firmware/ados-agent-manifest";

vi.mock("lucide-react", () => {
  const Stub = (name: string) => (props: Record<string, unknown>) =>
    <span data-testid={`icon-${name}`} {...props} />;
  return {
    HardDrive: Stub("HardDrive"),
    RefreshCw: Stub("RefreshCw"),
    Copy: Stub("Copy"),
    Check: Stub("Check"),
    Terminal: Stub("Terminal"),
    Usb: Stub("Usb"),
    Info: Stub("Info"),
    Zap: Stub("Zap"),
    Loader2: Stub("Loader2"),
    AlertTriangle: Stub("AlertTriangle"),
    ChevronDown: Stub("ChevronDown"),
    Search: Stub("Search"),
  };
});

import { AdosAgentSection } from "@/components/fc/firmware/AdosAgentSection";

function curlBoard(overrides: Partial<AdosAgentBoard> = {}): AdosAgentBoard {
  const install: AdosAgentInstall = {
    method: "curl",
    command: "curl -sSL https://example.org/install.sh | sudo bash",
    notes: ["Run this on the Pi after first boot.", "Pi must be online first."],
  };
  return {
    id: "rpi4b",
    label: "Raspberry Pi 4 Model B",
    soc: "BCM2711",
    arch: "aarch64-glibc",
    stacks: ["ados-drone-agent"],
    installs: { "ados-drone-agent": install },
    ...overrides,
  };
}

function webFlashBoard(
  overrides: Partial<AdosAgentInstall & { id?: string }> = {},
): AdosAgentBoard {
  const install: AdosAgentInstall = {
    method: "web-flash",
    imageUrl: "https://example.org/lite.img.gz",
    sha256: "deadbeefcafe",
    minisignSignature: "AAAA",
    imageSizeBytes: 50 * 1024 * 1024,
    notes: ["Hold the BOOT button while plugging USB-C in."],
    ...(overrides as Partial<AdosAgentInstall>),
  } as AdosAgentInstall;
  return {
    id: "luckfox-pico-zero",
    label: "Luckfox Pico Zero",
    soc: "RV1106G3",
    arch: "armv7-musl",
    stacks: ["ados-drone-agent"],
    installs: { "ados-drone-agent": install },
  };
}

describe("AdosAgentSection", () => {
  let writeText: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", {
      ...globalThis.navigator,
      clipboard: { writeText },
    });
  });

  it("disables the board picker while loading", () => {
    renderWithIntl(
      <AdosAgentSection
        stack="ados-drone-agent"
        boards={[]}
        loading={true}
        error=""
        agentVersion=""
        selectedBoardId=""
        setSelectedBoardId={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    const trigger = screen.getByRole("combobox");
    expect((trigger as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/loading manifest/i)).toBeDefined();
  });

  it("renders the agent version pill when provided", () => {
    renderWithIntl(
      <AdosAgentSection
        stack="ados-drone-agent"
        boards={[]}
        loading={false}
        error=""
        agentVersion="lite-v0.1.3"
        selectedBoardId=""
        setSelectedBoardId={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByText(/lite-v0\.1\.3/)).toBeDefined();
  });

  it("renders the error message and a Retry button when error is set", () => {
    const onRetry = vi.fn();
    renderWithIntl(
      <AdosAgentSection
        stack="ados-drone-agent"
        boards={[]}
        loading={false}
        error="Failed to load ADOS manifest"
        agentVersion=""
        selectedBoardId=""
        setSelectedBoardId={vi.fn()}
        onRetry={onRetry}
      />,
    );

    expect(screen.getByText("Failed to load ADOS manifest")).toBeDefined();
    const retry = screen.getByRole("button", { name: /retry/i });
    fireEvent.click(retry);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  describe("curl install board", () => {
    it("renders the command in a pre block and the setup-page hint", () => {
      const board = curlBoard();
      renderWithIntl(
        <AdosAgentSection
          stack="ados-drone-agent"
          boards={[board]}
          loading={false}
          error=""
          agentVersion="lite-v0.1.3"
          selectedBoardId={board.id}
          setSelectedBoardId={vi.fn()}
          onRetry={vi.fn()}
        />,
      );

      const install = board.installs["ados-drone-agent"]!;
      if (install.method !== "curl") throw new Error("expected curl install");
      expect(screen.getByText(install.command)).toBeDefined();
      expect(screen.getByText(/setup page/i)).toBeDefined();
      expect(screen.getByText(/8080/)).toBeDefined();
    });

    it("renders all install notes as list items", () => {
      const board = curlBoard();
      renderWithIntl(
        <AdosAgentSection
          stack="ados-drone-agent"
          boards={[board]}
          loading={false}
          error=""
          agentVersion=""
          selectedBoardId={board.id}
          setSelectedBoardId={vi.fn()}
          onRetry={vi.fn()}
        />,
      );

      expect(screen.getByText("Run this on the Pi after first boot.")).toBeDefined();
      expect(screen.getByText("Pi must be online first.")).toBeDefined();
    });

    it("copies the command via navigator.clipboard.writeText when the copy button is clicked", async () => {
      const board = curlBoard();
      renderWithIntl(
        <AdosAgentSection
          stack="ados-drone-agent"
          boards={[board]}
          loading={false}
          error=""
          agentVersion=""
          selectedBoardId={board.id}
          setSelectedBoardId={vi.fn()}
          onRetry={vi.fn()}
        />,
      );

      const copyButton = screen.getByRole("button", { name: /copy/i });
      await act(async () => {
        fireEvent.click(copyButton);
      });

      const install = board.installs["ados-drone-agent"]!;
      if (install.method !== "curl") throw new Error("expected curl install");
      expect(writeText).toHaveBeenCalledWith(install.command);
      expect(screen.getByRole("button", { name: /copied/i })).toBeDefined();
    });

    it("resets the Copied state when the selectedBoardId changes", async () => {
      const boardA = curlBoard();
      const boardB = curlBoard({
        id: "pi-zero-2w",
        label: "Pi Zero 2 W",
        soc: "BCM2710A1",
        arch: "aarch64-musl",
      });

      const { rerender } = renderWithIntl(
        <AdosAgentSection
          stack="ados-drone-agent"
          boards={[boardA, boardB]}
          loading={false}
          error=""
          agentVersion=""
          selectedBoardId={boardA.id}
          setSelectedBoardId={vi.fn()}
          onRetry={vi.fn()}
        />,
      );

      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: /copy/i }));
      });
      expect(screen.getByRole("button", { name: /copied/i })).toBeDefined();

      rerender(
        <AdosAgentSection
          stack="ados-drone-agent"
          boards={[boardA, boardB]}
          loading={false}
          error=""
          agentVersion=""
          selectedBoardId={boardB.id}
          setSelectedBoardId={vi.fn()}
          onRetry={vi.fn()}
        />,
      );

      // After the board change, the copy pip drops back to the default
      // "Copy" label so users don't think they copied the new command.
      expect(screen.getByRole("button", { name: /copy/i })).toBeDefined();
      expect(screen.queryByRole("button", { name: /copied/i })).toBeNull();
    });
  });

  describe("web-flash install board", () => {
    it("shows the image size and sha256 when imageUrl is published", () => {
      const board = webFlashBoard();
      renderWithIntl(
        <AdosAgentSection
          stack="ados-drone-agent"
          boards={[board]}
          loading={false}
          error=""
          agentVersion="lite-v0.1.3"
          selectedBoardId={board.id}
          setSelectedBoardId={vi.fn()}
          onRetry={vi.fn()}
        />,
      );

      // 50 * 1024 * 1024 bytes = 50.0 MB.
      expect(screen.getByText(/50\.0 MB/)).toBeDefined();
      expect(screen.getByText(/deadbeefcafe/)).toBeDefined();
      // The "Flash via browser" string appears as both the section heading
      // and the action button. Asserting `getAllByText` keeps the test
      // resilient to either / both surfaces moving copy around.
      expect(screen.getAllByText(/flash via browser/i).length).toBeGreaterThan(0);
    });

    it("warns when no image URL has been published yet", () => {
      const board = webFlashBoard({
        imageUrl: "",
        sha256: "",
        minisignSignature: "",
        imageSizeBytes: 0,
      });
      renderWithIntl(
        <AdosAgentSection
          stack="ados-drone-agent"
          boards={[board]}
          loading={false}
          error=""
          agentVersion=""
          selectedBoardId={board.id}
          setSelectedBoardId={vi.fn()}
          onRetry={vi.fn()}
        />,
      );

      expect(screen.getByText(/no image url published/i)).toBeDefined();
    });

    it("renders web-flash notes as a list", () => {
      const board = webFlashBoard();
      renderWithIntl(
        <AdosAgentSection
          stack="ados-drone-agent"
          boards={[board]}
          loading={false}
          error=""
          agentVersion=""
          selectedBoardId={board.id}
          setSelectedBoardId={vi.fn()}
          onRetry={vi.fn()}
        />,
      );

      expect(
        screen.getByText("Hold the BOOT button while plugging USB-C in."),
      ).toBeDefined();
    });
  });
});
