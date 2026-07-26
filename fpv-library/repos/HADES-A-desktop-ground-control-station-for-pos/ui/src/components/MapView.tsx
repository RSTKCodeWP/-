import type { FeatureCollection, Point } from "geojson";
import maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";
import { useEffect, useRef, useState } from "react";
import "maplibre-gl/dist/maplibre-gl.css";

import { contactsToCirclesGeoJSON } from "../map/circle";
import { contactsToGeoJSON, toLngLat } from "../map/geo";
import {
  circleStrokeColorExpr,
  circleStrokeWidthExpr,
  pinColorExpr,
  pinRadiusExpr,
} from "../map/layers";
import { operationalStyle } from "../map/style";
import {
  coverageGeoJSON,
  droneGeoJSON,
  footprintGeoJSON,
  trackGeoJSON,
} from "../map/telemetryLayers";
import { PinTweener } from "../map/tween";
import { useContactStore } from "../store/contacts";
import { useLayerStore, type LayerKey } from "../store/layers";
import { useSelectionStore } from "../store/selection";
import { useTelemetryStore } from "../store/telemetry";
import { useThemeStore } from "../store/theme";
import type { ContactRecord } from "../types/wire";
import { LayerToggle } from "./LayerToggle";

/* The map — the heart of the tool, the application itself (impl-plan Task 5.5a/b; ATAK
 * "the map is the application"). Bespoke MapLibre GL viz (NO shadcn/Magic). Renders the
 * desaturated operational basemap + uncertainty rings (below) + reticle pins (above), all
 * tinted by the shared status encoding. Pins are bound bidirectionally to the selection
 * spine (click a pin → select; selection elsewhere → ring/keep-framed here) and GLIDE to
 * refined coordinates (never teleport, §4.5).
 *
 * Imperative GL, so it's verified by screenshot rather than jsdom; the data transforms it
 * uses (geo/circle/layers/tween) are exhaustively unit-tested. */

// register the pmtiles:// protocol once so a pre-downloaded offline basemap can drop in
let pmtilesRegistered = false;
function ensurePmtiles() {
  if (pmtilesRegistered) return;
  maplibregl.addProtocol("pmtiles", new Protocol().tile);
  pmtilesRegistered = true;
}

// The pre-downloaded offline basemap (Stage 1.1): a Protomaps v4 extract of the Biloxi /
// MS-Gulf-Coast AO (z0–14, ~4.6 MB), bundled under `ui/public/` and served fully offline via
// the `pmtiles://` protocol. Resolved RELATIVE to the page base (matching mission.json) so the
// URL is identical under the GitHub-Pages subpath, a root deploy, AND file://.
const DEFAULT_PMTILES_URL = `pmtiles://${import.meta.env.BASE_URL ?? "/"}biloxi-coastal.pmtiles`;

const PIN_SRC = "contacts";
const RING_SRC = "uncertainty";
const COVERAGE_SRC = "coverage";
const FOOTPRINT_SRC = "footprint";
const TRACK_SRC = "track";
const DRONE_SRC = "drone";

// which map layer ids each operator toggle controls
const LAYER_IDS: Record<LayerKey, string[]> = {
  coverage: ["coverage-fill", "coverage-line"],
  track: ["track-line"],
  footprint: ["footprint-fill", "footprint-line"],
  uncertainty: ["uncertainty-fill", "uncertainty-stroke"],
};

