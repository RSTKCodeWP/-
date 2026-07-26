"use client";

import {
  createContext,
  Fragment,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
} from "react";

import type { BridgeHandler } from "@/lib/plugins/bridge";
import { IframeLRU } from "@/lib/plugins/iframe-lru";
import type { PluginSlotName } from "@/lib/plugins/types";

import type { PluginIframeHostHandle } from "./PluginIframeHost";

/**
 * One renderable plugin contribution at a specific slot. The host
 * orchestrator hands these to `<PluginSlot>`, which mounts a
 * `<PluginIframeHost>` per entry. The contribution is the unit of
 * trust: each iframe gets its own granted-cap set, its own handler
 * surface, and its own bundle URL.
 */
export interface PluginSlotContribution {
  pluginId: string;
  /** Stable id within the plugin (`gcs.contributes.panels[].id`). */
  panelId: string;
  /** Blob URL or hosted URL pointing at the plugin's GCS bundle. */
  bundleUrl: string;
  /** Capability ids the operator has granted for this plugin. */
  grantedCapabilities: ReadonlySet<string>;
  /** Per-method dispatchers wired to host services. */
  handlers: Record<string, BridgeHandler>;
  /** Optional theme variables forwarded into the iframe on mount. */
  themeVars?: Record<string, string>;
  /** Optional class list applied to the iframe element. */
  iframeClassName?: string;
  /** Title attribute for assistive tech. Defaults to pluginId/panelId. */
  title?: string;
  /**
   * Stable install id for this plugin record. Used as the LRU key in
   * the drone-detail slot so revoke/install cycles map to a single
   * entry. Falls back to `pluginId` if the caller omits it.
   */
  pluginInstallId?: string;
}

/**
 * Optional adapter for prefetching capability tokens. The caller
 * supplies the real implementation (see `use-capability-token.ts`);
 * the provider takes a function so the wiring stays
 * inversion-of-control and tests can stub it out. The provider calls
 * this once per installed plugin on mount; the returned promise is
 * fire-and-forget (tokens land in the bridge's own cache).
 */
export type PrefetchCapabilityToken = (input: {
  pluginId: string;
  deviceId: string | null;
  grantedCapabilities: ReadonlySet<string>;
}) => Promise<void> | void;

interface PluginHostContextValue {
  /** Contributions keyed by slot name. Slots not in the map are empty. */
  bySlot: ReadonlyMap<PluginSlotName, ReadonlyArray<PluginSlotContribution>>;
  /** Drone the provider is currently scoped to, or null for fleet-wide. */
  deviceId: string | null;
  /** Register / unregister iframe-host refs for drone-switch coordination. */
  registerIframeHost: (
    pluginInstallId: string,
    handle: PluginIframeHostHandle | null,
  ) => void;
  /** Snapshot of currently-registered iframe hosts. */
  getIframeHosts: () => ReadonlyMap<string, PluginIframeHostHandle>;
  /** LRU shared across all per-drone iframe slots in this provider. */
  iframeLru: IframeLRU;
}

const PluginHostContext = createContext<PluginHostContextValue | null>(null);

interface PluginHostProviderProps {
  /**
   * Flat contribution list keyed by plugin/panel. The provider groups
   * them by slot for `<PluginSlot>` consumption. The list is expected
   * to come from a Convex query joined with the live plugin manifest;
   * the provider stays presentational so the wiring is testable.
   */
  contributions: ReadonlyArray<
    PluginSlotContribution & { slot: PluginSlotName }
  >;
  /**
   * The drone this provider is scoped to. When non-null, the entire
   * provider subtree is keyed by this id so React unmounts every
   * descendant on drone switch. Pass `null` for fleet-wide slots
   * (settings, hardware list, etc.) where the provider behaves as a
   * single long-lived host.
   */
  deviceId?: string | null;
  /**
   * Optional token prefetcher. The provider calls this once per
   * installed plugin shortly after mount so iframes do not wait for
   * tokens on first RPC.
   */
  prefetchToken?: PrefetchCapabilityToken;
  /**
   * Capacity for the per-provider LRU cache of mounted iframes. The
   * spec caps this at 8; tests pass smaller numbers.
   */
  lruCapacity?: number;
  children: React.ReactNode;
}

/**
 * Top-level provider that hands per-slot contributions to descendant
 * `<PluginSlot>` instances. The tree shape is deliberate: one provider
 * near the root, slots scattered across the chrome and tabs.
 *
 * When `deviceId` is set, the children are wrapped in a keyed
 * `Fragment` so React tears the subtree down end-to-end on drone
 * switch. The switcher is responsible for pausing iframes (giving
 * plugins a 300 ms grace to persist state) before triggering the key
 * change.
 */
