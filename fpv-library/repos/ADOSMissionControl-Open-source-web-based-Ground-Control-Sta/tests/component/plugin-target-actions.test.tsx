/**
 * Tests for plugin-contributed target actions: `buildPluginTargetAction`
 * designates the target then writes the plugin's config, and
 * `PluginTargetActionHost` registers a drone's contributions into the shared
 * registry (class-predicate honored) and cleans up on unmount.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";

vi.mock("@/lib/utils", async (orig) => ({
  ...(await orig<typeof import("@/lib/utils")>()),
  isDemoMode: () => true,
}));

const MOCK_CONTRIBS = [
  {
    installId: "i1",
    pluginId: "com.altnautica.follow-me",
    localId: "follow",
    label: "Follow this target",
    order: 20,
    appliesToClass: "person",
    designate: true,
    configKey: "active",
    configValue: true,
    defaultKey: "f",
  },
];
vi.mock("@/hooks/use-drone-target-actions", () => ({
  useDroneTargetActions: () => MOCK_CONTRIBS,
}));

import { PluginTargetActionHost } from "@/components/vision/PluginTargetActionHost";
import {
  buildPluginTargetAction,
  resolveTargetActions,
  useTargetActionRegistry,
} from "@/lib/skills/target-actions";
import type { SelectedTarget } from "@/stores/selected-target-store";

const PERSON: SelectedTarget = {
  droneId: "node:drone-1",
  cameraId: "cam0",
  trackId: 3,
  bbox: { x: 1, y: 2, width: 3, height: 4 },
  classLabel: "person",
  confidence: 0.9,
};

describe("buildPluginTargetAction", () => {
  it("designates then writes the plugin config on activate", async () => {
    const writeConfig = vi.fn().mockResolvedValue(undefined);
    const notify = vi.fn();
    const action = buildPluginTargetAction(
      {
        installId: "i1",
        pluginId: "p",
        localId: "follow",
        label: "Follow",
        designate: true,
        configKey: "active",
        configValue: true,
      },
      "node:drone-1",
      writeConfig,
    );
    await action.activate({ target: PERSON, notify });
    // deviceId is resolved from the node id.
    expect(writeConfig).toHaveBeenCalledWith("p", "drone-1", "active", true);
    expect(notify).toHaveBeenCalledWith("Follow", "success");
  });
});

describe("PluginTargetActionHost", () => {
  beforeEach(() => useTargetActionRegistry.setState({ actions: [] }));
  afterEach(() => cleanup());

  it("registers a drone's plugin target actions and honors the class predicate", () => {
    const { unmount } = render(<PluginTargetActionHost droneId="node:drone-1" />);

    const id = "com.altnautica.follow-me:follow";
    expect(
      useTargetActionRegistry.getState().actions.some((a) => a.id === id),
    ).toBe(true);

    // Applies to a person, not a car.
    expect(
      resolveTargetActions(PERSON).some((a) => a.id === id),
    ).toBe(true);
    expect(
      resolveTargetActions({ ...PERSON, classLabel: "car" }).some(
        (a) => a.id === id,
      ),
    ).toBe(false);

    unmount();
    expect(
      useTargetActionRegistry.getState().actions.some((a) => a.id === id),
    ).toBe(false);
  });
});
