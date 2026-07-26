/**
 * @license GPL-3.0-only
 *
 * Tests for the fleet-scoped plugin contribution producer. Covers:
 *   - demo mode surfaces the fleet mock fixtures (one per fleet slot), since
 *     the live producer returns [] in demo
 *   - a slot narrow returns only that slot's contribution
 *   - each demo fixture carries the matching `ui.slot.<id>` capability so the
 *     slot's capability gate admits it
 *   - non-demo mode delegates to the live producer (passes through its value)
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";

import { slotToCapability, type PluginSlotName } from "@/lib/plugins/types";

const { demoRef, liveRef } = vi.hoisted(() => ({
  demoRef: { value: false },
  liveRef: { value: [] as unknown[] },
}));

vi.mock("@/lib/utils", async (orig) => {
  const actual = await orig<typeof import("@/lib/utils")>();
  return { ...actual, isDemoMode: () => demoRef.value };
});

// The live producer is exercised by its own tests; stub it so this test
// isolates the fleet wrapper's demo-mock + slot-narrow + delegation behavior.
vi.mock("@/hooks/use-plugin-contributions", () => ({
  usePluginContributions: () => liveRef.value,
}));

import { useFleetPluginContributions } from "@/hooks/use-fleet-plugin-contributions";
import { getDemoFleetPluginContributions } from "@/mock/mock-plugins";

const FLEET_SLOTS: PluginSlotName[] = [
  "settings.section",
  "fc.tab",
  "hardware.tab",
  "mission.template",
  "map.overlay",
  "notification.channel",
];

describe("useFleetPluginContributions", () => {
  beforeEach(() => {
    demoRef.value = false;
    liveRef.value = [];
  });

  it("returns one demo contribution per fleet slot in demo mode", () => {
    demoRef.value = true;
    const { result } = renderHook(() => useFleetPluginContributions());
    const slots = new Set(result.current.map((c) => c.slot));
    for (const slot of FLEET_SLOTS) {
      expect(slots.has(slot)).toBe(true);
    }
  });

  it("narrows to a single slot when asked", () => {
    demoRef.value = true;
    const { result } = renderHook(() =>
      useFleetPluginContributions("settings.section"),
    );
    expect(result.current.length).toBe(1);
    expect(result.current[0].slot).toBe("settings.section");
  });

  it("each demo fixture carries its slot capability so the gate admits it", () => {
    demoRef.value = true;
    for (const slot of FLEET_SLOTS) {
      const { result } = renderHook(() => useFleetPluginContributions(slot));
      expect(result.current.length).toBeGreaterThan(0);
      const cap = slotToCapability(slot);
      for (const c of result.current) {
        expect(c.grantedCapabilities.has(cap)).toBe(true);
      }
    }
  });

  it("demo fixtures expose a loadable bundle URL", () => {
    demoRef.value = true;
    const { result } = renderHook(() => useFleetPluginContributions());
    for (const c of result.current) {
      // A `blob:` URL in the browser (CSP `frame-src 'self' blob:`), or a
      // `data:` URL where the Blob URL API is absent (SSR fallback).
      expect(/^(blob:|data:)/.test(c.bundleUrl)).toBe(true);
    }
  });

  it("the demo fixture set covers exactly the fleet slots", () => {
    const fixtures = getDemoFleetPluginContributions();
    const slots = new Set(fixtures.map((f) => f.slot));
    expect([...slots].sort()).toEqual([...FLEET_SLOTS].sort());
  });

  it("delegates to the live producer when not in demo mode", () => {
    demoRef.value = false;
    const fromLive = [{ slot: "settings.section", pluginId: "p" }];
    liveRef.value = fromLive;
    const { result } = renderHook(() => useFleetPluginContributions());
    expect(result.current).toBe(fromLive);
  });
});
