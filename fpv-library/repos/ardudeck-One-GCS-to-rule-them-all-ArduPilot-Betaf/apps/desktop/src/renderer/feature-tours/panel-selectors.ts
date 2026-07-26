import type { PanelId } from '../components/panels';

/**
 * Maps a telemetry panel to its data-tour selector in the rendered DOM.
 * Used by the tour manager to verify that a tour's required panels are
 * actually visible before launching. If a panel isn't listed here, the
 * tour manager can't probe it and will trust the bridge's hasPanel check.
 */
export const PANEL_TOUR_SELECTORS: Partial<Record<PanelId, string>> = {
  map: '[data-tour="telemetry-map"]',
  flightControl: '[data-tour="telemetry-flight-control"]',
};

export function findPanelElement(panelId: PanelId): HTMLElement | null {
  const selector = PANEL_TOUR_SELECTORS[panelId];
  if (!selector) return null;
  return document.querySelector<HTMLElement>(selector);
}

export function isPanelVisible(panelId: PanelId): boolean {
  const el = findPanelElement(panelId);
  if (!el) return false;
  const rect = el.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}
