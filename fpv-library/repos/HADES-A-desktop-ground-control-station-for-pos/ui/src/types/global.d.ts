/* The preload bridge surface (electron/preload.ts). Present only under Electron; in a plain
 * browser/dev `window.hades` is undefined and the app falls back to the canned mock mission. */
export interface HadesBridge {
  version: string;
  service?: {
    binaryUrl: string;
    jsonUrl: string;
  };
}

declare global {
  interface Window {
    hades?: HadesBridge;
    /* Test-only handle to the live MapLibre map, set once the map's `load` fires (MapView).
     * Lets the E2E suite assert that the offline basemap actually PAINTED tiles (via
     * `queryRenderedFeatures` on the basemap layers) — pixel readback off a WebGL canvas is
     * unreliable. Never read by app code. */
    __hadesMap?: import("maplibre-gl").Map;
  }
}

export {};
