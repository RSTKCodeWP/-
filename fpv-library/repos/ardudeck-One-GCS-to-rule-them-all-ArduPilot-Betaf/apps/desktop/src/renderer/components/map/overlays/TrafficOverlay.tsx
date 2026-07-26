/**
 * TrafficOverlay — renders ADS-B + glider contacts on the Leaflet maps (shared by
 * the telemetry and mission surfaces).
 *
 * Contacts arrive ~1 Hz as full snapshots from the main process. We manage L.Marker
 * instances imperatively (create/update/remove diffed against the snapshot) so there
 * is no React-reconciliation churn, mirroring WindParticleOverlay. Icons rotate to
 * track and recolour by proximity tier against the live own-vehicle position; the
 * two overlay toggles ('traffic' = ADS-B, 'gliders' = OGN) filter by source.
 */

import { useEffect } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import { useTrafficStore, initTrafficStore, reportTrafficViewport } from '../../../stores/traffic-store';
import { useTelemetryStore } from '../../../stores/telemetry-store';
import { useOverlayStore } from '../../../stores/overlay-store';
import type { TrafficContact } from '../../../../shared/traffic-types';
import { classifyProximity, type OwnPosition, type ProximityTier } from '../traffic/proximity';
import { contactColor, glyphSvg, contactLabel, altitudeRelevance, relevanceStyle, isAltitudeRelevant, type AltitudeBand } from '../traffic/contact-style';
import { buildContactPopup } from '../traffic/contact-popup';

const PANE = 'trafficContacts';
const ZONE_PANE = 'trafficZones';

function buildIcon(c: TrafficContact, tier: ProximityTier, rel: number, band: AltitudeBand, iconScale: number, intruding: boolean): L.DivIcon {
  const color = contactColor(c, tier, band);
  const rot = c.trackDeg ?? 0;
  const { scale, opacity } = relevanceStyle(rel);
  const size = Math.round(20 * scale * iconScale);
  const half = size / 2;
  const ringR = half + 5;
  const ring =
    tier !== 'none'
      ? `<div style="position:absolute;left:${-ringR}px;top:${-ringR}px;width:${ringR * 2}px;height:${ringR * 2}px;border-radius:50%;border:2px solid ${color};opacity:.75"></div>`
      : '';
  // A contact inside an alert zone gets a pulsing red halo, regardless of its
  // proximity tier, so a perimeter intrusion is unmistakable.
  const haloR = half + 9;
  const halo = intruding
    ? `<div style="position:absolute;left:${-haloR}px;top:${-haloR}px;width:${haloR * 2}px;height:${haloR * 2}px;border-radius:50%;border:2px dashed #ef4444;opacity:.9"></div>`
    : '';
  const html = `<div style="position:absolute;left:0;top:0;opacity:${opacity.toFixed(2)}">
      ${halo}
      ${ring}
      <div style="position:absolute;left:${-half}px;top:${-half}px;width:${size}px;height:${size}px;transform:rotate(${rot}deg)">
        <svg width="${size}" height="${size}" viewBox="0 0 20 20">${glyphSvg(c.category, color)}</svg>
      </div>
      <div style="position:absolute;left:${half + 3}px;top:-6px;white-space:nowrap;font-size:10px;font-weight:500;color:#e2e8f0;text-shadow:0 0 3px #000,0 0 3px #000">${contactLabel(c)}</div>
    </div>`;
  return L.divIcon({ html, className: 'traffic-contact-icon !bg-transparent !border-0', iconSize: [0, 0] });
}

function ownPosition(): OwnPosition | null {
  const { position } = useTelemetryStore.getState();
  if (!position || (position.lat === 0 && position.lon === 0)) return null;
  return { lat: position.lat, lon: position.lon, altMeters: position.alt };
}