export function PluginHostProvider({
  contributions,
  deviceId = null,
  prefetchToken,
  lruCapacity = 8,
  children,
}: PluginHostProviderProps) {
  const bySlot = useMemo<
    ReadonlyMap<PluginSlotName, ReadonlyArray<PluginSlotContribution>>
  >(() => {
    const map = new Map<
      PluginSlotName,
      Array<PluginSlotContribution>
    >();
    for (const c of contributions) {
      const list = map.get(c.slot);
      const entry: PluginSlotContribution = {
        pluginId: c.pluginId,
        panelId: c.panelId,
        bundleUrl: c.bundleUrl,
        grantedCapabilities: c.grantedCapabilities,
        handlers: c.handlers,
        themeVars: c.themeVars,
        iframeClassName: c.iframeClassName,
        title: c.title,
        pluginInstallId: c.pluginInstallId ?? c.pluginId,
      };
      if (list) list.push(entry);
      else map.set(c.slot, [entry]);
    }
    return map;
  }, [contributions]);

  // Per-provider LRU. Keyed by deviceId via React subtree reset so
  // each drone gets a fresh cache; old entries are released when the
  // outer Fragment unmounts (see clear() in the teardown effect).
  const lruRef = useRef<IframeLRU | null>(null);
  if (lruRef.current === null) {
    lruRef.current = new IframeLRU(lruCapacity);
  }
  const iframeLru = lruRef.current;

  // Refs for iframe hosts so the switcher can call pause()/resume()
  // without prop drilling. Cleared on every drone switch via the
  // Fragment key reset (the registry lives inside the keyed subtree).
  const hostsRef = useRef(new Map<string, PluginIframeHostHandle>());

  const registerIframeHost = useCallback(
    (pluginInstallId: string, handle: PluginIframeHostHandle | null) => {
      if (handle === null) {
        hostsRef.current.delete(pluginInstallId);
      } else {
        hostsRef.current.set(pluginInstallId, handle);
      }
    },
    [],
  );

  const getIframeHosts = useCallback(
    () => hostsRef.current as ReadonlyMap<string, PluginIframeHostHandle>,
    [],
  );

  // Token prefetch on mount. We only fire for the currently-mounted
  // contributions; revoke/install changes during the provider's
  // lifetime are handled by the capability-token hook attached at the
  // bridge layer.
  useEffect(() => {
    if (!prefetchToken) return;
    // Dedupe by pluginId so we don't issue 2 tokens for a plugin that
    // contributes to multiple slots.
    const seen = new Set<string>();
    for (const list of bySlot.values()) {
      for (const c of list) {
        if (seen.has(c.pluginId)) continue;
        seen.add(c.pluginId);
        try {
          void prefetchToken({
            pluginId: c.pluginId,
            deviceId,
            grantedCapabilities: c.grantedCapabilities,
          });
        } catch (err) {
          // Token prefetch is best-effort; the bridge will mint on
          // demand if we miss here.
          console.warn("plugin_token_prefetch_failed", {
            pluginId: c.pluginId,
            error: err instanceof Error ? err.message : String(err),
          });
        }
      }
    }
  }, [bySlot, deviceId, prefetchToken]);

  // Teardown: when the provider unmounts (drone switch via key reset,
  // or unmount of the host page) clear the LRU so every iframe entry
  // gets its unmount callback. Component unmount in React fires this
  // cleanup after children have unmounted, so the callbacks here
  // serve as a safety net rather than the primary teardown path.
  useEffect(() => {
    const lru = iframeLru;
    return () => {
      lru.clear();
    };
  }, [iframeLru]);

  const value = useMemo<PluginHostContextValue>(
    () => ({
      bySlot,
      deviceId,
      registerIframeHost,
      getIframeHosts,
      iframeLru,
    }),
    [bySlot, deviceId, registerIframeHost, getIframeHosts, iframeLru],
  );

  // The Fragment key makes drone switch a full subtree reset: React
  // unmounts every descendant (slots, iframe hosts, plugin state) and
  // mounts a fresh tree against the new deviceId. Fleet-wide use
  // (deviceId=null) collapses to the "fleet" key so the subtree is
  // stable across the app lifetime.
  return (
    <PluginHostContext.Provider value={value}>
      <Fragment key={deviceId ?? "fleet"}>{children}</Fragment>
    </PluginHostContext.Provider>
  );
}

/**
 * Read the contributions registered at one slot. Returns an empty
 * array if no provider is mounted, which lets non-plugin-aware
 * surfaces render without runtime checks.
 */
export function useSlotContributions(
  name: PluginSlotName,
): ReadonlyArray<PluginSlotContribution> {
  const ctx = useContext(PluginHostContext);
  return ctx?.bySlot.get(name) ?? EMPTY_LIST;
}

/**
 * Access the provider's coordination surface (iframe registry + LRU +
 * scoped deviceId). The drone-switcher uses this to drive the
 * pause/resume protocol; per-drone slot hosts use it to register
 * their iframe refs and to call `IframeLRU.add/touch`.
 *
 * Returns `null` when no provider is mounted, so call sites can
 * gracefully no-op outside the plugin host context.
 */
export function usePluginHost(): PluginHostContextValue | null {
  return useContext(PluginHostContext);
}

const EMPTY_LIST: ReadonlyArray<PluginSlotContribution> = Object.freeze([]);
