import { MapView } from "../components/MapView";

/* MAP — Map / Playback (DESIGN-SYSTEM §11.2). The map gets a full-bleed analytical mode: the
 * whole survivor map, coverage layers, and (Stage 4) a timeline scrub/replay + measure tool.
 * Reuses the same MapView component + offline basemap as OPS, so the same pins/rings/coverage
 * and the selection spine carry over. Stage 3 lands the mode; Stage 4 adds the playback/measure
 * controls with the iterate-against-render loop. */

export function MapPage() {
  return (
    <div data-testid="page-map" className="relative h-full">
      <MapView />
    </div>
  );
}
