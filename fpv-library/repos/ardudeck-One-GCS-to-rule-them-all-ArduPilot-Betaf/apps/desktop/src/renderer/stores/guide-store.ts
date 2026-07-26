/**
 * Boundary guides: imported polygons shown on the mission map as reference
 * outlines. Unlike the survey import flow, importing a guide generates
 * NOTHING - the user later starts a survey from a guide on demand, with
 * whichever generator (built-in pattern or module engine) is selected in the
 * survey panel.
 *
 * Guides persist across sessions via the settings store, independent of
 * mission files - they are geography, not mission content.
 */
import { create } from 'zustand';
import type { LatLng } from '../components/survey/survey-types';
import { parseGisArea } from '../../shared/gis-area-import';
import { simplifyPolygon } from '../components/survey/geo-math';
import { GROUP_COLOR_PALETTE } from '../../shared/mission-group-types';
import { useSettingsStore } from './settings-store';
import { useSurveyStore } from './survey-store';

export interface MapGuide {
  id: string;
  name: string;
  polygon: LatLng[];
  holes: LatLng[][];
  visible: boolean;
  color: string;
}

interface GuideStore {
  guides: MapGuide[];
  /** Monotonic trigger + bounds for "focus the map on this guide" requests. */
  focusSeq: number;
  focusBounds: [[number, number], [number, number]] | null;

  /**
   * Import guides from a GIS file (KML/KMZ/GeoJSON/SHP) via the main-process
   * file dialog. One guide per polygon, holes preserved, no generation.
   */
  importGuides: () => Promise<{ ok: boolean; count: number; error?: string }>;
  toggleGuide: (id: string) => void;
  setAllVisible: (visible: boolean) => void;
  removeGuide: (id: string) => void;
  clearGuides: () => void;
  /** Pan/zoom the mission map to a guide (and unhide it if hidden). */
  focusGuide: (id: string) => void;
  /**
   * Load a guide into the survey draft (polygon + holes) and open the survey
   * panel. Generation then runs through the normal flow, so the currently
   * selected engine (grid, TOPAS, ...) applies and Insert commits as usual.
   * The guide itself stays untouched on the map.
   */
  startSurveyFromGuide: (id: string) => void;
}

function uuid(): string {
  return typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function persist(guides: MapGuide[]): void {
  useSettingsStore.getState().setMapGuides(guides as unknown as Record<string, unknown>[]);
}

export const useGuideStore = create<GuideStore>((set, get) => ({
  guides: [],
  focusSeq: 0,
  focusBounds: null,

  importGuides: async () => {
    const api = window.electronAPI;
    if (!api?.importSurveyArea) return { ok: false, count: 0, error: 'Import not available' };
    const res = await api.importSurveyArea();
    if (!res.success) {
      return { ok: false, count: 0, error: res.error === 'Cancelled' ? undefined : res.error };
    }
    if (!res.content || !res.format) return { ok: false, count: 0, error: 'Empty file' };
    const areas = parseGisArea(res.content, res.format);
    if (areas.length === 0) {
      return { ok: false, count: 0, error: 'No polygon boundary found in the file' };
    }

    // Same vertex thinning as the survey import: GIS boundaries are digitized
    // at sub-meter detail that a guide outline doesn't need.
    const toleranceM = useSettingsStore.getState().surveyPerformance.importSimplifyToleranceM;
    const base = get().guides.length;
    const added: MapGuide[] = areas.map((area, i) => ({
      id: uuid(),
      name: `Guide ${base + i + 1}`,
      polygon: simplifyPolygon(
        area.polygon.map((p) => ({ lat: p.lat, lng: p.lng })),
        toleranceM,
      ),
      holes: area.holes.map((ring) =>
        simplifyPolygon(ring.map((p) => ({ lat: p.lat, lng: p.lng })), toleranceM),
      ),
      visible: true,
      color: GROUP_COLOR_PALETTE[(base + i) % GROUP_COLOR_PALETTE.length]!,
    }));

    const guides = [...get().guides, ...added];
    set({ guides });
    persist(guides);
    return { ok: true, count: added.length };
  },

  toggleGuide: (id) => {
    const guides = get().guides.map((g) => (g.id === id ? { ...g, visible: !g.visible } : g));
    set({ guides });
    persist(guides);
  },

  setAllVisible: (visible) => {
    const guides = get().guides.map((g) => ({ ...g, visible }));
    set({ guides });
    persist(guides);
  },

  removeGuide: (id) => {
    const guides = get().guides.filter((g) => g.id !== id);
    set({ guides });
    persist(guides);
  },

  clearGuides: () => {
    set({ guides: [] });
    persist([]);
  },

  focusGuide: (id) => {
    const guide = get().guides.find((g) => g.id === id);
    if (!guide || guide.polygon.length === 0) return;
    const lats = guide.polygon.map((p) => p.lat);
    const lngs = guide.polygon.map((p) => p.lng);
    // Focusing a hidden guide would pan to seemingly nothing - unhide it.
    if (!guide.visible) {
      const guides = get().guides.map((g) => (g.id === id ? { ...g, visible: true } : g));
      set({ guides });
      persist(guides);
    }
    set((s) => ({
      focusSeq: s.focusSeq + 1,
      focusBounds: [
        [Math.min(...lats), Math.min(...lngs)],
        [Math.max(...lats), Math.max(...lngs)],
      ],
    }));
  },

  startSurveyFromGuide: (id) => {
    const guide = get().guides.find((g) => g.id === id);
    if (!guide) return;
    useSurveyStore.getState().loadDraftFromPolygon(guide.polygon, guide.holes);
  },
}));

// Hydration mirrors survey-store: apply persisted guides once settings load,
// and immediately if they already have (late import / HMR).
function hydrate(): void {
  const raw = useSettingsStore.getState().mapGuides;
  if (Array.isArray(raw) && raw.length > 0) {
    useGuideStore.setState({ guides: raw as unknown as MapGuide[] });
  }
}

useSettingsStore.subscribe(
  (state) => state._isInitialized,
  (init, prev) => {
    if (init && !prev) hydrate();
  },
);

if (useSettingsStore.getState()._isInitialized) hydrate();
