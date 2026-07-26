"use client";

/**
 * @module use-plugin-contributions
 * @description The live plugin contribution producer. Joins a drone's
 * (or the fleet-wide) enabled plugin installs from
 * `cmdPlugins.listForDeviceWithDetail` with each install's signed GCS
 * bundle blob and a per-plugin handler surface, and returns a stable
 * sorted list of `PluginSlotContribution & { slot }` ready to feed a
 * `<PluginHostProvider>`.
 *
 * This is the keystone that makes an installed + enabled + permission-
 * granted plugin actually mount as a live sandboxed iframe. The hook is
 * inert by default: it returns `[]` until the operator installs, enables,
 * and grants a plugin (the natural gate — no extra feature flag).
 *
 * Lifecycle the hook owns:
 *   - Bundle blobs: the Convex query hands back a short-lived SIGNED URL
 *     per install; a blob URL is null-origin and is what the sandboxed
 *     iframe needs, so we `loadPluginBundle()` each signed URL into a
 *     blob in an effect, cache it by `(installId, version)`, and revoke
 *     it when the install set changes or the hook unmounts. A
 *     contribution is omitted until its blob is ready, so no iframe ever
 *     mounts against an empty src.
 *   - Handlers: `buildPluginHandlers()` is built once per `(pluginId,
 *     deviceId)`, cached, and `dispose()`d when the plugin leaves the set
 *     or the hook unmounts (it tears down any telemetry subscriptions the
 *     plugin opened).
 *
 * The Convex query reference is hand-rolled via `makeFunctionReference`
 * so this file compiles before `api.d.ts` regenerates with the new
 * `cmdPlugins:listForDeviceWithDetail` path. The runtime resolves the
 * same way once the generated api picks the function up. Mirrors the
 * pattern in `use-drone-plugin-contributions.ts`.
 *
 * @license GPL-3.0-only
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { makeFunctionReference } from "convex/server";
import { useConvex } from "convex/react";
import { useTranslations } from "next-intl";

import JSZip from "jszip";

import { isDemoMode } from "@/lib/utils";
import { useConvexSkipQuery } from "@/hooks/use-convex-skip-query";
import { useAuthStore } from "@/stores/auth-store";
import { useLocalAgentPlugins } from "@/hooks/use-local-agent-plugins";
import { loadPluginBundle } from "@/lib/plugins/bundle-loader";
import { PluginAgentClient } from "@/lib/agent/plugin-client";
import { buildIframeHtml } from "@/components/plugins/transports/finalize-gcs-install";
import { buildPluginHandlers } from "@/lib/plugins/handlers";
import type { BridgeHandler } from "@/lib/plugins/bridge";
import type { PluginSlotContribution } from "@/components/plugins/PluginHostProvider";
import {
  PLUGIN_SLOTS,
  type PluginSlotName,
  type PairedNodeProfile,
} from "@/lib/plugins/types";

/** Slot fallback sort hint, matching the slot-13 contract default. */
const DEFAULT_ORDER = 60;

/** A renderable contribution carrying the slot it mounts into. */
type SlottedContribution = PluginSlotContribution & { slot: PluginSlotName };

/** Where this install's GCS iframe bundle comes from. Cloud installs hand
 * back a short-lived signed Convex URL; local-first drone installs are served
 * by the LAN agent that unpacked the archive; local-first fleet / GCS-only
 * installs come from the published archive via the same-origin proxy. */
type BundleSource =
  | { kind: "url"; url: string }
  | {
      kind: "agent";
      agentUrl: string;
      apiKey: string;
      pluginId: string;
      entrypoint: string;
    }
  | { kind: "archive"; archiveUrl: string; entrypoint: string };

/** Source-agnostic install row the blob + handler + builder pipeline reads,
 * unifying the Convex query rows and the local agent-detail rows. */
