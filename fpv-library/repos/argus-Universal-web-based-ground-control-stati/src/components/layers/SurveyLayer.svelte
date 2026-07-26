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
    if (app.surveyPolygon.length === 0) return;
    const gcjPts = app.surveyPolygon.map((p) => coord(p.lat, p.lon));
    if (gcjPts.length >= 3) {
      polyLayer = L.polygon(gcjPts, {
        color: '#ab47bc',
        fillColor: '#ab47bc',
        fillOpacity: 0.12,
        weight: 2,
        dashArray: '6,4',
      }).addTo(map);
    } else if (gcjPts.length >= 2) {
      polyLayer = L.polyline(gcjPts, { color: '#ab47bc', weight: 2, dashArray: '6,4' }).addTo(map);
    }
    gcjPts.forEach((pt, i) => {
      const cm = L.circleMarker(pt, {
        radius: 5,
        color: '#ab47bc',
        fillColor: i === 0 ? '#fff' : '#ab47bc',
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
