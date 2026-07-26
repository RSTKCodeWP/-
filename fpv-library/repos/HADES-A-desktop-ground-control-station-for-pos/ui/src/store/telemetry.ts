import { create } from "zustand";

import { toLngLat, type LngLat } from "../map/geo";

/* Drone telemetry for the map's non-pin layers (impl-plan Task 5.5c). Holds the current
 * pose + heading, the accumulated flight TRACK, the current camera FOOTPRINT polygon, and
 * the accumulated searched-area COVERAGE. The Python service owns the footprint geometry
 * (the georeference SSoT — DESIGN.md §1); the UI just accumulates what it's handed. The
 * track is capped so a multi-hour mission never grows unbounded (16 GB Air target). */

export interface DronePose {
  lat: number;
  lon: number;
  heading_deg: number;
  agl_m: number;
}

const TRACK_CAP = 2000;

interface TelemetryState {
  pose: DronePose | null;
  track: LngLat[]; // [lon,lat] trail (map-edge order)
  footprint: LngLat[] | null; // current camera footprint corners
  coverage: LngLat[][]; // accumulated swept footprints

  pushPose: (pose: DronePose) => void;
  setFootprint: (corners: LngLat[]) => void;
  reset: () => void;
}

export const useTelemetryStore = create<TelemetryState>((set, get) => ({
  pose: null,
  track: [],
  footprint: null,
  coverage: [],

  pushPose: (pose) => {
    const track = [...get().track, toLngLat(pose.lat, pose.lon)];
    if (track.length > TRACK_CAP) track.splice(0, track.length - TRACK_CAP);
    set({ pose, track });
  },

  setFootprint: (corners) => {
    set({ footprint: corners, coverage: [...get().coverage, corners] });
  },

  reset: () => set({ pose: null, track: [], footprint: null, coverage: [] }),
}));
