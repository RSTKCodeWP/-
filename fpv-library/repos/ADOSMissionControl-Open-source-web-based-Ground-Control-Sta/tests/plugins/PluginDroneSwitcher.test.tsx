import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, cleanup } from "@testing-library/react";

vi.mock("next-intl", () => ({
  useTranslations: () => (k: string) => k,
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

import { useDroneManager } from "@/stores/drone-manager";

import { PluginDroneSwitcher } from "@/components/plugins/PluginDroneSwitcher";
import { PluginSlot } from "@/components/plugins/PluginSlot";
import { slotToCapability } from "@/lib/plugins/types";
import type { PluginSlotContribution } from "@/components/plugins/PluginHostProvider";

function mkContribution(
  pluginId: string,
): PluginSlotContribution & { slot: "node.detail.tab" } {
  return {
    pluginId,
    panelId: "panel",
    slot: "node.detail.tab",
    bundleUrl: `blob:${pluginId}`,
    grantedCapabilities: new Set([slotToCapability("node.detail.tab")]),
    handlers: {},
    pluginInstallId: pluginId,
  };
}

/** Force-set selectedDroneId without touching any other manager state. */
function setSelected(id: string | null) {
  useDroneManager.setState({ selectedDroneId: id });
}

describe("PluginDroneSwitcher", () => {
  beforeEach(() => {
    setSelected("drone-1");
  });

  afterEach(() => {
    cleanup();
    setSelected(null);
  });

  it("unmounts the provider subtree on drone switch after the grace window", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const contributions = [mkContribution("com.example.alpha")];

    const { container } = render(
      <PluginDroneSwitcher contributions={contributions} graceMs={50}>
        <PluginSlot name="node.detail.tab" />
      </PluginDroneSwitcher>,
    );

    const firstIframe = container.querySelector("iframe");
    expect(firstIframe).not.toBeNull();

    await act(async () => {
      setSelected("drone-2");
      await vi.advanceTimersByTimeAsync(80);
    });

    const secondIframe = container.querySelector("iframe");
    expect(secondIframe).not.toBeNull();
    expect(secondIframe).not.toBe(firstIframe);
    vi.useRealTimers();
  });

  it("warns when the switch overruns the perf budget", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const nowSpy = vi.spyOn(performance, "now");
    // Two reads per swap path: start + end. Simulate a 700ms switch
    // to trip the 500ms warn threshold without actually waiting.
    let call = 0;
    nowSpy.mockImplementation(() => {
      call += 1;
      return call === 1 ? 0 : 700;
    });

    const contributions = [mkContribution("com.example.alpha")];

    render(
      <PluginDroneSwitcher contributions={contributions} graceMs={10}>
        <PluginSlot name="node.detail.tab" />
      </PluginDroneSwitcher>,
    );

    await act(async () => {
      setSelected("drone-3");
      await vi.advanceTimersByTimeAsync(50);
    });

    const slowCall = warnSpy.mock.calls.find(
      (c) => c[0] === "plugin_drone_switch_slow",
    );
    expect(slowCall).toBeDefined();
    warnSpy.mockRestore();
    nowSpy.mockRestore();
    vi.useRealTimers();
  });
});