interface NormalizedRow {
  installId: string;
  pluginId: string;
  version: string;
  name: string;
  grantedCaps: string[];
  gcsContributes: Array<{
    slot: string;
    panelId: string;
    title?: string;
    icon?: string;
    order?: number;
    profile?: PairedNodeProfile[];
  }>;
  /** Null when the install has no loadable GCS bundle yet (agent-only, or
   * a cloud row whose bundle has not finished uploading). */
  bundle: BundleSource | null;
}

/** Local install statuses that mount a contribution (matches the cloud
 * `listForDeviceWithDetail` server filter). */
function isLiveStatus(status: string): boolean {
  return status === "enabled" || status === "running";
}

/** A `node.detail.tab` mounts on a node when its `profile` narrowing is absent
 * or includes the node's resolved profile. Non-tab slots are never narrowed.
 * Matches `tabOffersOnProfile` in `use-drone-plugin-contributions.ts`. */
function slotOffersOnProfile(
  slot: string,
  profile: PairedNodeProfile[] | undefined,
  nodeProfile: PairedNodeProfile | undefined,
): boolean {
  if (slot !== "node.detail.tab") return true;
  if (!profile || profile.length === 0) return true;
  if (!nodeProfile) return true;
  return profile.includes(nodeProfile);
}

/**
 * Load + wrap a plugin's GCS bundle served by its LAN agent into a
 * null-origin blob URL — the local-first analogue of `loadPluginBundle`
 * for a signed Convex URL. The agent serves the raw ESM module; the
 * sandboxed iframe needs an HTML document, so we wrap it with
 * `buildIframeHtml` (the same shell the cloud upload path uses) before
 * minting the blob.
 */
async function loadAgentBundle(
  src: Extract<BundleSource, { kind: "agent" }>,
): Promise<{ blobUrl: string; revoke: () => void }> {
  const client = new PluginAgentClient(src.agentUrl, src.apiKey);
  const bundleJs = await client.getGcsBundle(src.pluginId, src.entrypoint);
  const html = buildIframeHtml(bundleJs);
  const blob = new Blob([html], { type: "text/html" });
  const blobUrl = URL.createObjectURL(blob);
  return { blobUrl, revoke: () => URL.revokeObjectURL(blobUrl) };
}

/**
 * Load + wrap a fleet / GCS-only plugin's GCS bundle from its published
 * archive into a null-origin blob URL — the local-first analogue of
 * `loadAgentBundle` for a plugin with no drone. The archive is fetched
 * through the same-origin `/api/registry-archive` proxy (the release CDN does
 * not promise cross-origin reads), the built ESM module is extracted with
 * JSZip, and it is wrapped in the same null-origin HTML shell the cloud upload
 * path uses before minting the blob. Mirrors `finalizeGcsInstall`'s extract +
 * wrap, the difference being we mint a blob here instead of uploading to Convex.
 */
