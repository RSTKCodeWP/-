/**
 * @module map-overlay-z
 * @description Shared z-index scale for floating overlays on the map/globe
 * views (Plan = Leaflet 2D, Simulate = Cesium 3D). One scale for both engines,
 * pinned to the Leaflet-safe high band so it sits above Leaflet's internal
 * panes (which reach ~z-600) and equally above a Cesium canvas.
 * @license GPL-3.0-only
 */

export const MAP_OVERLAY_Z = {
  /** Base cards, badges, banners, readouts. */
  overlay: 900,
  /** Toolbars and docked side panels. */
  panel: 1000,
  /** Popovers opened from a panel (help, layer settings). */
  popover: 1100,
  /** Hover tooltips (matches the ui/tooltip overlay). */
  tooltip: 2000,
} as const;

export type MapOverlayLayer = keyof typeof MAP_OVERLAY_Z;
