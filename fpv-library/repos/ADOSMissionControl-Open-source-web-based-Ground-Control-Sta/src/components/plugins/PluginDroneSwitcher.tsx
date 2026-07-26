"use client";

import { useEffect, useRef, useState } from "react";

import { useDroneManager } from "@/stores/drone-manager";

import { LIFECYCLE_ACK_TIMEOUT_MS } from "./PluginIframeHost";
import {
  PluginHostProvider,
  usePluginHost,
  type PluginSlotContribution,
  type PrefetchCapabilityToken,
} from "./PluginHostProvider";
import type { PluginSlotName } from "@/lib/plugins/types";

/** Warn threshold; the spec targets a 200 ms switch and treats 500 ms as a regression. */
const SWITCH_WARN_THRESHOLD_MS = 500;

interface PluginDroneSwitcherProps {
  /** Flat contribution list, same shape as PluginHostProvider accepts. */
  contributions: ReadonlyArray<
    PluginSlotContribution & { slot: PluginSlotName }
  >;
  /** Optional token prefetcher; passed through to the provider. */
  prefetchToken?: PrefetchCapabilityToken;
  /** Optional LRU capacity override; passed through to the provider. */
  lruCapacity?: number;
  /**
   * Optional grace window override (ms). The pause loop will wait at
   * most this long for the iframes to ACK before triggering the React
   * subtree reset. Defaults to the iframe host's own grace constant.
   */
  graceMs?: number;
  children: React.ReactNode;
}

/**
 * Per-drone scoped plugin host. Watches `selectedDroneId` on the
 * drone-manager store and, on change:
 *
 *   1. Pauses every mounted iframe via its ref handle. Each handle
 *      posts `{type:"lifecycle", method:"pause"}` and resolves on
 *      ACK or after the 300 ms grace window, whichever first.
 *   2. Triggers the provider key change so React unmounts the entire
 *      subtree. The LRU clears on unmount and the drone-detail tab
 *      host lazy-mounts iframes on click against the new device id.
 *
 * Performance target: < 200 ms switch. We instrument with
 * `performance.now()` and log a `plugin_drone_switch_slow` warning
 * when the budget is blown.
 */
export function PluginDroneSwitcher({
  contributions,
  prefetchToken,
  lruCapacity,
  graceMs,
  children,
}: PluginDroneSwitcherProps) {
  const selectedDroneId = useDroneManager((s) => s.selectedDroneId);

  // The deviceId we actually hand to the provider. Updated only after
  // the pause grace completes so the existing subtree gets a chance
  // to flush state before React rips it out.
  const [activeDeviceId, setActiveDeviceId] = useState<string | null>(
    selectedDroneId,
  );

  // Track the most recent intent so a rapid second switch supersedes
  // an in-flight pause without races. The pause loop checks this
  // before committing the new deviceId.
  const pendingDeviceIdRef = useRef<string | null>(selectedDroneId);
  // Hosts ref kept here for tests that want to assert pause was
  // called. The provider owns the canonical map; this ref mirrors the
  // handles only via the bridge below.
  const hostsBridgeRef = useRef<HostsBridge | null>(null);

  useEffect(() => {
    pendingDeviceIdRef.current = selectedDroneId;
    if (selectedDroneId === activeDeviceId) return;

    const grace = graceMs ?? LIFECYCLE_ACK_TIMEOUT_MS;
    const startedAt = performance.now();
    let cancelled = false;

    const swap = async () => {
      const hosts =
        hostsBridgeRef.current?.getHosts() ?? new Map();
      const handles = Array.from(hosts.values());

      // Pause everything in parallel; each handle has its own ACK
      // timeout, and Promise.race here just enforces a switcher-level
      // cap in case a handle never resolves (it always should, but
      // belt-and-suspenders for a buggy iframe host).
      if (handles.length > 0) {
        await Promise.race([
          Promise.all(
            handles.map((h) => {
              try {
                return h.pause();
              } catch {
                return Promise.resolve();
              }
            }),
          ),
          new Promise<void>((resolve) => {
            window.setTimeout(resolve, grace);
          }),
        ]);
      }

      if (cancelled) return;
      // If a newer selection arrived while we were pausing, drop this
      // commit and let the next effect run drive the swap.
      if (pendingDeviceIdRef.current !== selectedDroneId) return;

      setActiveDeviceId(selectedDroneId);

      const elapsed = performance.now() - startedAt;
      // Lower-bound log under info; over-budget bumps to warn so the
      // operator dashboard can surface it. The console.timing alias
      // requested in the plan does not exist in the standard console
      // API; we log a structured event instead which observability
      // tooling can pick up.
      console.info("plugin_drone_switch", {
        from: activeDeviceId,
        to: selectedDroneId,
        elapsedMs: Math.round(elapsed),
      });
      if (elapsed > SWITCH_WARN_THRESHOLD_MS) {
        console.warn("plugin_drone_switch_slow", {
          elapsedMs: Math.round(elapsed),
          thresholdMs: SWITCH_WARN_THRESHOLD_MS,
        });
      }
    };

    void swap();

    return () => {
      cancelled = true;
    };
  }, [selectedDroneId, activeDeviceId, graceMs]);

  return (
    <PluginHostProvider
      deviceId={activeDeviceId}
      contributions={contributions}
      prefetchToken={prefetchToken}
      lruCapacity={lruCapacity}
    >
      <HostsBridgeRegister bridgeRef={hostsBridgeRef} />
      {children}
    </PluginHostProvider>
  );
}

interface HostsBridge {
  getHosts: ReturnType<typeof usePluginHost> extends infer T
    ? T extends { getIframeHosts: infer F }
      ? F
      : never
    : never;
}

/**
 * Internal helper that copies the provider's iframe-host registry
 * accessor into a ref owned by the switcher. We can't call
 * `usePluginHost()` directly from the switcher because the switcher
 * sits *above* the provider in the tree; this child component does
 * the lift from inside.
 */
function HostsBridgeRegister({
  bridgeRef,
}: {
  bridgeRef: React.MutableRefObject<HostsBridge | null>;
}) {
  const host = usePluginHost();
  useEffect(() => {
    if (!host) {
      bridgeRef.current = null;
      return;
    }
    bridgeRef.current = { getHosts: host.getIframeHosts };
    return () => {
      bridgeRef.current = null;
    };
  }, [host, bridgeRef]);
  return null;
}
