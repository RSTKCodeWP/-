<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { app, addWaypoint, deleteWaypoint, saveWaypoints, addToast, showConfirm } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { toGcj, toWgs } from '../../lib/gcj02';
  import { t } from '../../lib/i18n.svelte';
  import { API_BASE } from '../../lib/backend';
  import { Ruler, Square, ShieldAlert, Grid3x3, X as XIcon } from '@lucide/svelte';
  import { segDist } from '../../lib/missionIO';
  import { polygonArea } from '../../lib/survey';
  import { fmtDist } from '../../lib/units';
  import maplibregl from 'maplibre-gl';
  import 'maplibre-gl/dist/maplibre-gl.css';

  let mapEl: HTMLDivElement;
  let map: maplibregl.Map | null = $state(null);
  let droneMarker: maplibregl.Marker | null = null;
  let homeMarker: maplibregl.Marker | null = null;
  let trailCoords: [number, number][] = [];
  let prevLat = 0;
  let prevLon = 0;

  interface TileSourceDef {
    name: string;
    sat: string;
    vec: string;
    label: string | null;
    gcj02: boolean;
    region: string;
  }
  const SOURCES: Record<string, TileSourceDef> = {
    amap: { name: 'Amap', sat: '6', vec: '7', label: '8', gcj02: true, region: 'china' },
    google_sat: {
      name: 'Google Satellite',
      sat: 'google_sat',
      vec: 'google_street',
      label: null,
      gcj02: false,
      region: 'global',
    },
    google_hybrid: {
      name: 'Google Hybrid',
      sat: 'google_hybrid',
      vec: 'google_street',
      label: null,
      gcj02: false,
      region: 'global',
    },
    osm: { name: 'OpenStreetMap', sat: 'osm_sat', vec: 'osm', label: null, gcj02: false, region: 'global' },
    esri: { name: 'Esri Topo', sat: 'osm_sat', vec: 'esri_topo', label: null, gcj02: false, region: 'global' },
  };

  function curSource(): TileSourceDef {
    return SOURCES[app.tileSource] || SOURCES['osm'];
  }
  let useGcj = $derived(curSource().gcj02);
  function toMap(lat: number, lon: number): [number, number] {
    return useGcj ? toGcj(lat, lon) : [lat, lon];
  }
  function fromMap(mlat: number, mlon: number): [number, number] {
    return useGcj ? toWgs(mlat, mlon) : [mlat, mlon];
  }

  // Per-waypoint maplibre Markers — replaces the static GeoJSON circle layer
  // so each WP is independently draggable. Mirrors WaypointLayer.svelte's 2D
  // pattern (Leaflet markers + dragend → saveWaypoints).
  let wpMarkers: maplibregl.Marker[] = [];
  let wpPopup: maplibregl.Popup | null = null;

  // Fence vertex markers (rendered as small dots; the fill/line is a GeoJSON
  // layer added once in onMount). Rebuilt every time app.fencePolygon changes.
  let fenceVertMarkers: maplibregl.Marker[] = [];
  // Survey polygon vertex markers — same pattern, purple instead of red.
  // Mirrors src/components/layers/SurveyLayer.svelte.
  let surveyVertMarkers: maplibregl.Marker[] = [];

  // Replay layer state: a single orange-triangle marker + trail polyline,
  // driven by app.replayPos. Mirrors src/components/layers/ReplayLayer.svelte.
  let replayMarker: maplibregl.Marker | null = null;
  let replayTrail: [number, number][] = [];

  // ADSB traffic markers — one per icao. Same Map<icao, Marker> pattern as
  // DroneLayer.svelte:136-162 with HTML titles for hover info (maplibre
  // markers don't have a built-in bindTooltip equivalent).
  const adsbMarkers = new Map<number, maplibregl.Marker>();

  // Measure mode: distance (polyline) or area (polygon). All state local to
  // this view — clear on ESC or by clicking the same mode button twice.
  let measuring = $state(false);
  let measureMode = $state<'distance' | 'area'>('distance');
  let measurePts: { lat: number; lon: number }[] = [];
  let measureVertMarkers: maplibregl.Marker[] = [];
  let measureLabel: maplibregl.Marker | null = null;

  // Distance + area math: reuse the shared helpers (lib/missionIO.segDist
  function fmtArea(m2: number): string {
    if (m2 < 10000) return `${m2.toFixed(0)} m²`;
    if (m2 < 1e6) return `${(m2 / 10000).toFixed(2)} ha`;
    return `${(m2 / 1e6).toFixed(3)} km²`;
  }

  function labelMarker(lonLat: [number, number], text: string, color: string): maplibregl.Marker {
    const el = document.createElement('div');
    el.style.cssText = `background:rgba(30,30,30,0.9);color:${color};padding:2px 6px;border-radius:3px;font-size:11px;font-weight:bold;white-space:nowrap;pointer-events:none`;
    el.textContent = text;
    return new maplibregl.Marker({ element: el, anchor: 'top' }).setLngLat(lonLat).addTo(map!);
  }

  function vertexMarker(lonLat: [number, number], color: string): maplibregl.Marker {
    const el = document.createElement('div');
    el.style.cssText = `width:10px;height:10px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 0 3px rgba(0,0,0,0.6)`;
    return new maplibregl.Marker({ element: el }).setLngLat(lonLat).addTo(map!);
  }

  function createSvgElement(svgMarkup: string): SVGSVGElement {
    const parser = new DOMParser();
    const doc = parser.parseFromString(svgMarkup, 'image/svg+xml');
    return doc.documentElement as unknown as SVGSVGElement;
  }

  onMount(() => {
    const src = curSource();
    const tileUrl = `${API_BASE}/api/tile/${src.sat}/{z}/{x}/{y}`;
    // Track the initial tile source so the prevTileSource $effect doesn't
    // fire a redundant swap on first render. Mirrors MapView.svelte:97.
    prevTileSource = app.tileSource;

    map = new maplibregl.Map({
      container: mapEl,
      style: {
        version: 8,
        sources: {
          'raster-tiles': {
            type: 'raster',
            tiles: [tileUrl],
            tileSize: 256,
            maxzoom: 18,
          },
          'terrain-dem': {
            type: 'raster-dem',
            tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
            tileSize: 256,
            maxzoom: 15,
            encoding: 'terrarium',
          },
        },
        layers: [{ id: 'raster', type: 'raster', source: 'raster-tiles' }],
        terrain: { source: 'terrain-dem', exaggeration: 1.3 },
        sky: {
          'sky-color': '#199EF3',
          'sky-horizon-blend': 0.5,
          'horizon-color': '#ffffff',
          'horizon-fog-blend': 0.5,
          'fog-color': '#0000ff',
          'fog-ground-blend': 0.5,
        },
      },
      center: [108.942, 34.258],
      zoom: 14,
      pitch: 50,
      bearing: 0,
      maxPitch: 85,
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 150 }), 'bottom-right');

    map.on('load', () => {
      map!.addSource('waypoints', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
      // Path line only — the points themselves are rendered as draggable
      // Markers below so we get native drag-to-edit without a custom layer.
      map!.addLayer({
        id: 'waypoint-line',
        type: 'line',
        source: 'waypoints',
        paint: { 'line-color': '#1565c0', 'line-width': 3, 'line-dasharray': [2, 1] },
      });

      map!.addSource('trail', {
        type: 'geojson',
        data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [] }, properties: {} },
      });
      map!.addLayer({
        id: 'trail-line',
        type: 'line',
        source: 'trail',
        paint: { 'line-color': '#4fc3f7', 'line-width': 2, 'line-opacity': 0.7 },
      });

      // Fence: red fill + dashed border (matches 2D FenceLayer.svelte color
      // convention). Polygon when ≥3 verts, polyline when 2.
      map!.addSource('fence', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
      map!.addLayer({
        id: 'fence-fill',
        type: 'fill',
        source: 'fence',
        filter: ['==', '$type', 'Polygon'],
        paint: { 'fill-color': '#f44336', 'fill-opacity': 0.1 },
      });
      map!.addLayer({
        id: 'fence-line',
        type: 'line',
        source: 'fence',
        paint: { 'line-color': '#f44336', 'line-width': 2, 'line-dasharray': [3, 2] },
      });

      // Measure overlay: line for distance + polygon for area.
      map!.addSource('measure', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
      map!.addLayer({
        id: 'measure-fill',
        type: 'fill',
        source: 'measure',
        filter: ['==', '$type', 'Polygon'],
        paint: { 'fill-color': '#ff5252', 'fill-opacity': 0.1 },
      });
      map!.addLayer({
        id: 'measure-line',
        type: 'line',
        source: 'measure',
        paint: { 'line-color': '#ff5252', 'line-width': 2, 'line-dasharray': [2, 2] },
      });

      // Replay trail: orange polyline driven by app.replayPos updates.
      map!.addSource('replay-trail', {
        type: 'geojson',
        data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [] }, properties: {} },
      });
      map!.addLayer({
        id: 'replay-trail-line',
        type: 'line',
        source: 'replay-trail',
        paint: { 'line-color': '#ffa726', 'line-width': 2, 'line-opacity': 0.6 },
      });

      // Survey polygon — purple, mirrors SurveyLayer.svelte. Used by
      // SurveyPanel to feed into the grid generator.
      map!.addSource('survey', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
      map!.addLayer({
        id: 'survey-fill',
        type: 'fill',
        source: 'survey',
        filter: ['==', '$type', 'Polygon'],
        paint: { 'fill-color': '#ab47bc', 'fill-opacity': 0.12 },
      });
      map!.addLayer({
        id: 'survey-line',
        type: 'line',
        source: 'survey',
        paint: { 'line-color': '#ab47bc', 'line-width': 2, 'line-dasharray': [3, 2] },
      });
    });

    // Map click: same priority order as MapView.svelte:118-140 —
    // measure → survey draw → fence draw → guided goto → addWaypoint.
    // Note the GCJ inverse-transform so China-tile providers don't store
    // shifted coordinates in app.waypoints / app.fencePolygon / surveyPolygon.
    map.on('click', (e) => {
      const { lat: mlat, lng: mlon } = e.lngLat;
      const [wlat, wlon] = fromMap(mlat, mlon);
      if (measuring) {
        addMeasurePoint(wlat, wlon);
        return;
      }
      if (app.drawingPolygon) {
        app.surveyPolygon = [...app.surveyPolygon, { lat: wlat, lon: wlon }];
        return;
      }
      if (app.drawingFence) {
        app.fencePolygon = [...app.fencePolygon, { lat: wlat, lon: wlon }];
        return;
      }
      if (app.guidedMode && app.drone.connected && app.drone.armed) {
        dispatch('guided_goto', undefined, { lat: wlat, lon: wlon, alt: app.defaultAlt });
        addToast(`${t('map.guided')} → ${wlat.toFixed(5)}, ${wlon.toFixed(5)}`, 'info');
        return;
      }
      addWaypoint({
        lat: wlat,
        lon: wlon,
        alt: app.defaultAlt,
        drop: false,
        delay: 0,
        speed: 0,
        type: 'wp',
        loiter_param: 0,
      });
    });

    // Right-click: guided-goto with confirm dialog. Mirrors MapView.svelte:
    // onRightClick. maplibre emits 'contextmenu' on right-click; the original
    // browser context menu is suppressed by the canvas element's own handler.
    map.on('contextmenu', (e) => {
      if (!app.drone.connected || !app.drone.armed) return;
      const [wlat, wlon] = fromMap(e.lngLat.lat, e.lngLat.lng);
      const msg = `${t('confirm.guidedGoto')}\n${wlat.toFixed(5)}, ${wlon.toFixed(5)}\n${t('ctrl.altitude')}: ${app.defaultAlt}m`;
      showConfirm(msg).then((ok) => {
        if (!ok) return;
        dispatch('guided_goto', undefined, { lat: wlat, lon: wlon, alt: app.defaultAlt });
        addToast(`${t('map.guided')} → ${wlat.toFixed(5)}, ${wlon.toFixed(5)}`, 'info');
      });
    });

    window.addEventListener('keydown', onKeyDown);
  });

  // ESC behaviors mirror MapView.svelte:onKeyDown (lines 156-167):
  // clear in-flight measure, draw-modes, guided mode. Does NOT clear the
  // already-committed polygons (fencePolygon / surveyPolygon) on ESC — same
  // as 2D, those go away only via the explicit Clear buttons / panel UI.
  function onKeyDown(e: KeyboardEvent) {
    if (e.key !== 'Escape') return;
    if (measuring) clearMeasure();
    if (app.guidedMode) app.guidedMode = false;
    if (app.drawingFence) app.drawingFence = false;
    if (app.drawingPolygon) app.drawingPolygon = false;
  }

  function toggleMeasure(mode: 'distance' | 'area') {
    if (measuring && measureMode === mode) {
      clearMeasure();
      return;
    }
    clearMeasure();
    measureMode = mode;
    measuring = true;
  }

  function clearMeasure() {
    measuring = false;
    measurePts = [];
    measureVertMarkers.forEach((m) => m.remove());
    measureVertMarkers = [];
    if (measureLabel) {
      measureLabel.remove();
      measureLabel = null;
    }
    const src = map?.getSource('measure') as maplibregl.GeoJSONSource | undefined;
    if (src) src.setData({ type: 'FeatureCollection', features: [] });
  }

  function addMeasurePoint(wlat: number, wlon: number) {
    measurePts.push({ lat: wlat, lon: wlon });
    const lonLats: [number, number][] = measurePts.map((p) => {
      const [mlat, mlon] = toMap(p.lat, p.lon);
      return [mlon, mlat];
    });
    measureVertMarkers.push(vertexMarker(lonLats[lonLats.length - 1], '#ff5252'));

    const src = map?.getSource('measure') as maplibregl.GeoJSONSource | undefined;
    if (!src) return;

    if (measureLabel) {
      measureLabel.remove();
      measureLabel = null;
    }

    if (measureMode === 'area') {
      if (lonLats.length >= 3) {
        const ring = [...lonLats, lonLats[0]]; // closed
        src.setData({
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: [ring] },
          properties: {},
        });
        const area = polygonArea(measurePts);
        // Center label at polygon centroid (mean of vertices — good enough
        // for typical small areas).
        const cLon = lonLats.reduce((s, p) => s + p[0], 0) / lonLats.length;
        const cLat = lonLats.reduce((s, p) => s + p[1], 0) / lonLats.length;
        measureLabel = labelMarker([cLon, cLat], fmtArea(area), '#ff5252');
      } else if (lonLats.length >= 2) {
        src.setData({
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: lonLats },
          properties: {},
        });
      }
    } else {
      if (lonLats.length >= 2) {
        src.setData({
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: lonLats },
          properties: {},
        });
        let total = 0;
        for (let i = 1; i < measurePts.length; i++) {
          total += segDist(measurePts[i - 1], measurePts[i]);
        }
        measureLabel = labelMarker(lonLats[lonLats.length - 1], fmtDist(total), '#ff5252');
      }
    }
  }

  function toggleFenceDraw() {
    // Toggle-only; never wipe the polygon. Mirrors 2D MapView.svelte:376 —
    // user clicks Fence → enter draw mode, adds vertices, clicks again to
    // exit and keep the polygon for FencePanel to upload. The explicit
    // Clear button (rendered only when drawingFence OR polygon non-empty)
    // is the one path that actually empties fencePolygon.
    app.drawingFence = !app.drawingFence;
  }

  function toggleSurveyDraw() {
    // Same toggle-only pattern as fence — SurveyPanel manages the polygon
    // lifecycle and grid generation; the map button just enters/leaves
    // drawing mode without destroying the existing polygon.
    app.drawingPolygon = !app.drawingPolygon;
  }

  function clearFence() {
    app.drawingFence = false;
    app.fencePolygon = [];
  }

  onDestroy(() => {
    window.removeEventListener('keydown', onKeyDown);
    if (droneMarker) droneMarker.remove();
    if (homeMarker) homeMarker.remove();
    wpMarkers.forEach((m) => m.remove());
    wpMarkers = [];
    if (wpPopup) {
      wpPopup.remove();
      wpPopup = null;
    }
    fenceVertMarkers.forEach((m) => m.remove());
    fenceVertMarkers = [];
    surveyVertMarkers.forEach((m) => m.remove());
    surveyVertMarkers = [];
    measureVertMarkers.forEach((m) => m.remove());
    measureVertMarkers = [];
    if (measureLabel) {
      measureLabel.remove();
      measureLabel = null;
    }
    if (replayMarker) {
      replayMarker.remove();
      replayMarker = null;
    }
    adsbMarkers.forEach((m) => m.remove());
    adsbMarkers.clear();
    if (map) map.remove();
  });

  $effect(() => {
    if (!map) return;
    const d = app.drone;
    if (!d.connected || d.lat === 0) return;

    const [mlat, mlon] = toMap(d.lat, d.lon);

    if (!droneMarker) {
      const el = document.createElement('div');
      const svg = createSvgElement(
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><polygon points="16,4 8,28 16,22 24,28" fill="#4fc3f7" stroke="#fff" stroke-width="1.5"/></svg>',
      );
      el.appendChild(svg);
      el.style.transform = `rotate(${d.hdg}deg)`;
      droneMarker = new maplibregl.Marker({ element: el, rotationAlignment: 'map' })
        .setLngLat([mlon, mlat])
        .addTo(map!);
    } else {
      droneMarker.setLngLat([mlon, mlat]);
      (droneMarker.getElement() as HTMLElement).style.transform = `rotate(${d.hdg}deg)`;
    }

    if (Math.abs(mlat - prevLat) > 0.00001 || Math.abs(mlon - prevLon) > 0.00001) {
      trailCoords.push([mlon, mlat]);
      if (trailCoords.length > 2000) trailCoords = trailCoords.slice(-1500);
      prevLat = mlat;
      prevLon = mlon;
      const trailSrc = map!.getSource('trail') as maplibregl.GeoJSONSource;
      if (trailSrc) {
        trailSrc.setData({
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: trailCoords },
          properties: {},
        });
      }
    }

    if (d.home_lat !== 0 && !homeMarker) {
      const [hlat, hlon] = toMap(d.home_lat, d.home_lon);
      const hel = document.createElement('div');
      const hsvg = createSvgElement(
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20"><circle cx="10" cy="10" r="8" fill="#4caf50" stroke="#fff" stroke-width="2"/><text x="10" y="14" text-anchor="middle" fill="white" font-size="10" font-weight="bold">H</text></svg>',
      );
      hel.appendChild(hsvg);
      homeMarker = new maplibregl.Marker({ element: hel }).setLngLat([hlon, hlat]).addTo(map!);
    }
  });

  $effect(() => {
    if (!map || !map.isStyleLoaded()) return;
    const wps = app.waypoints;
    const src = map.getSource('waypoints') as maplibregl.GeoJSONSource;
    if (!src) return;

    // Path line (rebuilt from full waypoint list every time it changes).
    if (wps.length >= 2) {
      const coords = wps.map((w) => {
        const [lat, lon] = toMap(w.lat, w.lon);
        return [lon, lat] as [number, number];
      });
      src.setData({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: coords },
        properties: {},
      });
    } else {
      src.setData({ type: 'FeatureCollection', features: [] });
    }

    // Per-waypoint draggable markers. Simpler to dispose + rebuild than to
    // diff — Argus missions are typically < 50 WPs so the DOM churn is
    // negligible. Closures capture the current index at marker creation.
    wpMarkers.forEach((m) => m.remove());
    wpMarkers = [];
    if (wpPopup) {
      wpPopup.remove();
      wpPopup = null;
    }

    wps.forEach((wp, i) => {
      const [mlat, mlon] = toMap(wp.lat, wp.lon);
      const isLoiter = wp.type === 'loiter_turns' || wp.type === 'loiter_time';
      const color = wp.drop ? '#e65100' : isLoiter ? '#7e57c2' : '#1565c0';
      const el = document.createElement('div');
      el.style.cssText = `position:relative;width:22px;height:22px;border-radius:50%;background:${color};color:white;text-align:center;line-height:22px;font-size:11px;font-weight:bold;border:2px solid white;box-shadow:0 0 4px rgba(0,0,0,0.6);cursor:pointer`;
      el.textContent = String(i + 1);
      if (wp.drop) {
        const badge = document.createElement('div');
        badge.style.cssText =
          'position:absolute;top:-5px;right:-5px;width:8px;height:8px;border-radius:50%;background:#ff5722;border:1px solid white';
        el.appendChild(badge);
      }

      const m = new maplibregl.Marker({ element: el, draggable: true }).setLngLat([mlon, mlat]).addTo(map!);

      m.on('dragend', () => {
        const ll = m.getLngLat();
        const [wlat, wlon] = fromMap(ll.lat, ll.lng);
        // Mutate in-place; the $effect that just rebuilt markers won't re-run
        // because Svelte 5 tracks .lat/.lon writes on the same array element.
        app.waypoints[i].lat = wlat;
        app.waypoints[i].lon = wlon;
        saveWaypoints();
      });

      el.addEventListener('click', (ev) => {
        ev.stopPropagation();
        // Build popup DOM piecewise — never innerHTML on values pulled from
        // app state, even though wp fields here are typed as number/bool.
        const popupEl = document.createElement('div');
        popupEl.style.cssText = 'font-size:12px;min-width:160px';

        const title = document.createElement('b');
        title.textContent = `${t('label.wp')} ${i + 1}`;
        popupEl.appendChild(title);
        if (wp.drop) {
          const dropSpan = document.createElement('span');
          dropSpan.style.color = '#e65100';
          dropSpan.textContent = ` · ${t('label.drop')}`;
          popupEl.appendChild(dropSpan);
        }
        popupEl.appendChild(document.createElement('br'));

        const coord = document.createElement('span');
        coord.style.color = '#888';
        coord.textContent = `${wp.lat.toFixed(6)}, ${wp.lon.toFixed(6)}`;
        popupEl.appendChild(coord);
        popupEl.appendChild(document.createElement('br'));

        const altLabel = document.createTextNode(`${t('label.alt')}: `);
        popupEl.appendChild(altLabel);
        const altVal = document.createElement('b');
        altVal.textContent = `${wp.alt}m`;
        popupEl.appendChild(altVal);
        if (wp.speed) {
          popupEl.appendChild(document.createTextNode(` · ${t('label.spd')}: ${wp.speed}m/s`));
        }

        const btn = document.createElement('button');
        btn.textContent = t('label.delete');
        btn.style.cssText =
          'display:block;margin-top:6px;padding:3px 10px;background:#d32f2f;color:white;border:none;border-radius:3px;cursor:pointer;font-size:11px;font-weight:600';
        btn.addEventListener('click', () => {
          deleteWaypoint(i);
          if (wpPopup) {
            wpPopup.remove();
            wpPopup = null;
          }
        });
        popupEl.appendChild(btn);

        if (wpPopup) wpPopup.remove();
        wpPopup = new maplibregl.Popup({ closeOnClick: true, offset: 14 })
          .setLngLat([mlon, mlat])
          .setDOMContent(popupEl)
          .addTo(map!);
      });

      wpMarkers.push(m);
    });
  });

  /* ── Fence rendering ────────────────────────────────────────────────────
   * Mirrors src/components/layers/FenceLayer.svelte (the 2D path). Polygon
   * fill when ≥3 vertices, polyline when 2, plus per-vertex marker (first
   * vertex white-filled to mark the start). Re-runs on fencePolygon edits.
   */
  $effect(() => {
    if (!map || !map.isStyleLoaded()) return;
    const src = map.getSource('fence') as maplibregl.GeoJSONSource | undefined;
    if (!src) return;

    fenceVertMarkers.forEach((m) => m.remove());
    fenceVertMarkers = [];

    const verts = app.fencePolygon;
    if (verts.length === 0) {
      src.setData({ type: 'FeatureCollection', features: [] });
      return;
    }

    const lonLats: [number, number][] = verts.map((p) => {
      const [mlat, mlon] = toMap(p.lat, p.lon);
      return [mlon, mlat];
    });

    if (lonLats.length >= 3) {
      const ring = [...lonLats, lonLats[0]];
      src.setData({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [ring] },
        properties: {},
      });
    } else {
      src.setData({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: lonLats },
        properties: {},
      });
    }

    // Differentiate uploaded vs draft polygons — 2D FenceLayer.svelte:17-30
    // makes uploaded polygons solid + opaque so operators can see at a
    // glance whether the local edit has been pushed to the FC.
    const uploaded = app.fenceUploaded;
    map.setPaintProperty('fence-fill', 'fill-opacity', uploaded ? 0.18 : 0.1);
    map.setPaintProperty('fence-line', 'line-width', uploaded ? 2.5 : 2);
    map.setPaintProperty('fence-line', 'line-dasharray', uploaded ? [1, 0] : [3, 2]);

    lonLats.forEach((pt, i) => {
      // First vertex inverted (white-filled) to mark the polygon start,
      // matching 2D FenceLayer.svelte:34.
      const el = document.createElement('div');
      el.style.cssText = `width:10px;height:10px;border-radius:50%;background:${i === 0 ? '#fff' : '#f44336'};border:2px solid #f44336;box-shadow:0 0 3px rgba(0,0,0,0.6)`;
      fenceVertMarkers.push(new maplibregl.Marker({ element: el }).setLngLat(pt).addTo(map!));
    });
  });

  /* ── Survey polygon rendering — mirrors SurveyLayer.svelte ─────────────
   * Same dispose+rebuild pattern as fence. Purple instead of red. First
   * vertex inverted (white-filled) marks the polygon start direction.
   */
  $effect(() => {
    if (!map || !map.isStyleLoaded()) return;
    const src = map.getSource('survey') as maplibregl.GeoJSONSource | undefined;
    if (!src) return;

    surveyVertMarkers.forEach((m) => m.remove());
    surveyVertMarkers = [];

    const verts = app.surveyPolygon;
    if (verts.length === 0) {
      src.setData({ type: 'FeatureCollection', features: [] });
      return;
    }
    const lonLats: [number, number][] = verts.map((p) => {
      const [mlat, mlon] = toMap(p.lat, p.lon);
      return [mlon, mlat];
    });
    if (lonLats.length >= 3) {
      const ring = [...lonLats, lonLats[0]];
      src.setData({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [ring] },
        properties: {},
      });
    } else {
      src.setData({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: lonLats },
        properties: {},
      });
    }
    lonLats.forEach((pt, i) => {
      const el = document.createElement('div');
      el.style.cssText = `width:10px;height:10px;border-radius:50%;background:${i === 0 ? '#fff' : '#ab47bc'};border:2px solid #ab47bc;box-shadow:0 0 3px rgba(0,0,0,0.6)`;
      surveyVertMarkers.push(new maplibregl.Marker({ element: el }).setLngLat(pt).addTo(map!));
    });
  });

  /* ── Replay layer — mirrors ReplayLayer.svelte ────────────────────────
   * Driven by app.replayPos ({lat, lon, yaw} | null). When non-null, render
   * an orange triangle rotated by yaw + a trail polyline. When null, tear
   * everything down. Trail caps at 3000 points (same as 2D).
   */
  $effect(() => {
    if (!map || !map.isStyleLoaded()) return;
    const rp = app.replayPos;
    const trailSrc = map.getSource('replay-trail') as maplibregl.GeoJSONSource | undefined;

    if (!rp) {
      if (replayMarker) {
        replayMarker.remove();
        replayMarker = null;
      }
      replayTrail = [];
      if (trailSrc) {
        trailSrc.setData({
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: [] },
          properties: {},
        });
      }
      return;
    }

    const [mlat, mlon] = toMap(rp.lat, rp.lon);
    if (!replayMarker) {
      const el = document.createElement('div');
      el.style.cssText = 'width:28px;height:28px;transform-origin:center';
      // Orange arrow SVG — same shape as 2D ReplayLayer.svelte:23-27.
      const svg = createSvgElement(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-12 -12 24 24" width="28" height="28">' +
          '<polygon points="0,-10 -7,8 0,4 7,8" fill="#ffa726" stroke="white" stroke-width="1"/></svg>',
      );
      el.appendChild(svg);
      el.style.transform = `rotate(${rp.yaw}deg)`;
      replayMarker = new maplibregl.Marker({ element: el, rotationAlignment: 'map' })
        .setLngLat([mlon, mlat])
        .addTo(map);
    } else {
      replayMarker.setLngLat([mlon, mlat]);
      (replayMarker.getElement() as HTMLElement).style.transform = `rotate(${rp.yaw}deg)`;
    }

    replayTrail.push([mlon, mlat]);
    if (replayTrail.length > 3000) replayTrail = replayTrail.slice(-2000);
    if (trailSrc) {
      trailSrc.setData({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: replayTrail },
        properties: {},
      });
    }
  });

  /* ── ADSB traffic — mirrors DroneLayer.svelte:136-162 ───────────────── */
  $effect(() => {
    if (!map) return;
    const adsb = app.drone.adsb || [];
    const seen = new Set<number>();
    for (const a of adsb) {
      seen.add(a.icao);
      const [mlat, mlon] = toMap(a.lat, a.lon);
      const existing = adsbMarkers.get(a.icao);
      const title = `${a.callsign || 'ADSB'} | ${a.alt.toFixed(0)}m | ${a.speed.toFixed(0)}m/s`;
      if (existing) {
        existing.setLngLat([mlon, mlat]);
        const el = existing.getElement() as HTMLElement;
        const arrow = el.querySelector('.adsb-arrow') as HTMLElement | null;
        if (arrow) arrow.style.transform = `rotate(${a.hdg}deg)`;
        el.title = title;
        continue;
      }
      // Yellow triangle aircraft + callsign label above. Same colors and
      // shape as DroneLayer.svelte:148-153.
      const el = document.createElement('div');
      el.style.cssText = 'position:relative;width:20px;height:20px';
      el.title = title;
      const arrow = document.createElement('div');
      arrow.className = 'adsb-arrow';
      arrow.style.cssText = `transform:rotate(${a.hdg}deg);transform-origin:center`;
      const svg = createSvgElement(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-10 -10 20 20" width="20" height="20">' +
          '<polygon points="0,-8 -5,6 0,3 5,6" fill="#ffc107" stroke="#333" stroke-width="0.5"/></svg>',
      );
      arrow.appendChild(svg);
      el.appendChild(arrow);
      const label = document.createElement('div');
      label.style.cssText =
        'position:absolute;top:-14px;left:50%;transform:translateX(-50%);font-size:8px;color:#ffc107;font-weight:bold;white-space:nowrap;text-shadow:0 0 2px #000';
      label.textContent = a.callsign || a.icao.toString(16);
      el.appendChild(label);

      const m = new maplibregl.Marker({ element: el, rotationAlignment: 'map' }).setLngLat([mlon, mlat]).addTo(map!);
      adsbMarkers.set(a.icao, m);
    }
    // Remove markers for ICAOs no longer in the traffic list.
    for (const [icao, m] of adsbMarkers) {
      if (!seen.has(icao)) {
        m.remove();
        adsbMarkers.delete(icao);
      }
    }
  });

  // Tile-source switching: swap the raster source URL when app.tileSource
  // changes. Mirrors MapView.svelte:applyTileSource — re-creating layers
  // is the canonical maplibre pattern since setStyle() would nuke the
  // waypoint/fence/measure overlays we just added. NOTE: existing markers
  // continue to display at their old GCJ-shifted positions until the next
  // edit triggers a rebuild — same latent quirk as the 2D path.
  let prevTileSource = '';
  $effect(() => {
    const ts = app.tileSource;
    if (!map || !map.isStyleLoaded() || ts === prevTileSource) return;
    prevTileSource = ts;
    const src = curSource();
    const url = `${API_BASE}/api/tile/${src.sat}/{z}/{x}/{y}`;
    if (map.getLayer('raster')) map.removeLayer('raster');
    if (map.getSource('raster-tiles')) map.removeSource('raster-tiles');
    map.addSource('raster-tiles', {
      type: 'raster',
      tiles: [url],
      tileSize: 256,
      maxzoom: 18,
    });
    // Insert raster BELOW all overlays so waypoint/fence/measure stay visible.
    const firstOverlay = map.getLayer('waypoint-line') ? 'waypoint-line' : undefined;
    map.addLayer({ id: 'raster', type: 'raster', source: 'raster-tiles' }, firstOverlay);
  });
