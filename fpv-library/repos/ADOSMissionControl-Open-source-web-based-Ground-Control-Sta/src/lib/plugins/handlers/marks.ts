/**
 * Composited cockpit draw-layer handlers: `cockpit.marks` (replace this
 * plugin's marks) and `cockpit.marks.clear` (drop them).
 *
 * A plugin that draws over the video posts vector MARKS instead of stacking its
 * own overlay iframe; the host validates them (untrusted iframe input) and
 * writes them into the shared `cockpit-marks-store` under a per-plugin source
 * id, and `CockpitMarkLayer` composites every source's marks into ONE
 * letterbox-correct overlay. `dispose()` clears the plugin's marks on unmount /
 * drone switch so a dead plugin never leaves stale annotations on the video.
 *
 * The bridge gates `ui.slot.video-overlay` before `cockpit.marks` runs;
 * `cockpit.marks.clear` is always-allowed (clearing needs no grant), mirroring
 * the unsubscribe methods.
 *
 * @module plugins/handlers/marks
 * @license GPL-3.0-only
 */

import type { BridgeHandler } from "@/lib/plugins/bridge";
import { parseCockpitMarks } from "@/lib/cockpit/marks";
import { useCockpitMarksStore } from "@/stores/cockpit-marks-store";

/** The composited-marks source id for one plugin. */
export function pluginMarkSourceId(pluginId: string): string {
  return `plugin:${pluginId}`;
}

/**
 * Build the mark handlers for one plugin, plus a `dispose()` that drops its
 * marks. Marks are namespaced by the source id so two plugins that pick the
 * same local mark id never collide in the composited layer.
 */
export function buildMarksHandlers(pluginId: string): {
  handlers: Record<string, BridgeHandler>;
  dispose: () => void;
} {
  const sourceId = pluginMarkSourceId(pluginId);

  const setMarks: BridgeHandler = (args) => {
    const marks = parseCockpitMarks((args as { marks?: unknown })?.marks);
    // Namespace ids to keep them unique across sources in the flattened layer.
    const namespaced = marks.map((m) => ({ ...m, id: `${sourceId}::${m.id}` }));
    useCockpitMarksStore.getState().setMarks(sourceId, namespaced);
    return { ok: true, count: namespaced.length };
  };

  const clearMarks: BridgeHandler = () => {
    useCockpitMarksStore.getState().clearSource(sourceId);
    return { ok: true };
  };

  return {
    handlers: {
      "cockpit.marks": setMarks,
      "cockpit.marks.clear": clearMarks,
    },
    dispose: () => {
      useCockpitMarksStore.getState().clearSource(sourceId);
    },
  };
}
