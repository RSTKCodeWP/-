/**
 * attachTrafficLayer — ADS-B + glider contacts on the Area Editor's MapLibre map.
 *
 * The editor is a separate BrowserWindow with its own stores, so this is fully
 * self-contained (it does not use the renderer traffic-store): it subscribes to
 * the TRAFFIC_UPDATE push directly, mirrors the editor's 'traffic'/'gliders'
 * toggles to the backend, reports viewport, and renders a rotated icon-symbol
 * layer. The editor style ships no glyphs, so contacts carry no on-map text label;
 * a click popup shows the full readout instead.
 */

import type maplibregl from 'maplibre-gl';
import { Popup } from 'maplibre-gl';
import { useAreaEditorLayersStore } from './area-editor-layers-store';
import type { TrafficContact, TrafficSource } from '../../shared/traffic-types';
import {
  glyphSvg,
  altitudeRelevance,
  relevanceStyle,
  altitudeColorState,
  isAltitudeRelevant,
  ALT_STATE_COLOR,
  type AltitudeBand,
  type AltState,
} from '../components/map/traffic/contact-style';
import { buildContactPopup } from '../components/map/traffic/contact-popup';
import { useTrafficStore } from '../stores/traffic-store';

const SOURCE_ID = 'traffic-contacts';
const LAYER_ID = 'traffic-contacts-symbols';
const CATEGORIES = ['powered', 'jet', 'helicopter', 'glider', 'balloon', 'ground', 'unknown'] as const;
const STATES = Object.keys(ALT_STATE_COLOR) as AltState[];

function imageKey(category: string, state: AltState): string {
  return `traffic-${category}-${state}`;
}

/** Rasterise each category×altitude-state glyph into a map image once. */
function registerIcons(map: maplibregl.Map): void {
  const size = 40; // 2x for retina crispness
  for (const category of CATEGORIES) {
    for (const state of STATES) {
      const key = imageKey(category, state);
      if (map.hasImage(key)) continue;
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 20 20">${glyphSvg(category, ALT_STATE_COLOR[state])}</svg>`;
      const img = new Image(size, size);
      img.onload = () => {
        if (!map.hasImage(key)) map.addImage(key, img, { pixelRatio: 2 });
      };
      img.src = `data:image/svg+xml;base64,${btoa(svg)}`;
    }
  }
}

function toFeatures(contacts: TrafficContact[], band: AltitudeBand, iconScale: number): GeoJSON.Feature[] {
  return contacts.map((c) => {
    const { scale, opacity } = relevanceStyle(altitudeRelevance(c.altMeters, band));
    return {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [c.lon, c.lat] },
      properties: {
        id: c.id,
        icon: imageKey(c.category, altitudeColorState(c, band)),
        rot: c.trackDeg ?? 0,
        size: scale * 0.6 * iconScale,
        opacity,
        contact: JSON.stringify(c),
      },
    };
  });
}

export function attachTrafficLayer(map: maplibregl.Map): () => void {
  registerIcons(map);

  if (!map.getSource(SOURCE_ID)) {
    map.addSource(SOURCE_ID, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  }
  if (!map.getLayer(LAYER_ID)) {
    map.addLayer({
      id: LAYER_ID,
      type: 'symbol',
      source: SOURCE_ID,
      layout: {
        'icon-image': ['get', 'icon'],
        'icon-rotate': ['get', 'rot'],
        'icon-rotation-alignment': 'map',
        'icon-allow-overlap': true,
        'icon-size': ['get', 'size'],
      },
      paint: {
        'icon-opacity': ['get', 'opacity'],
      },
    });
  }

  let contacts: TrafficContact[] = [];
  // Seed the band from the saved default, then track the on-map filter control live.
  void window.electronAPI.getTrafficConfig().then((cfg) => {
    if (cfg?.altitudeFilter) useTrafficStore.getState().setAltitudeBand(cfg.altitudeFilter);
    if (cfg?.iconScale) useTrafficStore.getState().setIconScale(cfg.iconScale);
  });

  const enabledSources = (): Set<TrafficSource> => {
    const ov = useAreaEditorLayersStore.getState().overlays;
    const s = new Set<TrafficSource>();
    if (ov.traffic) s.add('adsb');
    if (ov.gliders) s.add('ogn');
    return s;
  };

  const render = (): void => {
    const sources = enabledSources();
    const { altitudeBand: band, iconScale } = useTrafficStore.getState();
    const visible = contacts.filter((c) => sources.has(c.source) && isAltitudeRelevant(c, band));
    const src = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    src?.setData({ type: 'FeatureCollection', features: toFeatures(visible, band, iconScale) });
  };

  const unsubPush = window.electronAPI.onTrafficUpdate((batch) => {
    contacts = batch.contacts;
    render();
  });

  // Mirror editor toggles -> backend enable, and re-render on toggle.
  let prev = new Set<TrafficSource>();
  const syncEnable = (): void => {
    const next = enabledSources();
    for (const s of next) if (!prev.has(s)) window.electronAPI.setTrafficEnabled(s, true);
    for (const s of prev) if (!next.has(s)) window.electronAPI.setTrafficEnabled(s, false);
    prev = next;
    render();
  };
  const unsubToggle = useAreaEditorLayersStore.subscribe((s) => s.overlays, syncEnable);
  syncEnable();

  // Re-render when the on-map altitude filter changes the band.
  const unsubBand = useTrafficStore.subscribe(render);

  const reportViewport = (): void => {
    const c = map.getCenter();
    const b = map.getBounds();
    const ne = b.getNorthEast();
    const radiusKm = Math.min(500, haversineKm(c.lat, c.lng, ne.lat, ne.lng));
    window.electronAPI.setTrafficViewport({ lat: c.lat, lon: c.lng, radiusKm });
  };
  reportViewport();
  map.on('moveend', reportViewport);

  const popup = new Popup({ closeButton: true, closeOnClick: true, className: 'traffic-popup' });
  const onClick = (e: maplibregl.MapLayerMouseEvent): void => {
    const f = e.features?.[0];
    if (!f) return;
    const c = JSON.parse(f.properties!.contact as string) as TrafficContact;
    const band = useTrafficStore.getState().altitudeBand;
    popup.setLngLat([c.lon, c.lat]).setHTML(buildContactPopup(c, null, Date.now(), band)).addTo(map);
  };
  map.on('click', LAYER_ID, onClick);

  return () => {
    unsubPush();
    unsubToggle();
    unsubBand();
    map.off('moveend', reportViewport);
    map.off('click', LAYER_ID, onClick);
    popup.remove();
    // Turn off any sources this window enabled so providers can stop.
    for (const s of prev) window.electronAPI.setTrafficEnabled(s, false);
    if (map.getLayer(LAYER_ID)) map.removeLayer(LAYER_ID);
    if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID);
  };
}

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}
