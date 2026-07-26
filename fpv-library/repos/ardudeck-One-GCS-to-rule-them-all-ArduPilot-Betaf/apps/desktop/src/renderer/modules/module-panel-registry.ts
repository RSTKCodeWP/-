/**
 * Registry of panels contributed by modules (host.panels). The host-owned
 * ModuleDock consults this to render one collision-free tray of launcher chips,
 * so multiple modules can't fight over the same corner the way the raw
 * floatingOverlay let them.
 */

import type { ComponentType } from 'react';
import type { ModulePanelRegistration } from '@ardudeck/module-sdk';

export interface RegisteredPanel extends ModulePanelRegistration {
  slug: string;
  component: ComponentType;
}

const registry = new Map<string, RegisteredPanel>();
const bySlug = new Map<string, Set<string>>();
const listeners = new Set<() => void>();

// Cached, stable-reference snapshot. useSyncExternalStore compares snapshots
// with Object.is, so listModulePanels() MUST return the same array reference
// until the registry actually changes - otherwise it re-renders every frame
// (infinite loop). Rebuilt only on mutation.
let snapshot: RegisteredPanel[] = [];

function changed(): void {
  snapshot = Array.from(registry.values());
  for (const l of listeners) l();
}

export function subscribeModulePanels(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function registerModulePanel(slug: string, reg: ModulePanelRegistration): void {
  if (!reg?.id) throw new Error(`[module:${slug}] panel needs an id`);
  // Namespace the dock key by slug so two modules can't clobber each other.
  const key = `${slug}:${reg.id}`;
  registry.set(key, { ...reg, slug });
  let ids = bySlug.get(slug);
  if (!ids) {
    ids = new Set();
    bySlug.set(slug, ids);
  }
  ids.add(reg.id);
  changed();
}

export function unregisterModulePanel(slug: string, id: string): void {
  if (!bySlug.get(slug)?.has(id)) return;
  registry.delete(`${slug}:${id}`);
  bySlug.get(slug)?.delete(id);
  changed();
}

/** Remove every panel a module registered (module unload/reload). */
export function unregisterModulePanels(slug: string): void {
  const ids = bySlug.get(slug);
  if (!ids) return;
  for (const id of ids) registry.delete(`${slug}:${id}`);
  bySlug.delete(slug);
  changed();
}

export function listModulePanels(): RegisteredPanel[] {
  return snapshot;
}
