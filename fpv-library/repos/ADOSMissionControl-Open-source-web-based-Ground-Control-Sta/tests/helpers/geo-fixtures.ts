/** Known reference polygons and points for testing geodetic functions. */

/** Bangalore city center area (~1km^2 rectangle) */
export const BANGALORE_POLYGON: [number, number][] = [
  [12.9700, 77.5900],
  [12.9700, 77.6000],
  [12.9800, 77.6000],
  [12.9800, 77.5900],
];

/** Point inside Bangalore polygon */
export const BANGALORE_CENTER: [number, number] = [12.9750, 77.5950];

/** Point outside Bangalore polygon */
export const BANGALORE_OUTSIDE: [number, number] = [12.9600, 77.5800];

/** Equator crossing polygon for edge-case testing */
export const EQUATOR_POLYGON: [number, number][] = [
  [-0.01, 36.80],
  [-0.01, 36.82],
  [0.01, 36.82],
  [0.01, 36.80],
];

/** Known haversine distance reference: Bangalore to Chennai (~290 km) */
export const BANGALORE: [number, number] = [12.9716, 77.5946];
export const CHENNAI: [number, number] = [13.0827, 80.2707];
export const BANGALORE_CHENNAI_DISTANCE = 290_000; // ~290 km

/** Self-intersecting polygon (bowtie shape) */
export const BOWTIE_POLYGON: [number, number][] = [
  [0, 0],
  [0, 1],
  [1, 0],
  [1, 1],
];

/** Concave polygon (L-shape) */
export const CONCAVE_L: [number, number][] = [
  [0, 0],
  [0, 2],
  [1, 2],
  [1, 1],
  [2, 1],
  [2, 0],
];
