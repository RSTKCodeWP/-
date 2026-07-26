/**
 * ImperativeMapLayer - Framework for adding Leaflet elements to the map without
 * React re-render flicker.
 *
 * PROBLEM: Any Leaflet element rendered as React JSX (<Marker>, <Polyline>, <Popup>)
 * inside a component that subscribes to fast-updating stores (telemetry at 2-10Hz)
 * gets destroyed and recreated on every render tick, causing visible flicker.
 *
 * SOLUTION: Manage Leaflet objects imperatively via refs. Create once, update via
 * Leaflet's own API (setLatLng, setLatLngs, setContent, etc.), remove explicitly.
 * React never touches the DOM for these elements.
 *
 * USAGE:
 *   const layer = useImperativeMapLayer();
 *
 *   // Create elements (idempotent - safe to call on every render)
 *   const marker = layer.marker('my-target', [lat, lon], { icon: myIcon });
 *   const line = layer.polyline('my-line', positions, { color: '#22d3ee' });
 *   const popup = layer.popup('my-popup', [lat, lon], htmlContent, popupOptions);
 *
 *   // Update position (cheap - just calls setLatLng on existing Leaflet object)
 *   marker.setLatLng([newLat, newLon]);
 *   line.setLatLngs(newPositions);
 *
 *   // Remove when done
 *   layer.remove('my-target');
 *   layer.removeAll();  // or clear everything
 *
 * Each element is keyed by a string ID. Calling marker/polyline/popup with the same
 * ID returns the existing instance (no DOM teardown). Calling with different options
 * recreates it. This is the "create-once, update-by-ref" pattern.
 */

import L from 'leaflet';
import { useMap } from 'react-leaflet';
import { useRef, useEffect, useCallback, useMemo } from 'react';

type LayerEntry = {
  type: 'marker' | 'polyline' | 'circle' | 'popup';
  instance: L.Marker | L.Polyline | L.Circle | L.Popup;
};

export interface ImperativeMapLayerHandle {
  /** Get or create a marker. Returns existing if same ID, creates new if not. */
  marker(id: string, latlng: L.LatLngExpression, options?: L.MarkerOptions): L.Marker;

  /** Get or create a polyline. Returns existing if same ID, creates new if not. */
  polyline(id: string, latlngs: L.LatLngExpression[], options?: L.PolylineOptions): L.Polyline;

  /** Get or create a circle. Returns existing if same ID, creates new if not. */
  circle(id: string, latlng: L.LatLngExpression, radius: number, options?: L.CircleMarkerOptions): L.Circle;

  /**
   * Open a popup at a position. Returns the L.Popup instance.
   * The popup is created once and updated via setContent/setLatLng - no flicker.
   * Wire interactivity (buttons, inputs) via onReady callback which fires after
   * the popup DOM is in the document.
   */
  popup(
    id: string,
    latlng: L.LatLngExpression,
    html: string,
    options?: L.PopupOptions,
    onReady?: (container: HTMLElement, popup: L.Popup) => void,
    onClose?: () => void,
  ): L.Popup;

  /** Remove a specific element by ID. */
  remove(id: string): void;

  /** Remove all elements managed by this layer. */
  removeAll(): void;

  /** Check if an element exists. */
  has(id: string): boolean;

  /** Get a raw Leaflet element by ID (for advanced updates). */
  get<T extends L.Layer = L.Layer>(id: string): T | undefined;

  /** The underlying Leaflet map instance. */
  map: L.Map;
}

/**
 * Hook that returns an ImperativeMapLayerHandle. All elements are automatically
 * cleaned up on unmount.
 *
 * Must be called inside a react-leaflet <MapContainer> child.
 */
