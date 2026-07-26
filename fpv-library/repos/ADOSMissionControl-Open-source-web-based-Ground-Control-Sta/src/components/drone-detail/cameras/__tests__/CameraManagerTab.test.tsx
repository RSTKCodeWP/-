/**
 * @license GPL-3.0-only
 *
 * The Cameras tab schedules a post-write pipeline-restart re-read. That timer
 * must be cleared on unmount so it never fires a load against a drone slice the
 * operator has navigated away from (the orphan-timer race).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import { render, screen, fireEvent, act } from "@testing-library/react";

import messages from "../../../../../locales/en.json";
import { CameraManagerTab } from "../CameraManagerTab";
import { useCameraManagerStore } from "@/stores/camera-manager-store";
import type { RosterCamera } from "@/lib/agent/feature-types";

const camera: RosterCamera = {
  id: "belly",
  name: "Belly cam",
  source: "/dev/video2",
  role: null,
  purpose: ["navigation"],
  orientation: "down",
  enabled: true,
  owner: "operator",
  state: "assigned",
  live: true,
};

const client = {
  getCameraRoster: vi.fn(),
  setCameraRoster: vi.fn(),
};

vi.mock("@/stores/agent-connection-store", () => ({
  useAgentConnectionStore: (sel: (s: unknown) => unknown) =>
    sel({ client, cloudMode: false }),
}));
vi.mock("@/stores/agent-capabilities-store", () => ({
  useAgentCapabilitiesStore: (sel: (s: unknown) => unknown) =>
    sel({ videoStreams: [] }),
}));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

function wrap(node: React.ReactElement) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {node}
    </NextIntlClientProvider>
  );
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("CameraManagerTab · restart timer lifecycle", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    client.getCameraRoster.mockReset().mockResolvedValue([{ ...camera }]);
    client.setCameraRoster.mockReset().mockResolvedValue(undefined);
    useCameraManagerStore.setState({ byDrone: {} });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("clears the post-write re-read timer on unmount (no orphan load)", async () => {
    const { unmount } = render(wrap(<CameraManagerTab droneId="d1" />));
    await flush(); // initial roster load resolves
    expect(client.getCameraRoster).toHaveBeenCalledTimes(1);

    // Toggle the camera — this persists and schedules the restart re-read.
    fireEvent.click(screen.getByRole("switch"));
    await flush();
    expect(client.setCameraRoster).toHaveBeenCalledTimes(1);
    // The re-read is still pending (behind the restart delay).
    expect(client.getCameraRoster).toHaveBeenCalledTimes(1);

    unmount();
    // Past the restart delay: a cleared timer must not fire a second read.
    vi.advanceTimersByTime(5000);
    await flush();
    expect(client.getCameraRoster).toHaveBeenCalledTimes(1);
  });
});
