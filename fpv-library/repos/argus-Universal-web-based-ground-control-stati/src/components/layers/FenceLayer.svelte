<script lang="ts">
  import { onDestroy } from 'svelte';
  import { app } from '../../lib/stores.svelte';

  type CoordFn = (lat: number, lon: number) => [number, number];
  let { map, coord }: { map: L.Map; coord: CoordFn } = $props();

  let polyLayer: L.Polygon | L.Polyline | null = null;
  let vertMarkers: L.CircleMarker[] = [];

  $effect(() => {
    vertMarkers.forEach((m) => map.removeLayer(m));
    vertMarkers = [];
    if (polyLayer) {
      map.removeLayer(polyLayer);
      polyLayer = null;
    }
    if (app.fencePolygon.length === 0) return;
    const uploaded = app.fenceUploaded;
    const gcjPts = app.fencePolygon.map((p) => coord(p.lat, p.lon));
    if (gcjPts.length >= 3) {
      polyLayer = L.polygon(gcjPts, {
        color: '#f44336',
        fillColor: '#f44336',
        fillOpacity: uploaded ? 0.15 : 0.06,
        weight: uploaded ? 2.5 : 2,
        dashArray: uploaded ? undefined : '6,4',
      }).addTo(map);
    } else if (gcjPts.length >= 2) {
      polyLayer = L.polyline(gcjPts, {
        color: '#f44336',
        weight: 2,
        dashArray: uploaded ? undefined : '6,4',
      }).addTo(map);
    }
    gcjPts.forEach((pt, i) => {
      const cm = L.circleMarker(pt, {
        radius: 5,
        color: '#f44336',
        fillColor: i === 0 ? '#fff' : '#f44336',
        fillOpacity: 1,
        weight: 2,
      }).addTo(map);
      vertMarkers.push(cm);
    });
  });

  onDestroy(() => {
    vertMarkers.forEach((m) => map.removeLayer(m));
    if (polyLayer) map.removeLayer(polyLayer);
  });
</script>
