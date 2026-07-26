/**
 * @license GPL-3.0-only
 *
 * Render tests for the ADOS Black Box push affordances: the "Push to cloud"
 * button is disabled (with a tooltip) on a LAN-only drone with no cloud id and
 * in cloud mode, and the exported-windows list renders only when the drone has
 * a cloud id and the reactive query returns a non-empty list.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import messages from "../../../../locales/en.json";

// Gate always passes so the body (and the toolbar) renders.
vi.mock("@/hooks/use-surface-gate", () => ({
  useSurfaceGate: () => ({ mode: "ok", requirement: "agent-online" }),
}));
vi.mock("./shared/agent-gate-fallback", () => ({
  agentGateFallback: () => null,
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

// The reactive cloud-read is driven per test.
let convexWindows: unknown[] | undefined = undefined;
vi.mock("@/hooks/use-convex-skip-query", () => ({
  useConvexSkipQuery: () => convexWindows,
}));
vi.mock("convex/react", () => ({
  useAction: () => vi.fn(async () => ({ url: "https://x/y", window: {} })),
}));

import { BlackBoxTab } from "../BlackBoxTab";
import { useAgentConnectionStore } from "@/stores/agent-connection-store";
import { useBlackBoxStore } from "@/stores/blackbox-store";

function renderTab() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <BlackBoxTab />
    </NextIntlClientProvider>,
  );
}

function setConn(opts: { cloudMode: boolean; cloudDeviceId: string | null }) {
  useAgentConnectionStore.setState({
    cloudMode: opts.cloudMode,
    cloudDeviceId: opts.cloudDeviceId,
    client: null,
  });
}

function pushButton(): HTMLButtonElement {
  const btn = screen
    .getAllByRole("button")
    .find((b) => b.textContent?.includes("Push to cloud"));
  if (!btn) throw new Error("Push to cloud button not found");
  return btn as HTMLButtonElement;
}

describe("BlackBoxTab push affordances", () => {
  beforeEach(() => {
    convexWindows = undefined;
    // The store starts available so the body is not the unavailable state.
    useBlackBoxStore.setState({ available: true, loadingRows: false });
  });

  it("disables Push to cloud when the drone has no cloud id (LAN-only)", () => {
    setConn({ cloudMode: false, cloudDeviceId: null });
    renderTab();
    const btn = pushButton();
    expect(btn).toBeDisabled();
    expect(btn.title).toBe(messages.blackbox.pushNeedsPairing);
  });

  it("disables Push to cloud in cloud mode", () => {
    setConn({ cloudMode: true, cloudDeviceId: "dev_1" });
    renderTab();
    const btn = pushButton();
    expect(btn).toBeDisabled();
    expect(btn.title).toBe(messages.blackbox.pushNeedsLocal);
  });

  it("enables Push to cloud on a local, cloud-paired drone", () => {
    setConn({ cloudMode: false, cloudDeviceId: "dev_1" });
    renderTab();
    const btn = pushButton();
    expect(btn).not.toBeDisabled();
    expect(btn.title).toBe(messages.blackbox.push);
  });

  it("hides the exported-windows list when the query is empty", () => {
    convexWindows = [];
    setConn({ cloudMode: false, cloudDeviceId: "dev_1" });
    renderTab();
    expect(screen.queryByText(messages.blackbox.pushedWindows)).toBeNull();
  });

  it("renders the exported-windows list when the query is non-empty", () => {
    convexWindows = [
      {
        _id: "w1",
        _creationTime: 1,
        deviceId: "dev_1",
        sessionId: "7",
        kind: "logs",
        windowStartUs: 1,
        windowEndUs: 2,
        contentHash: "h",
        format: "jsonl.zst",
        rowCount: 10,
        sizeBytes: 2048,
        pushedAt: Date.now(),
      },
    ];
    setConn({ cloudMode: false, cloudDeviceId: "dev_1" });
    renderTab();
    expect(screen.getByText(messages.blackbox.pushedWindows)).toBeTruthy();
  });
});
