/**
 * Boundary guides on the mission map: imported polygons rendered as dashed
 * reference outlines. Clicking one opens a small popup to start a survey
 * from it (loads the survey draft; nothing is committed) or hide it. The
 * survey itself then uses whichever engine the panel has selected.
 */
import { useEffect, useRef } from 'react';
import { Polygon, Popup, useMap } from 'react-leaflet';
import { useGuideStore } from '../../stores/guide-store';

// Pans/zooms to a guide when the store's focus trigger bumps (same
// trigger-counter pattern as the mission FitToBounds handler).
function GuideFocusHandler() {
  const map = useMap();
  const focusSeq = useGuideStore((s) => s.focusSeq);
  const focusBounds = useGuideStore((s) => s.focusBounds);
  const lastSeqRef = useRef(0);

  useEffect(() => {
    if (focusSeq === lastSeqRef.current || !focusBounds) return;
    lastSeqRef.current = focusSeq;
    map.fitBounds(focusBounds, { padding: [60, 60], maxZoom: 17 });
  }, [focusSeq, focusBounds, map]);

  return null;
}

export function GuidesOverlay() {
  const guides = useGuideStore((s) => s.guides);
  const toggleGuide = useGuideStore((s) => s.toggleGuide);
  const startSurveyFromGuide = useGuideStore((s) => s.startSurveyFromGuide);

  const visible = guides.filter((g) => g.visible && g.polygon.length >= 3);

  return (
    <>
      <GuideFocusHandler />
      {visible.map((g) => {
        const positions = [
          g.polygon.map((p) => [p.lat, p.lng] as [number, number]),
          ...g.holes
            .filter((h) => h.length >= 3)
            .map((h) => h.map((p) => [p.lat, p.lng] as [number, number])),
        ];
        return (
          <Polygon
            key={g.id}
            positions={positions}
            pathOptions={{
              color: g.color,
              weight: 2,
              dashArray: '6, 8',
              opacity: 0.8,
              fillColor: g.color,
              fillOpacity: 0.04,
            }}
          >
            <Popup>
              <div className="space-y-1.5 min-w-[10rem]">
                <div className="text-xs font-medium">{g.name}</div>
                <button
                  onClick={() => startSurveyFromGuide(g.id)}
                  className="w-full px-2 py-1 rounded text-xs font-medium bg-purple-600 hover:bg-purple-500 text-white transition-colors"
                >
                  Plan survey here
                </button>
                <button
                  onClick={() => toggleGuide(g.id)}
                  className="w-full px-2 py-1 rounded text-xs bg-gray-200 hover:bg-gray-300 text-gray-700 transition-colors"
                >
                  Hide guide
                </button>
              </div>
            </Popup>
          </Polygon>
        );
      })}
    </>
  );
}