export function MapView({ pmtilesUrl = DEFAULT_PMTILES_URL }: { pmtilesUrl?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const tweenerRef = useRef(new PinTweener(400));
  const rafRef = useRef<number | null>(null);
  const fittedRef = useRef(false); // auto-fit the viewport to the data ONCE (then operator owns it)
  // The basemap paints in the active ECDIS palette (§12). A theme change rebuilds the map (the
  // construction effect is keyed on it) — a full restyle is the robust path since setStyle()
  // would wipe our custom data sources/layers anyway; the toggle is infrequent.
  const theme = useThemeStore((s) => s.theme);
  // WebGL can be unavailable (old GPU, locked-down/headless browser visiting the demo): MapLibre's
  // Map constructor THROWS. Catch it so a map failure degrades to a placeholder instead of throwing
  // out of the effect and unmounting the whole coordinator (banner/list/video would vanish too).
  const [mapError, setMapError] = useState(false);

  // one-time map construction
  useEffect(() => {
    if (!containerRef.current) return;
    ensurePmtiles();

    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container: containerRef.current,
        style: operationalStyle({ pmtilesUrl, theme }),
        center: [-88.52, 30.215],
        zoom: 14,
        attributionControl: false,
      });
    } catch {
      setMapError(true); // WebGL unavailable — render the fallback, keep the rest of the UI alive
      return;
    }
    mapRef.current = map;

    map.on("load", () => {
      // Test-only handle so the E2E suite can assert the offline basemap painted tiles via
      // queryRenderedFeatures (WebGL pixel readback is unreliable). No app code reads this.
      window.__hadesMap = map;

      // Data-layer palette per ECDIS mode (§12). On a LIGHT ground the dark-tuned cool washes
      // wash out, so day uses higher coverage alpha + a crisp coverage OUTLINE, darker cool
      // track/footprint that don't vanish on paper, and a dark casing on the drone dot.
      // Coverage is searched-area CONTEXT, not a contact — it must RECEDE so the warm survivor
      // pins stay the only figure (§5.1 figure-ground). On light it leads with a thin outline +
      // a very low fill; a loud green slab out-shouting the pins is the exact inversion to avoid.
      const D =
        theme === "day"
          ? {
              coverage: "#3E8E6E", coverageOpacity: 0.08, coverageLine: "#2E7A5C", coverageLineOpacity: 0.45,
              cool: "#2B5E8E", droneFill: "#1C64B4", droneStroke: "#201E1A",
            }
          : {
              coverage: "#2FB67C", coverageOpacity: 0.08, coverageLine: "#2FB67C", coverageLineOpacity: 0.5,
              cool: "#6FA8DE", droneFill: "#3B7BC8", droneStroke: "#E6EDF3",
            };

      // telemetry sources/layers FIRST so they sit below the contact rings + pins (z-order)
      map.addSource(COVERAGE_SRC, { type: "geojson", data: emptyFC() });
      map.addSource(FOOTPRINT_SRC, { type: "geojson", data: emptyFC() });
      map.addSource(TRACK_SRC, { type: "geojson", data: emptyFC() });
      map.addSource(DRONE_SRC, { type: "geojson", data: emptyFC() });

      // searched-area coverage — the most important non-pin layer. Fill + a crisp dissolved
      // OUTLINE; on light the edge carries the meaning (the fill alone is too faint, §12).
      map.addLayer({
        id: "coverage-fill",
        type: "fill",
        source: COVERAGE_SRC,
        paint: { "fill-color": D.coverage, "fill-opacity": D.coverageOpacity },
      });
      map.addLayer({
        id: "coverage-line",
        type: "line",
        source: COVERAGE_SRC,
        paint: { "line-color": D.coverageLine, "line-width": 1, "line-opacity": D.coverageLineOpacity },
      });
      // current camera footprint — a brighter outlined quad
      map.addLayer({
        id: "footprint-fill",
        type: "fill",
        source: FOOTPRINT_SRC,
        paint: { "fill-color": D.cool, "fill-opacity": 0.12 },
      });
      map.addLayer({
        id: "footprint-line",
        type: "line",
        source: FOOTPRINT_SRC,
        paint: { "line-color": D.cool, "line-width": 1, "line-dasharray": [2, 1] },
      });
      // drone flight track — a thin cool line
      map.addLayer({
        id: "track-line",
        type: "line",
        source: TRACK_SRC,
        paint: { "line-color": D.cool, "line-width": 1.5 },
      });
      // drone position
      map.addLayer({
        id: "drone-dot",
        type: "circle",
        source: DRONE_SRC,
        paint: {
          "circle-radius": 5,
          "circle-color": D.droneFill,
          "circle-stroke-color": D.droneStroke,
          "circle-stroke-width": 1.5,
        },
      });

      map.addSource(RING_SRC, { type: "geojson", data: emptyFC() });
      // pin source clusters at low zoom so the map stays legible under dozens of contacts (§5.1)
      map.addSource(PIN_SRC, {
        type: "geojson",
        data: emptyFC(),
        cluster: true,
        clusterRadius: 44,
        clusterMaxZoom: 13,
      });

      // uncertainty rings: low fill + strong stroke (the EDGE carries the meaning, §5.1). On
      // light the fill is even fainter, so the stroke does the work (§12).
      map.addLayer({
        id: "uncertainty-fill",
        type: "fill",
        source: RING_SRC,
        paint: { "fill-color": circleStrokeColorExpr(theme), "fill-opacity": theme === "day" ? 0.08 : 0.12 },
      });
      map.addLayer({
        id: "uncertainty-stroke",
        type: "line",
        source: RING_SRC,
        paint: { "line-color": circleStrokeColorExpr(theme), "line-width": circleStrokeWidthExpr() },
      });

      // clusters (low zoom): a count bubble so the map stays legible under many contacts.
      // Bubble + count flip for the light ground (dark text on a light bubble).
      const clusterFill = theme === "day" ? "#FAF9F6" : "#28303E";
      const clusterStroke = theme === "day" ? "#2B5E8E" : "#5E9BD6";
      const clusterText = theme === "day" ? "#201E1A" : "#E6EDF3";
      map.addLayer({
        id: "pin-cluster",
        type: "circle",
        source: PIN_SRC,
        filter: ["has", "point_count"],
        paint: {
          "circle-radius": ["step", ["get", "point_count"], 12, 5, 16, 15, 22],
          "circle-color": clusterFill,
          "circle-stroke-color": clusterStroke,
          "circle-stroke-width": 1.5,
        },
      });
      map.addLayer({
        id: "pin-cluster-count",
        type: "symbol",
        source: PIN_SRC,
        filter: ["has", "point_count"],
        layout: { "text-field": ["get", "point_count_abbreviated"], "text-size": 11 },
        paint: { "text-color": clusterText },
      });

      // pins (individual, not clustered): reticle = outer ring + center dot, top (§5.1 z-order).
      map.addLayer({
        id: "pin-ring",
        type: "circle",
        source: PIN_SRC,
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-radius": pinRadiusExpr(),
          "circle-color": "rgba(0,0,0,0)",
          "circle-stroke-color": pinColorExpr(theme),
          "circle-stroke-width": 2,
        },
      });
      map.addLayer({
        id: "pin-dot",
        type: "circle",
        source: PIN_SRC,
        filter: ["!", ["has", "point_count"]],
        paint: { "circle-radius": 2, "circle-color": pinColorExpr(theme) },
      });

      // click a cluster → zoom in to expand it
      map.on("click", "pin-cluster", (e) => {
        const f = map.queryRenderedFeatures(e.point, { layers: ["pin-cluster"] })[0];
        const clusterId = f?.properties?.cluster_id;
        const src = map.getSource(PIN_SRC) as maplibregl.GeoJSONSource;
        if (clusterId == null || !src.getClusterExpansionZoom) return;
        void src.getClusterExpansionZoom(clusterId).then((zoom) => {
          map.easeTo({ center: (f.geometry as Point).coordinates as [number, number], zoom });
        });
      });

      // click a pin → commit selection (pin → selection spine)
      map.on("click", "pin-ring", (e) => {
        const f = e.features?.[0];
        if (f) useSelectionStore.getState().select(f.properties!.track_id as number);
      });
      map.on("mouseenter", "pin-ring", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "pin-ring", () => (map.getCanvas().style.cursor = ""));

      // prime with whatever is already in the store
      syncData();
      syncTelemetry();
      syncVisibility();
    });

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      if (window.__hadesMap === map) delete window.__hadesMap;
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pmtilesUrl, theme]);

  // re-sync whenever contacts, selection, or telemetry change
  useEffect(() => {
    const unsubC = useContactStore.subscribe(() => syncData());
    const unsubS = useSelectionStore.subscribe(() => syncData());
    const unsubT = useTelemetryStore.subscribe(() => syncTelemetry());
    const unsubL = useLayerStore.subscribe(() => syncVisibility());
    return () => {
      unsubC();
      unsubS();
      unsubT();
      unsubL();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Apply operator layer toggles to the map's layout visibility.
  function syncVisibility() {
    const map = mapRef.current;
    if (!map || !map.getLayer("coverage-fill")) return;
    const visible = useLayerStore.getState().visible;
    for (const [key, ids] of Object.entries(LAYER_IDS)) {
      const v = visible[key as LayerKey] ? "visible" : "none";
      for (const id of ids) {
        if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", v);
      }
    }
  }

  // Push drone track / footprint / coverage to the map.
  function syncTelemetry() {
    const map = mapRef.current;
    if (!map || !map.getSource(TRACK_SRC)) return;
    const t = useTelemetryStore.getState();
    (map.getSource(COVERAGE_SRC) as maplibregl.GeoJSONSource)?.setData(coverageGeoJSON(t.coverage));
    (map.getSource(FOOTPRINT_SRC) as maplibregl.GeoJSONSource)?.setData(footprintGeoJSON(t.footprint));
    (map.getSource(TRACK_SRC) as maplibregl.GeoJSONSource)?.setData(trackGeoJSON(t.track));
    (map.getSource(DRONE_SRC) as maplibregl.GeoJSONSource)?.setData(droneGeoJSON(t.pose));
  }

  // Push current store state to the map, feeding the tweener so pins glide on refine.
  function syncData() {
    const map = mapRef.current;
    if (!map || !map.getSource(PIN_SRC)) return;
    const contacts = [...useContactStore.getState().contacts.values()];
    const selectedId = useSelectionStore.getState().selectedId;
    const now = performance.now();

    // feed targets to the tweener (eased motion), then render eased positions
    for (const c of contacts) {
      if (c.lat !== null && c.lon !== null) {
        tweenerRef.current.setTarget(c.track_id, toLngLat(c.lat, c.lon), now);
      }
    }
    render(contacts, selectedId, now);
    startTickIfNeeded();
    maybeFitToData();
  }

  // Frame the viewport over all located data (contacts + drone track) the FIRST time any
  // appears, so the scene composes instead of scattering pins in a dead field. Once. After
  // that the operator owns the camera (pan/zoom); we never yank it from under them.
  function maybeFitToData() {
    const map = mapRef.current;
    if (!map || fittedRef.current) return;
    const pts: [number, number][] = [];
    for (const c of useContactStore.getState().contacts.values()) {
      if (c.lat !== null && c.lon !== null) pts.push(toLngLat(c.lat, c.lon));
    }
    pts.push(...useTelemetryStore.getState().track);
    if (pts.length === 0) return;
    fittedRef.current = true;
    const lons = pts.map((p) => p[0]);
    const lats = pts.map((p) => p[1]);
    const bounds: [[number, number], [number, number]] = [
      [Math.min(...lons), Math.min(...lats)],
      [Math.max(...lons), Math.max(...lats)],
    ];
    map.fitBounds(bounds, { padding: 120, maxZoom: 14, duration: 0 });
  }

  // render one frame of eased positions to the GeoJSON sources
  function render(contacts: ContactRecord[], selectedId: number | null, now: number) {
    const map = mapRef.current;
    if (!map) return;
    const eased = contacts
      .filter((c) => c.lat !== null && c.lon !== null)
      .map((c) => {
        const pos = tweenerRef.current.positionAt(c.track_id, now) ?? toLngLat(c.lat!, c.lon!);
        return { ...c, lat: pos[1], lon: pos[0] };
      });

    (map.getSource(PIN_SRC) as maplibregl.GeoJSONSource)?.setData(
      contactsToGeoJSON(eased, selectedId) as unknown as FeatureCollection,
    );
    (map.getSource(RING_SRC) as maplibregl.GeoJSONSource)?.setData(
      contactsToCirclesGeoJSON(eased, selectedId) as unknown as FeatureCollection,
    );
  }

  // keep ticking while any pin is gliding (then stop — no idle animation loop)
  function startTickIfNeeded() {
    if (rafRef.current || !tweenerRef.current.active) return;
    const tick = () => {
      rafRef.current = null;
      const contacts = [...useContactStore.getState().contacts.values()];
      render(contacts, useSelectionStore.getState().selectedId, performance.now());
      if (tweenerRef.current.active) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };
    rafRef.current = requestAnimationFrame(tick);
  }

  if (mapError) {
    // Honest degrade: the map needs WebGL, which this browser/GPU doesn't provide. The rest of
    // the coordinator (list, video, status, mission log) stays fully usable.
    return (
      <div
        data-testid="map-unavailable"
        className="absolute inset-0 flex h-full w-full items-center justify-center bg-bg-base p-6 text-center font-mono text-xs text-text-lo"
      >
        <p className="max-w-sm leading-relaxed">
          Map unavailable: this browser could not initialize WebGL. The survivor list, video, and
          mission log remain available; coordinates are shown in the contact panel.
        </p>
      </div>
    );
  }

  return (
    <div className="absolute inset-0 h-full w-full">
      <div ref={containerRef} data-testid="map-view" className="absolute inset-0 h-full w-full" />
      <LayerToggle />
    </div>
  );
}

function emptyFC(): FeatureCollection {
  return { type: "FeatureCollection", features: [] };
}
