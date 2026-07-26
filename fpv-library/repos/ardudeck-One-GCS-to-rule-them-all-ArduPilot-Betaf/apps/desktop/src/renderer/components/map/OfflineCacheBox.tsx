/**
 * Adjustable rectangle for selecting a map area to cache offline. Rendered inside the
 * telemetry MapContainer when "Cache map area" mode is active: a dashed box with four
 * corner handles (resize) and a centre handle (move). Drag updates the shared cache-area
 * bounds, which the OfflineCachePanel reads to estimate and download tiles. On activation
 * it auto-fits to ~60% of the current view so there's something to grab.
 */

import { useEffect } from 'react';
import { Rectangle, Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useTileCacheAreaStore } from '../../stores/tile-cache-area-store';

const HANDLE = L.divIcon({
  className: '',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
  html: '<div style="width:14px;height:14px;border-radius:3px;background:#06b6d4;border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.45)"></div>',
});

const MOVE = L.divIcon({
  className: '',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
  html: '<div style="width:24px;height:24px;border-radius:50%;background:rgba(6,182,212,.9);border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.4);display:grid;place-items:center"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18M3 12h18M9 6l3-3 3 3M9 18l3 3 3-3M6 9l-3 3 3 3M18 9l3 3-3 3"/></svg></div>',
});

export function OfflineCacheBox(): JSX.Element | null {
  const active = useTileCacheAreaStore((s) => s.active);
  const bounds = useTileCacheAreaStore((s) => s.bounds);
  const setBounds = useTileCacheAreaStore((s) => s.setBounds);
  const map = useMap();

  useEffect(() => {
    if (active && !bounds) {
      const b = map.getBounds();
      const latPad = (b.getNorth() - b.getSouth()) * 0.2;
      const lngPad = (b.getEast() - b.getWest()) * 0.2;
      setBounds({ north: b.getNorth() - latPad, south: b.getSouth() + latPad, east: b.getEast() - lngPad, west: b.getWest() + lngPad });
    }
  }, [active, bounds, map, setBounds]);

  if (!active || !bounds) return null;
  const { north, south, east, west } = bounds;
  const set = (n: number, s: number, e: number, w: number) =>
    setBounds({ north: Math.max(n, s), south: Math.min(n, s), east: Math.max(e, w), west: Math.min(e, w) });

  const corners: Array<{ k: string; lat: number; lng: number }> = [
    { k: 'nw', lat: north, lng: west },
    { k: 'ne', lat: north, lng: east },
    { k: 'se', lat: south, lng: east },
    { k: 'sw', lat: south, lng: west },
  ];
  const onCorner = (k: string, ll: L.LatLng) => {
    if (k === 'nw') set(ll.lat, south, east, ll.lng);
    else if (k === 'ne') set(ll.lat, south, ll.lng, west);
    else if (k === 'se') set(north, ll.lat, ll.lng, west);
    else set(north, ll.lat, east, ll.lng);
  };

  const c = { lat: (north + south) / 2, lng: (east + west) / 2 };
  const onMove = (ll: L.LatLng) => {
    const dLat = ll.lat - c.lat;
    const dLng = ll.lng - c.lng;
    setBounds({ north: north + dLat, south: south + dLat, east: east + dLng, west: west + dLng });
  };

  return (
    <>
      <Rectangle bounds={[[south, west], [north, east]]} pathOptions={{ color: '#06b6d4', weight: 2, fillColor: '#06b6d4', fillOpacity: 0.08, dashArray: '6 4' }} />
      {corners.map((cn) => (
        <Marker
          key={cn.k}
          position={[cn.lat, cn.lng]}
          icon={HANDLE}
          draggable
          zIndexOffset={6000}
          eventHandlers={{ drag: (e) => onCorner(cn.k, (e.target as L.Marker).getLatLng()) }}
        />
      ))}
      <Marker
        position={[c.lat, c.lng]}
        icon={MOVE}
        draggable
        zIndexOffset={6000}
        eventHandlers={{ drag: (e) => onMove((e.target as L.Marker).getLatLng()) }}
      />
    </>
  );
}