export function useImperativeMapLayer(): ImperativeMapLayerHandle {
  const map = useMap();
  const layersRef = useRef<Map<string, LayerEntry>>(new Map());
  // Track popup onClose handlers for cleanup
  const popupCloseHandlersRef = useRef<Map<string, () => void>>(new Map());

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      const layers = layersRef.current;
      for (const [, entry] of layers) {
        if (map.hasLayer(entry.instance as L.Layer)) {
          map.removeLayer(entry.instance as L.Layer);
        }
      }
      layers.clear();
      popupCloseHandlersRef.current.clear();
    };
  }, [map]);

  const remove = useCallback((id: string) => {
    const entry = layersRef.current.get(id);
    if (!entry) return;
    if (map.hasLayer(entry.instance as L.Layer)) {
      map.removeLayer(entry.instance as L.Layer);
    }
    layersRef.current.delete(id);
    popupCloseHandlersRef.current.delete(id);
  }, [map]);

  const removeAll = useCallback(() => {
    for (const [id] of layersRef.current) {
      remove(id);
    }
  }, [remove]);

  const markerFn = useCallback((
    id: string,
    latlng: L.LatLngExpression,
    options?: L.MarkerOptions,
  ): L.Marker => {
    const existing = layersRef.current.get(id);
    if (existing && existing.type === 'marker') {
      const m = existing.instance as L.Marker;
      m.setLatLng(latlng);
      return m;
    }
    // Remove old if type changed
    if (existing) remove(id);

    const m = L.marker(latlng, options).addTo(map);
    layersRef.current.set(id, { type: 'marker', instance: m });
    return m;
  }, [map, remove]);

  const polylineFn = useCallback((
    id: string,
    latlngs: L.LatLngExpression[],
    options?: L.PolylineOptions,
  ): L.Polyline => {
    const existing = layersRef.current.get(id);
    if (existing && existing.type === 'polyline') {
      const p = existing.instance as L.Polyline;
      p.setLatLngs(latlngs);
      return p;
    }
    if (existing) remove(id);

    const p = L.polyline(latlngs, options).addTo(map);
    layersRef.current.set(id, { type: 'polyline', instance: p });
    return p;
  }, [map, remove]);

  const circleFn = useCallback((
    id: string,
    latlng: L.LatLngExpression,
    radius: number,
    options?: L.CircleMarkerOptions,
  ): L.Circle => {
    const existing = layersRef.current.get(id);
    if (existing && existing.type === 'circle') {
      const c = existing.instance as L.Circle;
      c.setLatLng(latlng as L.LatLngExpression);
      c.setRadius(radius);
      return c;
    }
    if (existing) remove(id);

    const c = L.circle(latlng, { ...options, radius }).addTo(map);
    layersRef.current.set(id, { type: 'circle', instance: c });
    return c;
  }, [map, remove]);

  const popupFn = useCallback((
    id: string,
    latlng: L.LatLngExpression,
    html: string,
    options?: L.PopupOptions,
    onReady?: (container: HTMLElement, popup: L.Popup) => void,
    onClose?: () => void,
  ): L.Popup => {
    // Always recreate popups - content/handlers change between invocations
    const existingEntry = layersRef.current.get(id);
    if (existingEntry) {
      // Detach old close handler before removing
      const oldHandler = popupCloseHandlersRef.current.get(id);
      if (oldHandler) {
        (existingEntry.instance as L.Popup).off('remove', oldHandler);
      }
      remove(id);
    }

    const popup = L.popup({
      closeButton: false,
      maxWidth: 300,
      autoPan: true,
      ...options,
    })
      .setLatLng(latlng)
      .setContent(html)
      .openOn(map);

    layersRef.current.set(id, { type: 'popup', instance: popup });

    // Wire close handler
    if (onClose) {
      const handler = () => {
        layersRef.current.delete(id);
        popupCloseHandlersRef.current.delete(id);
        onClose();
      };
      popupCloseHandlersRef.current.set(id, handler);
      popup.on('remove', handler);
    }

    // Wire interactivity after DOM is ready
    if (onReady) {
      requestAnimationFrame(() => {
        const container = popup.getElement();
        if (container) onReady(container, popup);
      });
    }

    return popup;
  }, [map, remove]);

  const has = useCallback((id: string): boolean => {
    return layersRef.current.has(id);
  }, []);

  const getFn = useCallback(<T extends L.Layer = L.Layer>(id: string): T | undefined => {
    const entry = layersRef.current.get(id);
    return entry ? (entry.instance as unknown as T) : undefined;
  }, []);

  return useMemo(() => ({
    marker: markerFn,
    polyline: polylineFn,
    circle: circleFn,
    popup: popupFn,
    remove,
    removeAll,
    has,
    get: getFn,
    map,
  }), [markerFn, polylineFn, circleFn, popupFn, remove, removeAll, has, getFn, map]);
}
