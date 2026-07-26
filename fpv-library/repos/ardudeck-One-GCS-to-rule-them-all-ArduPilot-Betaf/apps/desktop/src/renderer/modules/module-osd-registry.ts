/**
 * Registry of OSD character-cell elements contributed by modules (host.osd).
 * The built-in OSD element system (element-registry / element-renderers /
 * osd-store) consults this so module elements appear in the Designer palette
 * and render into the buffer without core owning them.
 *
 * Kept separate from the module host API so the OSD renderers can import it
 * without pulling in the whole renderer host.
 */

import type { OsdElementRegistration } from '@ardudeck/module-sdk';

const registry = new Map<string, OsdElementRegistration>();
const bySlug = new Map<string, Set<string>>();
const listeners = new Set<() => void>();

function emit(): void {
  for (const l of listeners) l();
}

/** Subscribe to registry changes (palette needs to re-render on register). */
export function subscribeModuleOsdElements(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function registerModuleOsdElement(slug: string, reg: OsdElementRegistration): void {
  if (!reg?.id) throw new Error(`[module:${slug}] OSD element needs an id`);
  registry.set(reg.id, reg);
  let ids = bySlug.get(slug);
  if (!ids) {
    ids = new Set();
    bySlug.set(slug, ids);
  }
  ids.add(reg.id);
  emit();
}

export function unregisterModuleOsdElement(slug: string, id: string): void {
  if (!bySlug.get(slug)?.has(id)) return;
  registry.delete(id);
  bySlug.get(slug)?.delete(id);
  emit();
}

/** Remove every OSD element a module registered (module unload/reload). */
export function unregisterModuleOsdElements(slug: string): void {
  const ids = bySlug.get(slug);
  if (!ids) return;
  for (const id of ids) registry.delete(id);
  bySlug.delete(slug);
  emit();
}

export function getModuleOsdElement(id: string): OsdElementRegistration | undefined {
  return registry.get(id);
}

export function listModuleOsdElements(): OsdElementRegistration[] {
  return Array.from(registry.values());
}
