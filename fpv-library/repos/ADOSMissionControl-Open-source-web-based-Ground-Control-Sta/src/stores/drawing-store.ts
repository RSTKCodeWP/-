/**
 * @module drawing-store
 * @description Zustand store for map drawing state (polygon, circle, measure tools).
 * Stores completed shapes and in-progress drawing state.
 * @license GPL-3.0-only
 */

import { create } from "zustand";
import type { DrawingMode, DrawnPolygon, DrawnCircle, MeasureLine } from "@/lib/drawing/types";

/**
 * Immutable snapshot of the completed drawn content for the coordinated planner
 * undo timeline. The transient in-progress drawing state (`drawingMode`,
 * `activeDrawingVertices`) is intentionally excluded — those are driven by the
 * live draw gesture and the planner-mode machine, not by operator-completed
 * edits, so undo must not roll a half-drawn shape back and forth.
 */
export interface DrawingSnapshot {
  polygons: DrawnPolygon[];
  circles: DrawnCircle[];
  measureLine: MeasureLine | null;
  selectedPolygonIds: string[];
}

interface DrawingStoreState {
  /** Current drawing mode, or null when idle. */
  drawingMode: DrawingMode;
  /** Completed polygons. */
  polygons: DrawnPolygon[];
  /** Completed circles. */
  circles: DrawnCircle[];
  /** Active measure line result, or null. */
  measureLine: MeasureLine | null;
  /** In-progress polygon vertices (for live preview in other components). */
  activeDrawingVertices: [number, number][];
  /** IDs of polygons selected for multi-polygon operations. */
  selectedPolygonIds: string[];

  setDrawingMode: (mode: DrawingMode) => void;
  addPolygon: (polygon: DrawnPolygon) => void;
  addCircle: (circle: DrawnCircle) => void;
  removePolygon: (id: string) => void;
  removeCircle: (id: string) => void;
  setMeasureLine: (line: MeasureLine | null) => void;
  setActiveDrawingVertices: (vertices: [number, number][]) => void;
  togglePolygonSelection: (id: string) => void;
  selectAllPolygons: () => void;
  deselectAllPolygons: () => void;
  clearAll: () => void;

  /** Capture the completed drawn content for the coordinated undo timeline. */
  snapshot: () => DrawingSnapshot;
  /** Restore previously captured drawn content (from undo / redo). */
  restore: (snap: DrawingSnapshot) => void;
}

export const useDrawingStore = create<DrawingStoreState>()((set, get) => ({
  drawingMode: null,
  polygons: [],
  circles: [],
  measureLine: null,
  activeDrawingVertices: [],
  selectedPolygonIds: [],

  setDrawingMode: (drawingMode) => set({ drawingMode }),

  addPolygon: (polygon) =>
    set((s) => ({
      polygons: [...s.polygons, polygon],
      selectedPolygonIds: [...s.selectedPolygonIds, polygon.id],
    })),

  addCircle: (circle) =>
    set((s) => ({ circles: [...s.circles, circle] })),

  removePolygon: (id) =>
    set((s) => ({
      polygons: s.polygons.filter((p) => p.id !== id),
      selectedPolygonIds: s.selectedPolygonIds.filter((sid) => sid !== id),
    })),

  removeCircle: (id) =>
    set((s) => ({ circles: s.circles.filter((c) => c.id !== id) })),

  setMeasureLine: (measureLine) => set({ measureLine }),

  setActiveDrawingVertices: (activeDrawingVertices) =>
    set({ activeDrawingVertices }),

  togglePolygonSelection: (id) =>
    set((s) => ({
      selectedPolygonIds: s.selectedPolygonIds.includes(id)
        ? s.selectedPolygonIds.filter((sid) => sid !== id)
        : [...s.selectedPolygonIds, id],
    })),

  selectAllPolygons: () =>
    set((s) => ({ selectedPolygonIds: s.polygons.map((p) => p.id) })),

  deselectAllPolygons: () =>
    set({ selectedPolygonIds: [] }),

  clearAll: () =>
    set({
      drawingMode: null,
      polygons: [],
      circles: [],
      measureLine: null,
      activeDrawingVertices: [],
      selectedPolygonIds: [],
    }),

  snapshot: () => {
    const s = get();
    return {
      polygons: s.polygons.map((p) => ({
        ...p,
        vertices: p.vertices.map(([lat, lon]) => [lat, lon] as [number, number]),
      })),
      circles: s.circles.map((c) => ({
        ...c,
        center: [c.center[0], c.center[1]] as [number, number],
      })),
      measureLine: s.measureLine
        ? {
            points: s.measureLine.points.map(([lat, lon]) => [lat, lon] as [number, number]),
            totalDistance: s.measureLine.totalDistance,
            segmentDistances: [...s.measureLine.segmentDistances],
          }
        : null,
      selectedPolygonIds: [...s.selectedPolygonIds],
    };
  },

  restore: (snap) =>
    set({
      polygons: snap.polygons.map((p) => ({
        ...p,
        vertices: p.vertices.map(([lat, lon]) => [lat, lon] as [number, number]),
      })),
      circles: snap.circles.map((c) => ({
        ...c,
        center: [c.center[0], c.center[1]] as [number, number],
      })),
      measureLine: snap.measureLine
        ? {
            points: snap.measureLine.points.map(([lat, lon]) => [lat, lon] as [number, number]),
            totalDistance: snap.measureLine.totalDistance,
            segmentDistances: [...snap.measureLine.segmentDistances],
          }
        : null,
      selectedPolygonIds: [...snap.selectedPolygonIds],
    }),
}));