export function TrafficOverlay(): null {
  const map = useMap();
  const contacts = useTrafficStore((s) => s.contacts);
  const proximity = useTrafficStore((s) => s.proximity);
  const altitudeBand = useTrafficStore((s) => s.altitudeBand);
  const iconScale = useTrafficStore((s) => s.iconScale);
  const alertZones = useTrafficStore((s) => s.alertZones);
  const intrudingContactIds = useTrafficStore((s) => s.intrudingContactIds);
  const intrudingZoneIds = useTrafficStore((s) => s.intrudingZoneIds);
  const activeOverlays = useOverlayStore((s) => s.activeOverlays);

  // One-time wiring + a dedicated pane above the marker pane.
  useEffect(() => {
    initTrafficStore();
    if (!map.getPane(PANE)) {
      const p = map.createPane(PANE);
      p.style.zIndex = '610';
    }
  }, [map]);

  // Report viewport (centre + radius) so providers scope their queries.
  useEffect(() => {
    const report = (): void => {
      const c = map.getCenter();
      const ne = map.getBounds().getNorthEast();
      const radiusKm = Math.min(500, map.distance(c, ne) / 1000);
      reportTrafficViewport(c.lat, c.lng, radiusKm);
    };
    report();
    map.on('moveend', report);
    return () => {
      map.off('moveend', report);
    };
  }, [map]);

  // Diff the snapshot into markers.
  useEffect(() => {
    const showAdsb = activeOverlays.has('traffic');
    const showOgn = activeOverlays.has('gliders');
    const showRemoteId = activeOverlays.has('remoteid');
    const band: AltitudeBand = altitudeBand;
    const visible = contacts.filter((c) => {
      const sourceShown = c.source === 'adsb' ? showAdsb : c.source === 'ogn' ? showOgn : showRemoteId;
      // Remote ID drones fly low (often below the operator's altitude floor); the
      // whole point of the layer is catching them, so don't altitude-filter them.
      const altOk = c.source === 'remoteid' ? true : isAltitudeRelevant(c, band);
      return sourceShown && altOk;
    });

    const markers = new Map<string, L.Marker>(
      ((map as unknown as { __trafficMarkers?: Map<string, L.Marker> }).__trafficMarkers ?? new Map()),
    );
    const own = ownPosition();
    const seen = new Set<string>();
    const now = Date.now();

    for (const c of visible) {
      seen.add(c.id);
      const tier = classifyProximity(c, own, proximity)?.tier ?? 'none';
      const rel = altitudeRelevance(c.altMeters, band);
      const icon = buildIcon(c, tier, rel, band, iconScale, intrudingContactIds.has(c.id));
      let m = markers.get(c.id);
      if (!m) {
        m = L.marker([c.lat, c.lon], { icon, pane: PANE, keyboard: false });
        m.addTo(map);
        markers.set(c.id, m);
      } else {
        m.setLatLng([c.lat, c.lon]);
        m.setIcon(icon);
      }
      const prox = classifyProximity(c, own, proximity);
      m.bindPopup(buildContactPopup(c, prox, now, band), { className: 'traffic-popup' });
    }

    for (const [id, m] of markers) {
      if (!seen.has(id)) {
        m.remove();
        markers.delete(id);
      }
    }
    (map as unknown as { __trafficMarkers?: Map<string, L.Marker> }).__trafficMarkers = markers;
  }, [map, contacts, proximity, altitudeBand, iconScale, activeOverlays, intrudingContactIds]);

  // Draw the alert zones (circles + polygons). A zone with a live intruder turns
  // red, otherwise it sits as a muted amber perimeter. Independent of the source
  // toggles - a defined perimeter is always shown.
  useEffect(() => {
    if (!map.getPane(ZONE_PANE)) {
      const p = map.createPane(ZONE_PANE);
      p.style.zIndex = '600';
    }
    const layers = (map as unknown as { __zoneLayers?: Map<string, L.Layer> }).__zoneLayers ?? new Map<string, L.Layer>();
    const seen = new Set<string>();
    for (const z of alertZones) {
      if (!z.enabled) continue;
      seen.add(z.id);
      const hot = intrudingZoneIds.has(z.id);
      const color = hot ? '#ef4444' : '#f59e0b';
      const style = { color, weight: 2, opacity: 0.8, fillColor: color, fillOpacity: 0.08, pane: ZONE_PANE } as L.PathOptions;
      let layer = layers.get(z.id) as (L.Circle | L.Polygon) | undefined;
      if (z.shape === 'circle' && z.center && z.radiusMeters !== undefined) {
        if (layer instanceof L.Circle) {
          layer.setLatLng([z.center.lat, z.center.lon]);
          layer.setRadius(z.radiusMeters);
          layer.setStyle(style);
        } else {
          layer?.remove();
          layer = L.circle([z.center.lat, z.center.lon], { radius: z.radiusMeters, ...style });
          layer.addTo(map);
          layers.set(z.id, layer);
        }
      } else if (z.shape === 'polygon' && z.polygon && z.polygon.length >= 3) {
        const latlngs = z.polygon.map((p) => [p.lat, p.lon] as [number, number]);
        if (layer instanceof L.Polygon) {
          layer.setLatLngs(latlngs);
          layer.setStyle(style);
        } else {
          layer?.remove();
          layer = L.polygon(latlngs, style);
          layer.addTo(map);
          layers.set(z.id, layer);
        }
      } else {
        layer?.remove();
        layers.delete(z.id);
        seen.delete(z.id);
      }
      if (layer) layer.bindTooltip(z.name, { sticky: true });
    }
    for (const [id, layer] of layers) {
      if (!seen.has(id)) {
        layer.remove();
        layers.delete(id);
      }
    }
    (map as unknown as { __zoneLayers?: Map<string, L.Layer> }).__zoneLayers = layers;
  }, [map, alertZones, intrudingZoneIds]);

  // Clear all markers on unmount.
  useEffect(() => {
    return () => {
      const store = (map as unknown as { __trafficMarkers?: Map<string, L.Marker> }).__trafficMarkers;
      if (store) {
        for (const m of store.values()) m.remove();
        store.clear();
      }
      const zones = (map as unknown as { __zoneLayers?: Map<string, L.Layer> }).__zoneLayers;
      if (zones) {
        for (const l of zones.values()) l.remove();
        zones.clear();
      }
    };
  }, [map]);

  return null;
}