</script>

<div class="relative flex-1 min-w-0">
  <div bind:this={mapEl} class="h-full rounded-lg border border-border"></div>

  <div class="absolute top-2.5 left-2.5 z-10 flex gap-1">
    <div class="map-btn">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        ><path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" /></svg
      >
      3D {t('map.satellite')}
    </div>

    <button
      class="map-btn {measuring && measureMode === 'distance' ? '!text-red-400 !border-red-400' : ''}"
      onclick={() => toggleMeasure('distance')}
      title={t('map.measure')}
    >
      <Ruler size={13} />{t('map.measure')}
    </button>
    <button
      class="map-btn {measuring && measureMode === 'area' ? '!text-red-400 !border-red-400' : ''}"
      onclick={() => toggleMeasure('area')}
      title={t('map.area')}
    >
      <Square size={13} />{t('map.area')}
    </button>
    <button
      class="map-btn {app.drawingFence ? '!text-red-400 !border-red-400' : ''}"
      onclick={toggleFenceDraw}
      title={t('map.fence')}
    >
      <ShieldAlert size={13} />{t('map.fence')}
    </button>
    <button
      class="map-btn {app.drawingPolygon ? '!text-purple-400 !border-purple-400' : ''}"
      onclick={toggleSurveyDraw}
      title={t('map.survey')}
    >
      <Grid3x3 size={13} />{t('map.survey')}
    </button>
    {#if app.fencePolygon.length > 0 || app.surveyPolygon.length > 0 || measuring}
      <button
        class="map-btn"
        onclick={() => {
          clearMeasure();
          clearFence();
        }}
        title={t('label.clear')}
      >
        <XIcon size={13} />
      </button>
    {/if}
  </div>

  {#if app.drone.connected}
    <div
      class="absolute bottom-2 left-2.5 z-10 bg-card/85 backdrop-blur text-muted-foreground px-2 py-0.5 rounded text-[11px] font-mono"
    >
      {app.drone.lat.toFixed(6)}, {app.drone.lon.toFixed(6)} | {app.drone.alt_rel.toFixed(1)}m AGL
    </div>
  {/if}
</div>

<style>
  .map-btn {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 4px 10px;
    background: hsl(var(--card) / 0.92);
    border: 1px solid hsl(var(--border));
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 600;
    color: hsl(var(--muted-foreground));
    backdrop-filter: blur(4px);
  }
</style>
