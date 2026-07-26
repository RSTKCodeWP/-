import { describe, it, expect, beforeAll, beforeEach, vi } from 'vitest';
import { DOMParser as XmldomParser } from '@xmldom/xmldom';
import { useGuideStore } from './guide-store';
import { useSurveyStore } from './survey-store';
import { useSettingsStore } from './settings-store';

// Node test environment: polyfill the renderer globals the store touches -
// window.electronAPI (mocked per test) and DOMParser for the KML parser
// (same pattern as gis-area-import.test.ts).
beforeAll(() => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).window = globalThis;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (globalThis as any).DOMParser = class ThrowingDOMParser {
    parseFromString(content: string, mimeType: string): Document {
      let parseError: Error | null = null;
      const parser = new XmldomParser({
        errorHandler: {
          warning: () => {},
          error: (msg: string) => {
            parseError = new Error(msg);
          },
          fatalError: (msg: string) => {
            parseError = new Error(msg);
          },
        },
      });
      const doc = parser.parseFromString(content, mimeType as 'application/xml');
      if (parseError !== null) throw parseError;
      return doc as unknown as Document;
    }
  };
});

// A KML with one polygon (hole included) and a name, exercising the shared
// parseGisArea path end to end.
const KML = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
<Placemark><name>Test Field</name><Polygon>
<outerBoundaryIs><LinearRing><coordinates>
9.270,54.004,0 9.276,54.004,0 9.276,54.008,0 9.270,54.008,0 9.270,54.004,0
</coordinates></LinearRing></outerBoundaryIs>
<innerBoundaryIs><LinearRing><coordinates>
9.272,54.005,0 9.274,54.005,0 9.274,54.006,0 9.272,54.006,0 9.272,54.005,0
</coordinates></LinearRing></innerBoundaryIs>
</Polygon></Placemark>
</Document></kml>`;

function mockImportDialog(content: string | null) {
  (globalThis as unknown as { electronAPI: unknown }).electronAPI = {
    importSurveyArea: vi.fn().mockResolvedValue(
      content === null
        ? { success: false, error: 'Cancelled' }
        : { success: true, content, format: 'kml' },
    ),
    saveSettings: vi.fn().mockResolvedValue(undefined),
  };
}

beforeEach(() => {
  useGuideStore.setState({ guides: [], focusSeq: 0, focusBounds: null });
  useSettingsStore.setState({ mapGuides: [] });
  useSurveyStore.setState({ polygon: null, isActive: false, editingGroupId: 'stale' });
});

describe('guide-store', () => {
  it('imports polygons as guides with holes, no waypoints generated', async () => {
    mockImportDialog(KML);
    const res = await useGuideStore.getState().importGuides();
    expect(res).toEqual({ ok: true, count: 1 });
    const guides = useGuideStore.getState().guides;
    expect(guides).toHaveLength(1);
    expect(guides[0]!.name).toBe('Guide 1');
    expect(guides[0]!.polygon.length).toBeGreaterThanOrEqual(4);
    expect(guides[0]!.holes).toHaveLength(1);
    expect(guides[0]!.visible).toBe(true);
    // Importing a guide must not touch the survey draft.
    expect(useSurveyStore.getState().polygon).toBeNull();
    // Persisted to settings.
    expect(useSettingsStore.getState().mapGuides).toHaveLength(1);
  });

  it('handles cancel without error noise', async () => {
    mockImportDialog(null);
    const res = await useGuideStore.getState().importGuides();
    expect(res.ok).toBe(false);
    expect(res.error).toBeUndefined();
  });

  it('toggles visibility per guide and for all', async () => {
    mockImportDialog(KML);
    await useGuideStore.getState().importGuides();
    const id = useGuideStore.getState().guides[0]!.id;
    useGuideStore.getState().toggleGuide(id);
    expect(useGuideStore.getState().guides[0]!.visible).toBe(false);
    useGuideStore.getState().setAllVisible(true);
    expect(useGuideStore.getState().guides.every((g) => g.visible)).toBe(true);
  });

  it('removes guides and persists the change', async () => {
    mockImportDialog(KML);
    await useGuideStore.getState().importGuides();
    const id = useGuideStore.getState().guides[0]!.id;
    useGuideStore.getState().removeGuide(id);
    expect(useGuideStore.getState().guides).toHaveLength(0);
    expect(useSettingsStore.getState().mapGuides).toHaveLength(0);
  });

  it('focusGuide bumps the trigger with the guide bounds and unhides it', async () => {
    mockImportDialog(KML);
    await useGuideStore.getState().importGuides();
    const id = useGuideStore.getState().guides[0]!.id;
    useGuideStore.getState().toggleGuide(id);
    expect(useGuideStore.getState().guides[0]!.visible).toBe(false);

    useGuideStore.getState().focusGuide(id);
    const s = useGuideStore.getState();
    expect(s.focusSeq).toBe(1);
    expect(s.guides[0]!.visible).toBe(true);
    const [[minLat, minLng], [maxLat, maxLng]] = s.focusBounds!;
    expect(minLat).toBeCloseTo(54.004, 3);
    expect(maxLat).toBeCloseTo(54.008, 3);
    expect(minLng).toBeCloseTo(9.27, 3);
    expect(maxLng).toBeCloseTo(9.276, 3);
  });

  it('startSurveyFromGuide loads the draft with polygon + holes and opens the panel', async () => {
    mockImportDialog(KML);
    await useGuideStore.getState().importGuides();
    const guide = useGuideStore.getState().guides[0]!;
    useGuideStore.getState().startSurveyFromGuide(guide.id);

    const survey = useSurveyStore.getState();
    expect(survey.isActive).toBe(true);
    expect(survey.editingGroupId).toBeNull();
    expect(survey.polygon).toHaveLength(guide.polygon.length);
    expect(survey.config.holes).toHaveLength(1);
    // The guide itself stays on the map untouched.
    expect(useGuideStore.getState().guides).toHaveLength(1);
  });
});
