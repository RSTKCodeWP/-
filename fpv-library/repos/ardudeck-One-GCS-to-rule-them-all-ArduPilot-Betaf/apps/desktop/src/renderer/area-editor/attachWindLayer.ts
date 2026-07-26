/**
 * attachWindLayer — animated wind particles on the Area Editor's MapLibre map.
 *
 * Reuses the shared Canvas2D WindAnimator (map-agnostic via WindProjector) and
 * the shared wind-store for data. A transparent canvas sits over the GL canvas;
 * because maplibre's project() is live, particles track pan/zoom every frame
 * with no special handling. Enabled/disabled by the editor's layers store.
 */

import type maplibregl from 'maplibre-gl';
import { useWindStore } from '../stores/wind-store';
import { useAreaEditorLayersStore } from './area-editor-layers-store';
import { WindAnimator, type WindProjector, type FrameRef } from '../components/map/wind/wind-animator';
import type { WindBBox } from '../../shared/wind-types';

export function attachWindLayer(map: maplibregl.Map): () => void {
  const container = map.getCanvasContainer();
  const canvas = document.createElement('canvas');
  canvas.style.cssText = 'position:absolute;top:0;left:0;pointer-events:none;z-index:2;';
  container.appendChild(canvas);

  const viewBounds = (): WindBBox => {
    const b = map.getBounds();
    return { south: b.getSouth(), north: b.getNorth(), west: b.getWest(), east: b.getEast() };
  };

  const projector: WindProjector = {
    project: (lat, lng) => {
      const p = map.project([lng, lat]);
      return { x: p.x, y: p.y };
    },
    getZoom: () => map.getZoom(),
    getViewBounds: viewBounds,
  };

  const getFrame = (): FrameRef | null => {
    const { field, frameIndex } = useWindStore.getState();
    if (!field) return null;
    const frame = field.frames[frameIndex];
    return frame ? { field, frame } : null;
  };

  const animator = new WindAnimator(canvas, projector, getFrame, () => useWindStore.getState().speedScale);

  const resize = (): void => {
    const c = map.getCanvas();
    animator.resize(c.clientWidth, c.clientHeight);
  };
  resize();

  let running = false;
  let fetchTimer: number | null = null;

  const scheduleFetch = (): void => {
    if (!useAreaEditorLayersStore.getState().overlays.wind) return;
    if (fetchTimer !== null) window.clearTimeout(fetchTimer);
    fetchTimer = window.setTimeout(() => {
      void useWindStore.getState().fetchForBounds(viewBounds());
    }, 700);
  };

  const applyEnabled = (on: boolean): void => {
    if (on && !running) {
      running = true;
      resize();
      animator.start();
      void useWindStore.getState().fetchForBounds(viewBounds());
    } else if (!on && running) {
      running = false;
      animator.stop();
      animator.clear();
    }
  };

  const onMoveEnd = (): void => scheduleFetch();
  map.on('resize', resize);
  map.on('moveend', onMoveEnd);

  const unsub = useAreaEditorLayersStore.subscribe((s) => s.overlays.wind, applyEnabled);
  applyEnabled(useAreaEditorLayersStore.getState().overlays.wind);

  return () => {
    if (fetchTimer !== null) window.clearTimeout(fetchTimer);
    unsub();
    map.off('resize', resize);
    map.off('moveend', onMoveEnd);
    animator.stop();
    canvas.remove();
  };
}
