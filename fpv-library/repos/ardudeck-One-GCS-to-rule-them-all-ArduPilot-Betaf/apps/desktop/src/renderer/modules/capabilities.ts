import { useMemo } from 'react';
import type { ViewId } from '../stores/navigation-store';
import { useModuleStore } from '../stores/module-store';

/**
 * Built-in features gated behind Hangar cargo.
 *
 * Anything NOT listed here is always available. To put an existing built-in
 * feature behind a cargo, add one entry mapping the cargo slug to what it
 * gates - a whole view, individual HUD widgets, and/or text-OSD elements.
 * NavigationRail, the deep-link handler, the HUD renderers and the OSD
 * element browser all consult this map; no other code change is needed.
 *
 * A gated feature shows only while its cargo is installed AND not toggled
 * off, so the Cargo Bay enable/disable switch governs built-ins too.
 */
export interface Capability {
  /** Hangar cargo slug that enables the features below. */
  slug: string;
  /** A built-in view this cargo gates. */
  viewId?: ViewId;
  /** Built-in fighter-HUD widget ids (see hud-config HUD_WIDGETS). */
  hudWidgets?: string[];
  /** Built-in text-OSD element ids (see osd element-registry). */
  osdElements?: string[];
}

export const CAPABILITIES: Capability[] = [
  // Example (not active): { slug: 'com.ardudeck.area-editor', viewId: 'mission' },
];

const GATED_VIEWS: ReadonlyMap<ViewId, string> = new Map(
  CAPABILITIES.filter((c) => c.viewId).map((c): [ViewId, string] => [c.viewId!, c.slug]),
);

/** True if `viewId` is available given the set of enabled activatable slugs. */
export function isViewAvailable(viewId: ViewId, enabledSlugs: ReadonlySet<string>): boolean {
  const requiredSlug = GATED_VIEWS.get(viewId);
  return !requiredSlug || enabledSlugs.has(requiredSlug);
}

/** Reactive: true when the given cargo is installed and not toggled off. */
export function useCargoEnabled(slug: string): boolean {
  const modules = useModuleStore((s) => s.modules);
  return useMemo(
    () => modules.some((m) => m.slug === slug && m.enabled !== false),
    [modules, slug],
  );
}

/** Ids from the chosen Capability field whose gating cargo is missing or off. */
function useGatedOffIds(field: 'hudWidgets' | 'osdElements'): ReadonlySet<string> {
  const modules = useModuleStore((s) => s.modules);
  return useMemo(() => {
    const off = new Set<string>();
    for (const cap of CAPABILITIES) {
      const ids = cap[field];
      if (!ids?.length) continue;
      const enabled = modules.some((m) => m.slug === cap.slug && m.enabled !== false);
      if (!enabled) for (const id of ids) off.add(id);
    }
    return off;
  }, [modules, field]);
}

/** Reactive: built-in HUD widget ids to hide (their gating cargo is off/absent). */
export function useGatedOffHudWidgets(): ReadonlySet<string> {
  return useGatedOffIds('hudWidgets');
}

/** Reactive: built-in text-OSD element ids to hide (their gating cargo is off/absent). */
export function useGatedOffOsdElements(): ReadonlySet<string> {
  return useGatedOffIds('osdElements');
}

/** Reactive set of activatable module slugs currently enabled on this device. */
export function useEnabledCapabilitySlugs(): ReadonlySet<string> {
  const modules = useModuleStore((s) => s.modules);
  return useMemo(
    () => new Set(modules.filter((m) => m.activatable && m.enabled !== false).map((m) => m.slug)),
    [modules],
  );
}
