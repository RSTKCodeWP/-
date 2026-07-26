"use client";

/**
 * @module map/MinimapBasemapSelector
 * @description A compact map-type selector for the cockpit minimap — the basemap
 * segments only (DARK / OSM / SAT / TOPO), with no NFZ toggle and no
 * click-to-expand. It writes the shared `mapTileSource` setting, so both the
 * minimap and the full map follow the choice. The basemap catalog is kept local
 * (mirroring TileLayerSwitcher) so importing this client component never pulls
 * Leaflet into an SSR pass.
 * @license GPL-3.0-only
 */

import { useSettingsStore, type MapTileSource } from "@/stores/settings-store";
import { BasemapSwitcher } from "./BasemapSwitcher";

const LABELS: Record<MapTileSource, string> = {
  dark: "DARK",
  osm: "OSM",
  satellite: "SAT",
  terrain: "TOPO",
};
const ORDER: MapTileSource[] = ["dark", "osm", "satellite", "terrain"];

export function MinimapBasemapSelector({ className }: { className?: string }) {
  const source = useSettingsStore((s) => s.mapTileSource);
  const setSource = useSettingsStore((s) => s.setMapTileSource);
  return (
    <BasemapSwitcher
      className={className}
      value={source}
      onChange={(v) => setSource(v as MapTileSource)}
      options={ORDER.map((s) => ({ value: s, label: LABELS[s] }))}
    />
  );
}
