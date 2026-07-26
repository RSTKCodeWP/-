/**
 * @module EditableGeofenceOverlay
 * @description Interactive geofence overlay with draggable polygon vertices
 * and adjustable circle fence (draggable center + edge radius handle).
 * Syncs changes back to the geofence-store.
 * @license GPL-3.0-only
 */

"use client";

import { useEffect, useRef, useCallback } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import { useGeofenceStore } from "@/stores/geofence-store";

const FENCE_COLOR = "#f59e0b";
const FENCE_ACTIVE_COLOR = "#3A82FF";
const HANDLE_RADIUS = 7;

function makeVertexIcon(active = false): L.DivIcon {
  const color = active ? FENCE_ACTIVE_COLOR : FENCE_COLOR;
  return L.divIcon({
    className: "",
    iconSize: [14, 14],
    iconAnchor: [7, 7],
    html: `<div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid #fff;cursor:grab"></div>`,
  });
}

function makeRadiusIcon(): L.DivIcon {
  return L.divIcon({
    className: "",
    iconSize: [12, 12],
    iconAnchor: [6, 6],
    html: `<div style="width:12px;height:12px;border-radius:50%;background:${FENCE_COLOR};border:2px solid #fff;cursor:ew-resize;opacity:0.9"></div>`,
  });
}

export function EditableGeofenceOverlay() {
  const map = useMap();
  const layerGroupRef = useRef<L.LayerGroup | null>(null);
  const markersRef = useRef<L.Marker[]>([]);

  const enabled = useGeofenceStore((s) => s.enabled);
  const fenceType = useGeofenceStore((s) => s.fenceType);
  const polygonPoints = useGeofenceStore((s) => s.polygonPoints);
  const circleCenter = useGeofenceStore((s) => s.circleCenter);
  const circleRadius = useGeofenceStore((s) => s.circleRadius);
  const setPolygonPoints = useGeofenceStore((s) => s.setPolygonPoints);
  const setCircle = useGeofenceStore((s) => s.setCircle);

  const cleanup = useCallback(() => {
    if (layerGroupRef.current) {
      layerGroupRef.current.clearLayers();
      map.removeLayer(layerGroupRef.current);
      layerGroupRef.current = null;
    }
    markersRef.current = [];
  }, [map]);

  useEffect(() => {
    if (!enabled) {
      cleanup();
      return;
    }

    cleanup();
    const group = L.layerGroup().addTo(map);
    layerGroupRef.current = group;

    if (fenceType === "polygon" && polygonPoints.length >= 3) {
      // Draw polygon outline
      const polygon = L.polygon(polygonPoints, {
        color: FENCE_COLOR,
        weight: 2,
        dashArray: "8 4",
        fillColor: FENCE_COLOR,
        fillOpacity: 0.04,
        interactive: false,
      });
      group.addLayer(polygon);

      // Draggable vertex markers
      const markers: L.Marker[] = polygonPoints.map((point, idx) => {
        const marker = L.marker(point, {
          icon: makeVertexIcon(),
          draggable: true,
          zIndexOffset: 1000,
        });

        marker.on("dragstart", () => {
          marker.setIcon(makeVertexIcon(true));
        });

        marker.on("drag", () => {
          // Update polygon shape in real-time
          const newPoints = markersRef.current.map((m) => {
            const ll = m.getLatLng();
            return [ll.lat, ll.lng] as [number, number];
          });
          polygon.setLatLngs(newPoints);
        });

        marker.on("dragend", () => {
          marker.setIcon(makeVertexIcon(false));
          const newPoints = markersRef.current.map((m) => {
            const ll = m.getLatLng();
            return [ll.lat, ll.lng] as [number, number];
          });
          setPolygonPoints(newPoints);
        });

        group.addLayer(marker);
        return marker;
      });
      markersRef.current = markers;

    } else if (fenceType === "circle" && circleCenter) {
      // Draw circle fence
      const circle = L.circle(circleCenter, {
        radius: circleRadius,
        color: FENCE_COLOR,
        weight: 2,
        dashArray: "8 4",
        fillColor: FENCE_COLOR,
        fillOpacity: 0.04,
        interactive: false,
      });
      group.addLayer(circle);

      // Draggable center marker
      const centerMarker = L.marker(circleCenter, {
        icon: makeVertexIcon(),
        draggable: true,
        zIndexOffset: 1000,
      });

      // Radius handle — placed at 90 degrees (east) of center
      const radiusLat = circleCenter[0];
      const radiusLon = circleCenter[1] + circleRadius / (111320 * Math.cos((circleCenter[0] * Math.PI) / 180));
      const radiusMarker = L.marker([radiusLat, radiusLon], {
        icon: makeRadiusIcon(),
        draggable: true,
        zIndexOffset: 1001,
      });

      centerMarker.on("drag", () => {
        const ll = centerMarker.getLatLng();
        const newCenter: [number, number] = [ll.lat, ll.lng];
        circle.setLatLng(ll);
        // Move radius handle relative to new center
        const rLon = ll.lng + circleRadius / (111320 * Math.cos((ll.lat * Math.PI) / 180));
        radiusMarker.setLatLng([ll.lat, rLon]);
      });

      centerMarker.on("dragend", () => {
        const ll = centerMarker.getLatLng();
        setCircle([ll.lat, ll.lng], circle.getRadius());
      });

      radiusMarker.on("drag", () => {
        const centerLL = centerMarker.getLatLng();
        const handleLL = radiusMarker.getLatLng();
        const newRadius = centerLL.distanceTo(handleLL);
        circle.setRadius(newRadius);
      });

      radiusMarker.on("dragend", () => {
        const centerLL = centerMarker.getLatLng();
        const handleLL = radiusMarker.getLatLng();
        const newRadius = centerLL.distanceTo(handleLL);
        setCircle([centerLL.lat, centerLL.lng], newRadius);
      });

      group.addLayer(centerMarker);
      group.addLayer(radiusMarker);
      markersRef.current = [centerMarker, radiusMarker];
    }

    return cleanup;
  }, [map, enabled, fenceType, polygonPoints, circleCenter, circleRadius, setPolygonPoints, setCircle, cleanup]);

  return null;
}