async function loadArchiveBundle(
  src: Extract<BundleSource, { kind: "archive" }>,
): Promise<{ blobUrl: string; revoke: () => void }> {
  const res = await fetch(
    `/api/registry-archive?url=${encodeURIComponent(src.archiveUrl)}`,
  );
  if (!res.ok) {
    throw new Error(`archive fetch failed: HTTP ${res.status}`);
  }
  const archive = await res.blob();
  const zip = await JSZip.loadAsync(archive);
  const rel = src.entrypoint.replace(/^\.\//, "");
  const entry = zip.file(rel) ?? zip.file(`./${rel}`);
  if (!entry) {
    throw new Error(`archive is missing ${rel}`);
  }
  const bundleJs = await entry.async("string");
  const html = buildIframeHtml(bundleJs);
  const blob = new Blob([html], { type: "text/html" });
  const blobUrl = URL.createObjectURL(blob);
  return { blobUrl, revoke: () => URL.revokeObjectURL(blobUrl) };
}

/**
 * One install row returned by `cmdPlugins:listForDeviceWithDetail`. The
 * Convex `installId` is an `Id<"cmd_pluginInstalls">` that serializes to a
 * string on the wire; declaring it `string` here is exact enough for the
 * hand-rolled reference and `String(...)` keeps it safe either way.
 */
interface InstallDetailRow {
  installId: string;
  pluginId: string;
  version: string;
  name: string;
  grantedCaps: string[];
  gcsContributes: Array<{
    slot: string;
    panelId: string;
    title?: string;
    icon?: string;
    order?: number;
    profile?: PairedNodeProfile[];
  }>;
  bundleUrl: string | null;
}

/**
 * Hand-rolled reference for the `cmdPlugins:listForDeviceWithDetail`
 * query. Once `api.d.ts` exports the typed descriptor, this resolves to
 * the same value the generated `communityApi.plugins.*` export yields.
 */
const listForDeviceWithDetailRef = makeFunctionReference<
  "query",
  { deviceId?: string },
  InstallDetailRow[]
>("cmdPlugins:listForDeviceWithDetail");

const EMPTY: ReadonlyArray<SlottedContribution> = Object.freeze([]);

const KNOWN_SLOTS = new Set<string>(PLUGIN_SLOTS);
function isKnownSlot(slot: string): slot is PluginSlotName {
  return KNOWN_SLOTS.has(slot);
}

/** A bundle blob held for one install, keyed by install id. */
interface BlobEntry {
  version: string;
  blobUrl: string;
  revoke: () => void;
}

/** A handler surface held for one plugin, keyed by plugin id. */
interface HandlerEntry {
  deviceId: string | null;
  handlers: Record<string, BridgeHandler>;
  dispose: () => void;
}

/**
 * Live plugin contributions for a drone (or fleet-wide when `deviceId` is
 * null), optionally narrowed to a single `slot`. `nodeProfile` is the
 * resolved profile of the node these contributions mount on; a
 * `node.detail.tab` that declares a `profile` narrowing is dropped when the
 * node's profile is not in the set (so a ground-station-only tab's iframe
 * never mounts on a drone). Other slots ignore `nodeProfile`. Returns a stable
 * memoized array (same identity while the install set, loaded blobs, and
 * built handlers are unchanged) sorted by manifest `order` then
 * `pluginId`. Returns `[]` when unauthenticated, in demo mode, before the
 * query resolves, or while bundle blobs are still loading.
 */
export function usePluginContributions(
  deviceId: string | null,
  slot?: PluginSlotName,
  nodeProfile?: PairedNodeProfile,
): ReadonlyArray<SlottedContribution> {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const installs = useConvexSkipQuery(listForDeviceWithDetailRef, {
    args: { deviceId: deviceId ?? undefined },
    enabled: isAuthenticated,
  });

  // Local-first source (Rule 39): when signed out, the agent that
  // unpacked the archive both reports the install detail AND serves the
  // GCS bundle, so the iframe mounts with no cloud. Null in cloud/demo.
  const localDetail = useLocalAgentPlugins(deviceId);

  // Unify the two sources into one row shape. Everything downstream (blob
  // lifecycle, handler lifecycle, contribution builder) reads `rows`, so
  // the only difference between cloud and local is the bundle SOURCE.
  const rows = useMemo<NormalizedRow[] | null>(() => {
    if (isDemoMode()) return [];
    if (isAuthenticated) {
      if (!installs) return null;
      return installs.map((r) => ({
        installId: String(r.installId),
        pluginId: r.pluginId,
        version: r.version,
        name: r.name,
        grantedCaps: r.grantedCaps,
        gcsContributes: r.gcsContributes,
        bundle:
          typeof r.bundleUrl === "string" && r.bundleUrl.length > 0
            ? { kind: "url", url: r.bundleUrl }
            : null,
      }));
    }
    if (!localDetail) return null;
    return localDetail
      .filter((r) => isLiveStatus(r.status))
      .map((r) => {
        let bundle: BundleSource | null = null;
        if (r.bundle?.kind === "agent") {
          bundle = {
            kind: "agent",
            agentUrl: r.bundle.agentUrl,
            apiKey: r.bundle.apiKey,
            pluginId: r.pluginId,
            entrypoint: r.bundle.entrypoint,
          };
        } else if (r.bundle?.kind === "archive") {
          bundle = {
            kind: "archive",
            archiveUrl: r.bundle.archiveUrl,
            entrypoint: r.bundle.entrypoint,
          };
        }
        return {
          installId: r.installId,
          pluginId: r.pluginId,
          version: r.version,
          name: r.name,
          grantedCaps: r.grantedCaps,
          gcsContributes: r.gcsContributes,
          bundle,
        };
      });
  }, [isAuthenticated, installs, localDetail]);

  // Stable translator for the plugin handler factory. next-intl's `t`
  // identity can change across renders; the ref keeps the factory's
  // `translate` dependency stable so handlers are not rebuilt needlessly.
  const t = useTranslations();
  const tRef = useRef(t);
  useEffect(() => {
    tRef.current = t;
  }, [t]);
  const translate = useCallback(
    (key: string, params?: Record<string, string | number>): string =>
      tRef.current(key, params),
    [],
  );

  // Convex caller for cloud.read. The handler enforces the read allowlist +
  // arg validation + rate limit BEFORE this runs, so only the few public
  // allowlisted queries ever reach here.
  const convex = useConvex();
  const cloudQuery = useCallback(
    (fn: string, args: Record<string, unknown>): Promise<unknown> =>
      convex.query(
        makeFunctionReference<"query", Record<string, unknown>, unknown>(fn),
        args,
      ),
    [convex],
  );

  // ── Bundle blob lifecycle ───────────────────────────────────────────
  const blobCacheRef = useRef<Map<string, BlobEntry>>(new Map());
  const [blobs, setBlobs] = useState<ReadonlyMap<string, string>>(
    () => new Map(),
  );

  // Installs that ship a loadable GCS bundle, the only ones that can mount.
  const loadTargets = useMemo(() => {
    if (!rows) return [] as Array<{
      installId: string;
      version: string;
      bundle: BundleSource;
    }>;
    return rows
      .filter((r): r is NormalizedRow & { bundle: BundleSource } =>
        Boolean(r.bundle),
      )
      .map((r) => ({
        installId: r.installId,
        version: r.version,
        bundle: r.bundle,
      }));
  }, [rows]);

  useEffect(() => {
    let cancelled = false;
    const cache = blobCacheRef.current;
    const wanted = new Map(loadTargets.map((t) => [t.installId, t]));

    // Revoke entries no longer wanted, or wanted at a different version.
    for (const [installId, entry] of Array.from(cache.entries())) {
      const want = wanted.get(installId);
      if (!want || want.version !== entry.version) {
        entry.revoke();
        cache.delete(installId);
      }
    }

    const publish = () => {
      const next = new Map<string, string>();
      for (const [installId, entry] of cache.entries()) {
        next.set(installId, entry.blobUrl);
      }
      setBlobs(next);
    };

    const toLoad = loadTargets.filter((t) => !cache.has(t.installId));
    if (toLoad.length === 0) {
      // Covers the revoke-only case (an install left the set).
      publish();
      return () => {
        cancelled = true;
      };
    }

    void Promise.all(
      toLoad.map(async (target) => {
        try {
          const { blobUrl, revoke } =
            target.bundle.kind === "agent"
              ? await loadAgentBundle(target.bundle)
              : target.bundle.kind === "archive"
                ? await loadArchiveBundle(target.bundle)
                : await loadPluginBundle(target.bundle.url);
          // Drop the load if the hook moved on (unmount or set change).
          if (cancelled || !wanted.has(target.installId)) {
            revoke();
            return;
          }
          cache.set(target.installId, {
            version: target.version,
            blobUrl,
            revoke,
          });
        } catch (err) {
          console.warn("plugin_bundle_load_failed", {
            installId: target.installId,
            error: err instanceof Error ? err.message : String(err),
          });
        }
      }),
    ).then(() => {
      if (cancelled) return;
      publish();
    });

    return () => {
      cancelled = true;
    };
  }, [loadTargets]);

  // ── Handler lifecycle ───────────────────────────────────────────────
  const handlerCacheRef = useRef<Map<string, HandlerEntry>>(new Map());
  const [handlers, setHandlers] = useState<
    ReadonlyMap<string, Record<string, BridgeHandler>>
  >(() => new Map());

  const activePluginIds = useMemo(() => {
    if (!rows) return [] as string[];
    return Array.from(new Set(rows.map((r) => r.pluginId)));
  }, [rows]);
  const activePluginIdsKey = useMemo(
    () => [...activePluginIds].sort().join("|"),
    [activePluginIds],
  );

  useEffect(() => {
    const cache = handlerCacheRef.current;
    const wanted = new Set(activePluginIds);

    // Dispose handlers for plugins that left the set or moved drone.
    for (const [pluginId, entry] of Array.from(cache.entries())) {
      if (!wanted.has(pluginId) || entry.deviceId !== deviceId) {
        entry.dispose();
        cache.delete(pluginId);
      }
    }

    // Build handlers for newly-present plugins. The factory has no
    // immediate side effects (telemetry subscriptions open only when the
    // iframe calls telemetry.subscribe), so this is safe in an effect.
    for (const pluginId of activePluginIds) {
      if (cache.has(pluginId)) continue;
      const built = buildPluginHandlers(pluginId, deviceId, {
        translate,
        cloudQuery,
      });
      cache.set(pluginId, {
        deviceId,
        handlers: built.handlers,
        dispose: built.dispose,
      });
    }

    const next = new Map<string, Record<string, BridgeHandler>>();
    for (const [pluginId, entry] of cache.entries()) {
      next.set(pluginId, entry.handlers);
    }
    setHandlers(next);
    // activePluginIdsKey captures membership; deviceId rebuilds on switch.
  }, [activePluginIdsKey, deviceId, translate, cloudQuery, activePluginIds]);

  // ── Teardown: revoke every blob + dispose every handler on unmount ───
  useEffect(() => {
    const blobCache = blobCacheRef.current;
    const handlerCache = handlerCacheRef.current;
    return () => {
      for (const entry of blobCache.values()) entry.revoke();
      blobCache.clear();
      for (const entry of handlerCache.values()) entry.dispose();
      handlerCache.clear();
    };
  }, []);

  // ── Build the stable, sorted contribution list ──────────────────────
  return useMemo(() => {
    // demo mode does not mount real plugin iframes
    if (isDemoMode()) return EMPTY;
    if (!rows) return EMPTY;

    const built: Array<{ contribution: SlottedContribution; order: number }> =
      [];
    for (const row of rows) {
      const blobUrl = blobs.get(row.installId);
      if (!blobUrl) continue; // omit until the bundle blob is ready
      const pluginHandlers = handlers.get(row.pluginId);
      if (!pluginHandlers) continue; // omit until handlers are built
      const grantedCapabilities = new Set(row.grantedCaps);
      for (const entry of row.gcsContributes) {
        if (slot && entry.slot !== slot) continue;
        if (!isKnownSlot(entry.slot)) continue;
        // Profile-narrow a node.detail.tab iframe to the node it mounts on,
        // matching the header/body filter so an off-profile tab never mounts.
        if (!slotOffersOnProfile(entry.slot, entry.profile, nodeProfile)) {
          continue;
        }
        built.push({
          order: typeof entry.order === "number" ? entry.order : DEFAULT_ORDER,
          contribution: {
            slot: entry.slot,
            pluginId: row.pluginId,
            panelId: entry.panelId,
            title: entry.title ?? row.name,
            bundleUrl: blobUrl,
            grantedCapabilities,
            handlers: pluginHandlers,
            pluginInstallId: row.installId,
          },
        });
      }
    }

    if (built.length === 0) return EMPTY;
    built.sort((a, b) => {
      if (a.order !== b.order) return a.order - b.order;
      return a.contribution.pluginId.localeCompare(b.contribution.pluginId);
    });
    return built.map((b) => b.contribution);
  }, [rows, blobs, handlers, slot, nodeProfile]);
}
