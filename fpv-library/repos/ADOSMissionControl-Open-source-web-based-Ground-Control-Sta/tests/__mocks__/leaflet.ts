import { vi } from 'vitest';

// A layer-like stub whose `.addTo()` returns itself so call chains such as
// `L.marker(...).addTo(group)` resolve to a usable handle in tests.
const makeLayer = () => {
  const layer = {
    addTo: vi.fn(() => layer),
    setRadius: vi.fn(),
    setLatLng: vi.fn(),
    remove: vi.fn(),
  };
  return layer;
};

// A feature-group stub that records added/removed layers so drawing-tool tests
// can assert cleanup without a real DOM map.
const makeFeatureGroup = () => {
  const group = {
    addTo: vi.fn(() => group),
    addLayer: vi.fn(),
    removeLayer: vi.fn(),
    clearLayers: vi.fn(),
  };
  return group;
};

export default {
  map: vi.fn(),
  tileLayer: vi.fn(),
  featureGroup: vi.fn(() => makeFeatureGroup()),
  marker: vi.fn(() => makeLayer()),
  polyline: vi.fn(() => makeLayer()),
  polygon: vi.fn(() => makeLayer()),
  circle: vi.fn(() => makeLayer()),
  circleMarker: vi.fn(() => makeLayer()),
  latLng: vi.fn((lat: number, lng: number) => ({ lat, lng })),
  latLngBounds: vi.fn(),
  icon: vi.fn(),
  divIcon: vi.fn(),
  DomUtil: { create: vi.fn(), remove: vi.fn() },
  DomEvent: { on: vi.fn(), off: vi.fn(), stop: vi.fn() },
  Util: { extend: vi.fn() },
};
