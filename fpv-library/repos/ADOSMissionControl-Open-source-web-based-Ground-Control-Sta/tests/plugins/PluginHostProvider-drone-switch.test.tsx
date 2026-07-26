import { describe, it, expect, vi } from "vitest";
import { render, cleanup } from "@testing-library/react";

vi.mock("next-intl", () => ({
  useTranslations: () => (k: string) => k,
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

import {
  PluginHostProvider,
  type PluginSlotContribution,
} from "@/components/plugins/PluginHostProvider";
import { PluginSlot } from "@/components/plugins/PluginSlot";
import { slotToCapability } from "@/lib/plugins/types";

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

describe("PluginHostProvider drone-switch keying", () => {
  it("keys the subtree by deviceId so React tears it down on switch", () => {
    const contributions = [mkContribution("com.example.alpha")];

    const { container, rerender } = render(
      <PluginHostProvider
        deviceId="drone-1"
        contributions={contributions}
      >
        <PluginSlot name="node.detail.tab" />
      </PluginHostProvider>,
    );

    const firstIframe = container.querySelector("iframe");
    expect(firstIframe).not.toBeNull();
    const firstHandle = firstIframe as HTMLIFrameElement;

    rerender(
      <PluginHostProvider
        deviceId="drone-2"
        contributions={contributions}
      >
        <PluginSlot name="node.detail.tab" />
      </PluginHostProvider>,
    );

    const secondIframe = container.querySelector("iframe");
    expect(secondIframe).not.toBeNull();
    // Different React identity proves the subtree was torn down and
    // remounted (rather than the iframe element merely re-rendered).
    expect(secondIframe).not.toBe(firstHandle);
    cleanup();
  });

  it("treats deviceId=null as a stable 'fleet' subtree", () => {
    const contributions = [mkContribution("com.example.alpha")];

    const { container, rerender } = render(
      <PluginHostProvider deviceId={null} contributions={contributions}>
        <PluginSlot name="node.detail.tab" />
      </PluginHostProvider>,
    );

    const firstIframe = container.querySelector("iframe") as HTMLIFrameElement;
    expect(firstIframe).not.toBeNull();

    // Re-render with the same null deviceId; the subtree should be
    // preserved (no remount, same iframe element identity).
    rerender(
      <PluginHostProvider deviceId={null} contributions={contributions}>
        <PluginSlot name="node.detail.tab" />
      </PluginHostProvider>,
    );

    const secondIframe = container.querySelector("iframe");
    expect(secondIframe).toBe(firstIframe);
    cleanup();
  });

  it("fires prefetchToken once per installed plugin on mount", () => {
    const prefetch = vi.fn();
    const contributions = [
      mkContribution("com.example.alpha"),
      // Same pluginId, different panel: should still mint exactly one token.
      { ...mkContribution("com.example.alpha"), panelId: "panel-2" },
      mkContribution("com.example.beta"),
    ];

    render(
      <PluginHostProvider
        deviceId="drone-1"
        contributions={contributions}
        prefetchToken={prefetch}
      >
        <PluginSlot name="node.detail.tab" />
      </PluginHostProvider>,
    );

    expect(prefetch).toHaveBeenCalledTimes(2);
    const calledPluginIds = prefetch.mock.calls.map(
      (c) => (c[0] as { pluginId: string }).pluginId,
    );
    expect(calledPluginIds.sort()).toEqual([
      "com.example.alpha",
      "com.example.beta",
    ]);
    expect(prefetch.mock.calls[0]![0]).toMatchObject({ deviceId: "drone-1" });
    cleanup();
  });
});
