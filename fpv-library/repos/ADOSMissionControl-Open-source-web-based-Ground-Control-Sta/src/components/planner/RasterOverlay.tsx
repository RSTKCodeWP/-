/**
 * @module RasterOverlay
 * @description Renders a loaded georeferenced raster (orthophoto) as a Leaflet
 * `imageOverlay` on the planner map. Display-only, non-interactive, and drawn
 * beneath the mission vectors so waypoints and paths stay legible on top.
 * Must be rendered inside a react-leaflet MapContainer. Renders nothing until a
 * raster is loaded and visible; toggling visibility off unmounts the overlay,
 * which removes the image from the map.
 * @license GPL-3.0-only
 */
"use client";

import { ImageOverlay } from "react-leaflet";
import { useRasterOverlayStore } from "@/stores/raster-overlay-store";

export function RasterOverlay() {
  const raster = useRasterOverlayStore((s) => s.raster);
  const visible = useRasterOverlayStore((s) => s.visible);

  if (!raster || !visible) return null;

  const [[south, west], [north, east]] = raster.bounds;
  // Key on the resolved corners so loading a new raster cleanly remounts (and so
  // Leaflet drops the previous image) instead of mutating in place.
  const key = `raster-${south.toFixed(6)}-${west.toFixed(6)}-${north.toFixed(6)}-${east.toFixed(6)}`;

  return (
    <ImageOverlay
      key={key}
      url={raster.dataUrl}
      bounds={raster.bounds}
      opacity={1}
      interactive={false}
    />
  );
}
