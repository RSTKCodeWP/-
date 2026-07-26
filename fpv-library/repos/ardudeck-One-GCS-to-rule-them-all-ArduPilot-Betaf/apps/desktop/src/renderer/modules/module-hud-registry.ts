/**
 * Registry of toggleable HUD instruments contributed by modules (host.hud).
 * The HUD control panel (HudPanel) consults this so module instruments appear
 * in the Instruments list alongside built-ins, without core owning them. Their
 * on/off state lives in the hud-store like any other widget.
 *
 * Kept separate from the module host API so HudPanel can import it without
 * pulling in the whole renderer host.
 */

import type { HudInstrumentRegistration } from '@ardudeck/module-sdk';

const registry = new Map<string, HudInstrumentRegistration>();
const bySlug = new Map<string, Set<string>>();
const listeners = new Set<() => void>();

function emit(): void {
  for (const l of listeners) l();
}

/** Subscribe to registry changes (the panel re-renders on register/unregister). */
export function subscribeModuleHudInstruments(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function registerModuleHudInstrument(slug: string, reg: HudInstrumentRegistration): void {
  if (!reg?.id) throw new Error(`[module:${slug}] HUD instrument needs an id`);
  registry.set(reg.id, reg);
  let ids = bySlug.get(slug);
  if (!ids) {
    ids = new Set();
    bySlug.set(slug, ids);
  }
  ids.add(reg.id);
  emit();
}

export function unregisterModuleHudInstrument(slug: string, id: string): void {
  if (!bySlug.get(slug)?.has(id)) return;
  registry.delete(id);
  bySlug.get(slug)?.delete(id);
  emit();
}

/** Remove every HUD instrument a module registered (module unload/reload). */
export function unregisterModuleHudInstruments(slug: string): void {
  const ids = bySlug.get(slug);
  if (!ids) return;
  for (const id of ids) registry.delete(id);
  bySlug.delete(slug);
  emit();
}

export function listModuleHudInstruments(): HudInstrumentRegistration[] {
  return Array.from(registry.values());
}
