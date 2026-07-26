<script lang="ts">
  import { onDestroy } from 'svelte';
  import { app } from '../../lib/stores.svelte';

  type CoordFn = (lat: number, lon: number) => [number, number];
  let {
    map,
    target = $bindable(null),
    coord,
  }: { map: L.Map; target: { lat: number; lon: number; alt: number } | null; coord: CoordFn } = $props();

  let guidedMarker: L.CircleMarker | null = null;
  let guidedLine: L.Polyline | null = null;
  let guidedLabel: L.Marker | null = null;

  $effect(() => {
    if (guidedMarker) {
      map.removeLayer(guidedMarker);
      guidedMarker = null;
    }
    if (guidedLine) {
      map.removeLayer(guidedLine);
      guidedLine = null;
    }
    if (guidedLabel) {
      map.removeLayer(guidedLabel);
      guidedLabel = null;
    }
    if (!target || !app.drone.connected || !app.drone.armed) {
      target = null;
      return;
    }
    const dlat = (target.lat - app.drone.lat) * 111320;
    const dlon = (target.lon - app.drone.lon) * 111320 * Math.cos((app.drone.lat * Math.PI) / 180);
    const dist = Math.sqrt(dlat * dlat + dlon * dlon);
    if (dist < 5) {
      target = null;
      return;
    }
    const [glat, glon] = coord(target.lat, target.lon);
    guidedMarker = L.circleMarker([glat, glon], {
      radius: 12,
      color: '#ffa726',
      fillColor: '#ffa726',
      fillOpacity: 0.2,
      weight: 2.5,
      dashArray: '6,4',
      className: 'guided-pulse',
    }).addTo(map);
    const [dglat, dglon] = coord(app.drone.lat, app.drone.lon);
    guidedLine = L.polyline(
      [
        [dglat, dglon],
        [glat, glon],
      ],
      {
        color: '#ffa726',
        weight: 2,
        opacity: 0.6,
        dashArray: '6,6',
      },
    ).addTo(map);
    const mid = L.latLng((dglat + glat) / 2, (dglon + glon) / 2);
    const txt = dist < 1000 ? `${dist.toFixed(0)}m` : `${(dist / 1000).toFixed(1)}km`;
    guidedLabel = L.marker(mid, {
      icon: L.divIcon({
        className: '',
        html: `<div style="background:rgba(255,167,38,0.9);color:white;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:600;white-space:nowrap">${txt} · ${target.alt}m</div>`,
        iconAnchor: [0, 0],
      }),
      interactive: false,
    }).addTo(map);
  });

  onDestroy(() => {
    [guidedMarker, guidedLine, guidedLabel].filter(Boolean).forEach((l) => map.removeLayer(l!));
  });
</script>
