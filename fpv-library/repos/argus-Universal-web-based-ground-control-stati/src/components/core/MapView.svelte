<script lang="ts">
  import { onMount } from 'svelte';
  import { app, addWaypoint, addToast, showConfirm } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { fmtDist } from '../../lib/units';
  import { toGcj, toWgs } from '../../lib/gcj02';
  import { API_BASE } from '../../lib/backend';
  import MapControls from './MapControls.svelte';
  import HudOverlay from './HudOverlay.svelte';
  import { FileUp } from '@lucide/svelte';
  import DroneLayer from '../layers/DroneLayer.svelte';
  import WaypointLayer from '../layers/WaypointLayer.svelte';
  import GuidedLayer from '../layers/GuidedLayer.svelte';
  import FenceLayer from '../layers/FenceLayer.svelte';
  import SurveyLayer from '../layers/SurveyLayer.svelte';
  import ReplayLayer from '../layers/ReplayLayer.svelte';
  import {
    Layers,
    Ruler,
    Navigation,
    Grid3x3,
    ShieldAlert,
    Download,
    Crosshair,
    Home,
    Maximize2,
  } from '@lucide/svelte';
  import { t } from '../../lib/i18n.svelte';

  let { showHud = true }: { showHud?: boolean } = $props();

  let mapEl: HTMLDivElement;
  let map = $state<L.Map | null>(null);
  let follow = $state(true);
  let isSat = $state(true);
  let measuring = $state(false);
  let mouseCoord = $state('');
  let guidedTarget = $state<{ lat: number; lon: number; alt: number } | null>(null);
  let droneTrail: [number, number][] = $state([]);

  let satLayer: L.TileLayer | null = null;
  let vecLayer: L.TileLayer | null = null;
  let labelLayer: L.TileLayer | null = null;
  let measurePts: { marker: L.CircleMarker; ll: L.LatLng }[] = [];
  let measureLine: L.Polyline | null = null;
  let measureLabel: L.Marker | null = null;
  let measureMode: 'distance' | 'area' = $state<'distance' | 'area'>('distance');
  let measurePolygon: L.Polygon | null = null;

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
    carto_dark: {
      name: 'CartoDB Dark',
      sat: 'carto_dark',
      vec: 'carto_dark',
      label: null,
      gcj02: false,
      region: 'global',
    },
    carto_light: {
      name: 'CartoDB Light',
      sat: 'carto_light',
      vec: 'carto_light',
      label: null,
      gcj02: false,
      region: 'global',
    },
    esri: { name: 'Esri Topo', sat: 'osm_sat', vec: 'esri_topo', label: null, gcj02: false, region: 'global' },
    tianditu: { name: 'Tianditu', sat: 'tdt_sat', vec: 'tdt_vec', label: 'tdt_label', gcj02: false, region: 'china' },
  };

  function tileUrl(style: string): string {
    return `${API_BASE}/api/tile/${style}/{z}/{x}/{y}`;
  }

  function curSource(): TileSourceDef {
    return SOURCES[app.tileSource] || SOURCES['amap'];
  }

  let useGcj = $derived(curSource().gcj02);

  function toMap(lat: number, lon: number): [number, number] {
    return useGcj ? toGcj(lat, lon) : [lat, lon];
  }
  function fromMap(mlat: number, mlon: number): [number, number] {
    return useGcj ? toWgs(mlat, mlon) : [mlat, mlon];
  }

  function applyTileSource() {
    if (!map) return;
    const src = curSource();
    if (satLayer) map!.removeLayer(satLayer!);
    if (labelLayer) map!.removeLayer(labelLayer!);
    if (vecLayer) map!.removeLayer(vecLayer!);
    satLayer = L.tileLayer(tileUrl(src.sat), { maxZoom: 18 });
    vecLayer = L.tileLayer(tileUrl(src.vec), { maxZoom: 18 });
    labelLayer = src.label ? L.tileLayer(tileUrl(src.label), { maxZoom: 18 }) : null;
    if (isSat) {
      satLayer.addTo(map!);
      if (labelLayer) labelLayer.addTo(map!);
    } else {
      vecLayer.addTo(map!);
    }
  }

  let prevTileSource = '';
  $effect(() => {
    const ts = app.tileSource;
    if (ts !== prevTileSource && map) {
      prevTileSource = ts;
      applyTileSource();
    }
  });

  onMount(() => {
    const src = curSource();
    prevTileSource = app.tileSource;
    map = L.map(mapEl, { zoomControl: true, attributionControl: false }).setView([34.258, 108.942], 15);
    satLayer = L.tileLayer(tileUrl(src.sat), { maxZoom: 18 }).addTo(map!);
    labelLayer = src.label ? L.tileLayer(tileUrl(src.label), { maxZoom: 18 }).addTo(map) : null;
    vecLayer = L.tileLayer(tileUrl(src.vec), { maxZoom: 18 });
    L.control.scale({ metric: true, imperial: false, position: 'bottomright' }).addTo(map!);
    map.on('click', onMapClick);
    map.on('contextmenu', onRightClick);
    map.on('mousemove', (e: L.LeafletMouseEvent) => {
      const [wlat, wlon] = fromMap(e.latlng.lat, e.latlng.lng);
      mouseCoord = `${wlat.toFixed(6)}, ${wlon.toFixed(6)}`;
    });
    window.addEventListener('keydown', onKeyDown);
    const invalidateTimer = setTimeout(() => {
      if (map) map.invalidateSize();
    }, 100);
    return () => {
      clearTimeout(invalidateTimer);
      window.removeEventListener('keydown', onKeyDown);
      if (map) {
        map.remove();
        map = null;
      }
    };
  });

  function onMapClick(e: L.LeafletMouseEvent) {
    const ll = e.latlng;
    if (measuring) {
      addMeasurePoint(ll);
      return;
    }
    if (app.drawingPolygon) {
      const [wlat, wlon] = fromMap(ll.lat, ll.lng);
      app.surveyPolygon = [...app.surveyPolygon, { lat: wlat, lon: wlon }];
      return;
    }
    if (app.drawingFence) {
      const [wlat, wlon] = fromMap(ll.lat, ll.lng);
      app.fencePolygon = [...app.fencePolygon, { lat: wlat, lon: wlon }];
      return;
    }
    if (app.guidedMode && app.drone.connected && app.drone.armed) {
      const [wlat, wlon] = fromMap(ll.lat, ll.lng);
      dispatch('guided_goto', undefined, { lat: wlat, lon: wlon, alt: app.defaultAlt });
      guidedTarget = { lat: wlat, lon: wlon, alt: app.defaultAlt };
      addToast(`${t('map.guided')} → ${wlat.toFixed(5)}, ${wlon.toFixed(5)}`, 'info');
      return;
    }
    const [wlat, wlon] = fromMap(ll.lat, ll.lng);
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
  }

  function onRightClick(e: L.LeafletMouseEvent) {
    e.originalEvent.preventDefault();
    if (!app.drone.connected || !app.drone.armed) return;
    const ll = e.latlng;
    const [wlat, wlon] = fromMap(ll.lat, ll.lng);
    showConfirm(
      `${t('confirm.guidedGoto')}\n${wlat.toFixed(5)}, ${wlon.toFixed(5)}\n${t('ctrl.altitude')}: ${app.defaultAlt}m`,
    ).then((ok) => {
      if (ok) {
        dispatch('guided_goto', undefined, { lat: wlat, lon: wlon, alt: app.defaultAlt });
        guidedTarget = { lat: wlat, lon: wlon, alt: app.defaultAlt };
        addToast(`${t('map.guided')} → ${wlat.toFixed(5)}, ${wlon.toFixed(5)}`, 'info');
      }
    });
  }

  function onKeyDown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      if (measuring) clearMeasure();
      if (app.guidedMode) {
        app.guidedMode = false;
        guidedTarget = null;
      }
      if (app.drawingPolygon) {
        app.drawingPolygon = false;
        app.surveyPolygon = [];
      }
      if (app.drawingFence) {
        app.drawingFence = false;
        app.fencePolygon = [];
      }
      map?.closePopup();
    }
    if (e.key === 'g' && (e.target as HTMLElement).tagName !== 'INPUT') {
      if (app.drone.connected && app.drone.armed) app.guidedMode = !app.guidedMode;
    }
  }

  function calcPolygonArea(pts: { lat: number; lng: number }[]): number {
    if (pts.length < 3) return 0;
    let area = 0;
    const R = 6371000;
    for (let i = 0; i < pts.length; i++) {
      const j = (i + 1) % pts.length;
      const lat1 = (pts[i].lat * Math.PI) / 180,
        lat2 = (pts[j].lat * Math.PI) / 180;
      const dlon = ((pts[j].lng - pts[i].lng) * Math.PI) / 180;
      area += dlon * (2 + Math.sin(lat1) + Math.sin(lat2));
    }
    return Math.abs((area * R * R) / 2);
  }

  function fmtArea(m2: number): string {
    if (m2 < 10000) return `${m2.toFixed(0)} m²`;
    if (m2 < 1e6) return `${(m2 / 10000).toFixed(2)} ha`;
    return `${(m2 / 1e6).toFixed(3)} km²`;
  }

  function addMeasurePoint(ll: L.LatLng) {
    const cm = L.circleMarker([ll.lat, ll.lng], {
      radius: 4,
      color: '#ff5252',
      fillColor: '#ff5252',
      fillOpacity: 1,
    }).addTo(map!);
    measurePts.push({ marker: cm, ll });
    const pts = measurePts.map((p) => [p.ll.lat, p.ll.lng] as [number, number]);

    if (measureMode === 'area') {
      if (measurePolygon) map!.removeLayer(measurePolygon);
      if (measureLabel) map!.removeLayer(measureLabel);
      if (pts.length >= 3) {
        measurePolygon = L.polygon(pts, {
          color: '#ff5252',
          weight: 2,
          dashArray: '4,4',
          fillColor: '#ff5252',
          fillOpacity: 0.1,
        }).addTo(map!);
        const area = calcPolygonArea(measurePts.map((p) => p.ll));
        const center = measurePolygon.getBounds().getCenter();
        measureLabel = L.marker(center, {
          icon: L.divIcon({
            className: '',
            html: `<div style="background:rgba(30,30,30,0.9);color:#ff5252;padding:2px 6px;border-radius:3px;font-size:11px;font-weight:bold;white-space:nowrap">${fmtArea(area)}</div>`,
            iconAnchor: [0, 0],
          }),
        }).addTo(map!);
      } else if (pts.length >= 2) {
        if (measureLine) map!.removeLayer(measureLine);
        measureLine = L.polyline(pts, { color: '#ff5252', weight: 2, dashArray: '4,4' }).addTo(map!);
      }
    } else {
      if (measurePts.length >= 2) {
        let total = 0;
        for (let i = 1; i < measurePts.length; i++) total += map!.distance(measurePts[i - 1].ll, measurePts[i].ll);
        if (measureLine) map!.removeLayer(measureLine);
        measureLine = L.polyline(pts, { color: '#ff5252', weight: 2, dashArray: '4,4' }).addTo(map!);
        if (measureLabel) map!.removeLayer(measureLabel);
        const last = measurePts[measurePts.length - 1].ll;
        const txt = fmtDist(total);
        measureLabel = L.marker([last.lat, last.lng], {
          icon: L.divIcon({
            className: '',
            html: `<div style="background:rgba(30,30,30,0.9);color:#ff5252;padding:2px 6px;border-radius:3px;font-size:11px;font-weight:bold;white-space:nowrap">${txt}</div>`,
            iconAnchor: [0, -10],
          }),
        }).addTo(map!);
      }
    }
  }

  function clearMeasure() {
    measuring = false;
    measurePts.forEach((p) => map!.removeLayer(p.marker));
    measurePts = [];
    if (measureLine) {
      map!.removeLayer(measureLine);
      measureLine = null;
    }
    if (measureLabel) {
      map!.removeLayer(measureLabel);
      measureLabel = null;
    }
    if (measurePolygon) {
      map!.removeLayer(measurePolygon);
      measurePolygon = null;
    }
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

  let kmlLayers: L.Layer[] = $state([]);

  function importKmlOverlay() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.kml,.kmz';
    input.onchange = (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev: ProgressEvent<FileReader>) => {
        try {
          const doc = new DOMParser().parseFromString(ev.target!.result as string, 'text/xml');
          let count = 0;
          const placemarks = doc.getElementsByTagName('Placemark');
          for (let i = 0; i < placemarks.length; i++) {
            const pm = placemarks[i];
            const coordsEl = pm.getElementsByTagName('coordinates');
            if (coordsEl.length === 0) continue;
            const pts: [number, number][] = [];
            coordsEl[0]
              .textContent!.trim()
              .split(/\s+/)
              .forEach((c: string) => {
                const p = c.split(',');
                if (p.length >= 2) {
                  const lon = parseFloat(p[0]),
                    lat = parseFloat(p[1]);
                  if (Math.abs(lat) > 0.001) {
                    const [mlat, mlon] = toMap(lat, lon);
                    pts.push([mlat, mlon]);
                  }
                }
              });
            if (pts.length < 2) continue;
            const isPolygon = pm.getElementsByTagName('Polygon').length > 0;
            const layer = isPolygon
              ? L.polygon(pts, { color: '#e040fb', weight: 2, fillOpacity: 0.1 }).addTo(map!)
              : L.polyline(pts, { color: '#e040fb', weight: 2 }).addTo(map!);
            const name = pm.getElementsByTagName('name')[0]?.textContent || '';
            if (name) layer.bindTooltip(name, { permanent: false });
            kmlLayers.push(layer);
            count++;
          }
          addToast(t('kml.loaded').replace('{n}', String(count)), 'success');
        } catch {
          addToast(t('kml.loadFail'), 'error');
        }
      };
      reader.readAsText(file);
    };
    input.click();
  }

  function clearKmlOverlay() {
    kmlLayers.forEach((l) => map!.removeLayer(l));
    kmlLayers = [];
  }

  function toggleMapType() {
    isSat = !isSat;
    if (isSat) {
      map!.removeLayer(vecLayer!);
      map!.addLayer(satLayer!);
      map!.addLayer(labelLayer!);
    } else {
      map!.removeLayer(satLayer!);
      map!.removeLayer(labelLayer!);
      map!.addLayer(vecLayer!);
    }
  }

  function fitRoute() {
    const pts = app.waypoints.map((w) => toMap(w.lat, w.lon));
    if (pts.length) map!.fitBounds(L.latLngBounds(pts), { padding: [40, 40] });
  }

  function centerHome() {
    if (app.drone.home_lat) map!.setView(toMap(app.drone.home_lat, app.drone.home_lon), 16);
  }

  function exportTrack() {
    if (!droneTrail.length) return;
    const coords = droneTrail
      .map(([glat, glon]) => {
        const [wlat, wlon] = fromMap(glat, glon);
        return `${wlon},${wlat},0`;
      })
      .join('\n');
    const kml = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Flight Track</name>
<Style id="track"><LineStyle><color>ff4fc3f7</color><width>2</width></LineStyle></Style>
<Placemark><name>Track</name><styleUrl>#track</styleUrl>
<LineString><coordinates>${coords}</coordinates></LineString>
</Placemark></Document></kml>`;
    const blob = new Blob([kml], { type: 'application/vnd.google-earth.kml+xml' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'track_' + new Date().toISOString().slice(0, 10) + '.kml';
    a.click();
    URL.revokeObjectURL(a.href);
  }
</script>

<div class="relative flex-1 min-w-0">
  <div bind:this={mapEl} class="h-full rounded-lg border border-border"></div>

  {#if map}
    <DroneLayer {map} {follow} trail={droneTrail} coord={toMap} />
    <WaypointLayer {map} coord={toMap} coordInv={fromMap} />
    <GuidedLayer {map} bind:target={guidedTarget} coord={toMap} />
    <FenceLayer {map} coord={toMap} />
    <SurveyLayer {map} coord={toMap} />
    <ReplayLayer {map} {follow} coord={toMap} />
  {/if}

  <div class="absolute top-2.5 left-2.5 z-[1000] flex gap-1">
    <button class="map-btn" onclick={toggleMapType} title={isSat ? t('map.street') : t('map.satellite')}>
      <Layers size={13} />{isSat ? t('map.satellite') : t('map.street')}
    </button>
    <button
      class="map-btn {measuring && measureMode === 'distance' ? '!text-destructive !border-destructive' : ''}"
      onclick={() => toggleMeasure('distance')}
      title={t('map.measure')}
    >
      <Ruler size={13} />{measuring && measureMode === 'distance' ? t('map.cancel') : t('map.measure')}
    </button>
    <button
      class="map-btn {measuring && measureMode === 'area' ? '!text-destructive !border-destructive' : ''}"
      onclick={() => toggleMeasure('area')}
      title={t('map.area')}
    >
      □ {measuring && measureMode === 'area' ? t('map.cancel') : t('map.area')}
    </button>
    {#if app.drone.connected && app.drone.armed}
      <button
        class="map-btn {app.guidedMode ? '!text-warning !border-warning' : ''}"
        onclick={() => (app.guidedMode = !app.guidedMode)}
        title={t('map.guided')}
      >
        <Navigation size={13} />{app.guidedMode ? t('map.guidedActive') : t('map.guided')}
      </button>
    {/if}
    <button
      class="map-btn {app.showSurvey || app.drawingPolygon ? '!text-purple-400 !border-purple-400' : ''}"
      onclick={() => (app.showSurvey = !app.showSurvey)}
      title={t('map.survey')}
    >
      <Grid3x3 size={13} />{t('map.survey')}
    </button>
    <button
      class="map-btn {app.showFence || app.drawingFence ? '!text-destructive !border-destructive' : ''}"
      onclick={() => (app.showFence = !app.showFence)}
      title={t('map.fence')}
    >
      <ShieldAlert size={13} />{t('map.fence')}
    </button>
    {#if droneTrail.length > 10}
      <button class="map-btn" onclick={exportTrack} title={t('map.track')}>
        <Download size={13} />{t('map.track')}
      </button>
    {/if}
    <button class="map-btn" onclick={importKmlOverlay} title={t('kml.import')}>
      <FileUp size={13} />KML
    </button>
    {#if kmlLayers.length > 0}
      <button class="map-btn !text-purple-400 !border-purple-400" onclick={clearKmlOverlay} title={t('kml.clear')}>
        ✕ KML
      </button>
    {/if}
  </div>
  <div class="absolute top-2.5 right-2.5 z-[1000] flex gap-1">
    <button
      class="map-btn {follow ? '!text-destructive !border-destructive' : ''}"
      onclick={() => (follow = !follow)}
      title={follow ? t('map.free') : t('map.follow')}
    >
      <Crosshair size={13} />{follow ? t('map.follow') : t('map.free')}
    </button>
    <button class="map-btn" onclick={centerHome} title={t('map.home')}>
      <Home size={13} />{t('map.home')}
    </button>
    <button class="map-btn" onclick={fitRoute} title={t('map.fitAll')}>
      <Maximize2 size={13} />{t('map.fitAll')}
    </button>
  </div>
  {#if app.drone.connected}
    <div class="absolute top-12 right-3 z-[1000]" title="{t('telem.hdg')} {app.drone.hdg.toFixed(0)}°">
      <svg width="42" height="42" viewBox="0 0 42 42" class="drop-shadow-lg">
        <circle cx="21" cy="21" r="19" fill="rgba(0,0,0,0.65)" stroke="rgba(255,255,255,0.15)" stroke-width="0.5" />
        <text x="21" y="10" text-anchor="middle" fill="#f44336" font-size="9" font-weight="bold" font-family="monospace"
          >N</text
        >
        <text x="21" y="37" text-anchor="middle" fill="#666" font-size="7" font-family="monospace">S</text>
        <text x="5" y="24" text-anchor="middle" fill="#666" font-size="7" font-family="monospace">W</text>
        <text x="37" y="24" text-anchor="middle" fill="#666" font-size="7" font-family="monospace">E</text>
        <g transform="rotate({app.drone.hdg}, 21, 21)" class="compass-needle">
          <polygon points="21,5 18,17 24,17" fill="#4fc3f7" opacity="0.9" />
          <polygon points="21,37 18,25 24,25" fill="#4fc3f7" opacity="0.25" />
        </g>
      </svg>
    </div>
  {/if}
  <button
    class="absolute bottom-1.5 left-2.5 z-[1000] bg-card/85 backdrop-blur text-muted-foreground px-2 py-0.5 rounded text-[11px] font-mono cursor-pointer hover:text-primary transition-colors"
    onclick={() => {
      if (mouseCoord) {
        navigator.clipboard.writeText(mouseCoord);
        addToast(t('toast.coordCopied'), 'success', 1500);
      }
    }}
    title={t('tip.copyCoord')}>{mouseCoord || '---'}</button
  >
  <MapControls />

  {#if showHud && app.drone.connected}
    <HudOverlay />
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
    transition: all 0.15s;
  }
  .map-btn:hover {
    color: hsl(var(--primary));
    border-color: hsl(var(--primary));
  }
  :global(.drone-icon) {
    transition: transform 200ms linear !important;
    background: none !important;
    border: none !important;
  }
  :global(.drone-arrow) {
    transition: transform 150ms ease-out;
  }
  :global(.dark .leaflet-tile-pane) {
    filter: brightness(0.75) contrast(1.1) saturate(0.85);
  }
  :global(.dark .leaflet-control-zoom a) {
    background: hsl(var(--card));
    color: hsl(var(--foreground));
    border-color: hsl(var(--border));
  }
  :global(.guided-pulse) {
    animation: guidedPulse 1.5s ease-in-out infinite;
  }
  @keyframes guidedPulse {
    0%,
    100% {
      opacity: 0.6;
    }
    50% {
      opacity: 1;
    }
  }
  .compass-needle {
    transition: transform 200ms ease-out;
    transform-origin: 21px 21px;
  }
</style>
