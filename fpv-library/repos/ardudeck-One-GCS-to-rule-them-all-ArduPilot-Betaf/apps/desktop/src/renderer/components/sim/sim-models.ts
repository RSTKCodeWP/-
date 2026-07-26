/**
 * Maps an ArduPilot vehicle class to the 3D model the sim world renders for it.
 *
 * Kept separate from sim-world-scene.ts (which owns the asset URLs + three.js
 * loading) so the mapping is pure and unit-testable. The quad is the fallback:
 * any class without a dedicated model renders as the quad.
 */

export type ModelKey = 'quad' | 'plane' | 'hexa' | 'rover';

/** Rendered when a class has no dedicated model yet. */
export const FALLBACK_MODEL: ModelKey = 'quad';

/**
 * Vehicle class → model. Classes absent here fall back to the quad. `vtol` and
 * `sub` have no dedicated model yet, so they render as the quad. (Map
 * `copter → 'hexa'` etc. once we distinguish frame class / motor count beyond
 * the coarse vehicle class.)
 */
export const CLASS_MODEL: Partial<Record<string, ModelKey>> = {
  plane: 'plane',
  rover: 'rover',
};

export function modelKeyForClass(vehicleClass: string | undefined): ModelKey {
  return (vehicleClass && CLASS_MODEL[vehicleClass]) || FALLBACK_MODEL;
}
