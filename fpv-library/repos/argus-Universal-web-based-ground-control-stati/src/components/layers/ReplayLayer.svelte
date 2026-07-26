<script lang="ts">
  import { onDestroy } from 'svelte';
  import { app } from '../../lib/stores.svelte';

  type CoordFn = (lat: number, lon: number) => [number, number];
  let { map, follow, coord }: { map: L.Map; follow: boolean; coord: CoordFn } = $props();

  let marker: L.Marker | null = null;
  let trail: [number, number][] = [];
  let trailLine: L.Polyline | null = null;

  $effect(() => {
    const rp = app.replayPos;
    if (!rp) {
      if (marker) {
        map.removeLayer(marker);
        marker = null;
      }
      if (trailLine) {
        map.removeLayer(trailLine);
        trailLine = null;
      }
      trail = [];
      return;
    }
    const [glat, glon] = coord(rp.lat, rp.lon);
    if (!marker) {
      const icon = L.divIcon({
        className: '',
        html: `<div class="drone-arrow" style="transform:rotate(${rp.yaw}deg)"><svg viewBox="-12 -12 24 24" width="28" height="28"><polygon points="0,-10 -7,8 0,4 7,8" fill="#ffa726" stroke="white" stroke-width="1"/></svg></div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });
      marker = L.marker([glat, glon], { icon, zIndexOffset: 900 }).addTo(map);
    } else {
      marker.setLatLng([glat, glon]);
      const el = marker.getElement();
      if (el) {
        const a = el.querySelector('.drone-arrow');
        if (a) (a as HTMLElement).style.transform = `rotate(${rp.yaw}deg)`;
      }
    }
    trail.push([glat, glon]);
    if (trail.length > 3000) trail.splice(0, trail.length - 2000);
    if (trailLine) map.removeLayer(trailLine);
    trailLine = L.polyline(trail, { color: '#ffa726', weight: 2, opacity: 0.6 }).addTo(map);
    if (follow) map.setView([glat, glon], map.getZoom());
  });

  onDestroy(() => {
    if (marker) map.removeLayer(marker);
    if (trailLine) map.removeLayer(trailLine);
  });
</script>
