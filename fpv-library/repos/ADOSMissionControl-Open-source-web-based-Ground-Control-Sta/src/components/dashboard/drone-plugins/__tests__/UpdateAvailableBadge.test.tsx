/**
 * @license GPL-3.0-only
 *
 * Render tests for UpdateAvailableBadge. Verifies the badge renders
 * nothing when no pending event exists for the (deviceId, pluginId)
 * pair, renders a clickable button when an event is present, and
 * fires the onClick callback when activated.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import { fireEvent, render } from "@testing-library/react";

import messages from "../../../../../locales/en.json";
import { usePluginUpdateStore } from "@/stores/plugin-update-store";

import { UpdateAvailableBadge } from "../UpdateAvailableBadge";

function wrap(children: React.ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("UpdateAvailableBadge", () => {
  beforeEach(() => {
    usePluginUpdateStore.setState({ pendingUpdates: [] });
  });

  it("renders nothing when no event matches the (deviceId, pluginId)", () => {
    const { container } = render(
      wrap(<UpdateAvailableBadge deviceId="drone-1" pluginId="plugin-a" />),
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders the badge when a matching event exists", () => {
    usePluginUpdateStore.getState().addUpdate({
      deviceId: "drone-1",
      pluginId: "plugin-a",
      currentVersion: "1.0.0",
      latestVersion: "2.0.0",
      reason: "major_bump",
      newPermissions: [],
      timestamp: 1_000,
    });
    const { getByTestId } = render(
      wrap(<UpdateAvailableBadge deviceId="drone-1" pluginId="plugin-a" />),
    );
    const badge = getByTestId("plugin-update-badge-plugin-a");
    expect(badge).toBeDefined();
    expect(badge.textContent).toContain("Update available");
  });

  it("does not render a badge for a non-matching plugin on the same drone", () => {
    usePluginUpdateStore.getState().addUpdate({
      deviceId: "drone-1",
      pluginId: "plugin-a",
      currentVersion: "1.0.0",
      latestVersion: "2.0.0",
      reason: "major_bump",
      newPermissions: [],
      timestamp: 1_000,
    });
    const { container } = render(
      wrap(<UpdateAvailableBadge deviceId="drone-1" pluginId="plugin-b" />),
    );
    expect(container.firstChild).toBeNull();
  });

  it("fires the onClick callback when activated", () => {
    usePluginUpdateStore.getState().addUpdate({
      deviceId: "drone-1",
      pluginId: "plugin-a",
      currentVersion: "1.0.0",
      latestVersion: "2.0.0",
      reason: "permission_delta",
      newPermissions: ["network.outbound"],
      timestamp: 1_000,
    });
    const onClick = vi.fn();
    const { getByTestId } = render(
      wrap(
        <UpdateAvailableBadge
          deviceId="drone-1"
          pluginId="plugin-a"
          onClick={onClick}
        />,
      ),
    );
    fireEvent.click(getByTestId("plugin-update-badge-plugin-a"));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
