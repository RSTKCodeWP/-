import type { StyleSpecification } from "maplibre-gl";

/* The operational basemap style (DESIGN-SYSTEM §5.1 / §12) — a DESATURATED chart so colored
 * detection data is the only figure on the map. Ships in BOTH ECDIS modes:
 *  - NIGHT (CARTO Dark Matter lineage): dark-gray land, darker water that recedes.
 *  - DAY (UI overhaul §12): light land paper, slightly-cooler water; pins/rings/coverage stay
 *    the only saturated marks. Land is the same warm-neutral family as the chrome so the map
 *    reads as part of the instrument, not a foreign tile layer.
 *
 * Offline by construction: with no PMTiles file, the style is just a flat operational
 * background (zero network sources, fully deterministic for tests + the canned demo). With
 * a pre-downloaded `.pmtiles` file (cached before a mission per the on-device constraint),
 * it adds the vector basemap via the `pmtiles://` protocol — still no remote tile server. */

export type BasemapTheme = "day" | "night";

// Per-theme operational colors. Day = light chart; Night = CARTO Dark Matter-derived.
const THEME_COLORS: Record<BasemapTheme, { land: string; water: string; road: string; label: string }> = {
  night: { land: "#101418", water: "#2C353C", road: "#454C55", label: "#9AA3AD" },
  // Day: a light land that's distinctly a CHART, not the chrome — warm paper land, a clearly
  // COOLER grey-blue water that reads as water (not just "lighter land"), and a road casing dark
  // enough to register as line-work. The land/water contrast is the cartographic signal that
  // makes the AO read as a place; saturated pins/rings still stay the figure on the light ground.
  day: { land: "#DAD3C4", water: "#A9B8C6", road: "#9C9484", label: "#4E4A43" },
};

export interface OperationalStyleOptions {
  /** A pmtiles:// URL to a pre-downloaded offline basemap; omit for the flat canvas. */
  pmtilesUrl?: string;
  /** Which ECDIS palette to paint the basemap in (defaults to day, the default chrome theme). */
  theme?: BasemapTheme;
}

export function operationalStyle(opts: OperationalStyleOptions = {}): StyleSpecification {
  const { land: LAND, water: WATER, road: ROAD, label: LABEL } = THEME_COLORS[opts.theme ?? "day"];
  const sources: StyleSpecification["sources"] = {};
  const layers: StyleSpecification["layers"] = [
    {
      id: "background",
      type: "background",
      paint: { "background-color": LAND },
    },
  ];

  if (opts.pmtilesUrl) {
    sources.basemap = {
      type: "vector",
      url: opts.pmtilesUrl,
    };
    // Land/water/road geometry off the pmtiles basemap. Source-layer ids are the Protomaps
    // BASEMAPS v4 schema (verified against the extract's `vector_layers` metadata, NOT the
    // OpenMapTiles names): land polygon = `earth`, water = `water`, roads = `roads` (NOT
    // `transportation`). No symbol (label) layer in v1: text needs a `glyphs` source, and the
    // offline constraint forbids a remote glyphs URL — bundled offline glyphs are a v1.x
    // refinement (LABEL kept for it).
    void LABEL;
    layers.push(
      // earth: the land polygon. Painted just above the flat background so coastline/landmass
      // reads as real terrain (the background still shows through anywhere earth is absent).
      {
        id: "earth",
        type: "fill",
        source: "basemap",
        "source-layer": "earth",
        paint: { "fill-color": LAND },
      },
      {
        id: "water",
        type: "fill",
        source: "basemap",
        "source-layer": "water",
        paint: { "fill-color": WATER },
      },
      {
        id: "roads",
        type: "line",
        source: "basemap",
        "source-layer": "roads",
        paint: { "line-color": ROAD, "line-width": 0.6 },
      },
    );
  }

  // NOTE: do NOT emit a `glyphs` key. MapLibre's Style._load requires glyphs to be ABSENT
  // or a string; an explicit `glyphs: undefined` fails "string expected" and aborts the
  // load (→ blank canvas). With no symbol layers there is nothing that needs glyphs.
  return {
    version: 8,
    sources,
    layers,
  } as StyleSpecification;
}

// Exposed for tests + any non-map surface that needs the operational basemap colors.
export const OPERATIONAL_COLORS = THEME_COLORS;
