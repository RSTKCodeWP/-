/**
 * Garmin-SVT terrain coloring — a saturated topographic palette
 * (water → lowland green → olive → tan → brown → gray peaks), intentionally
 * more saturated than real terrain for cockpit readability.
 *
 * Ported 1:1 from the ardudeck-mobile SVT package (terrain_colors.dart) so the
 * desktop synthetic view matches the mobile one. Returns 0..1 RGB floats
 * (three.js vertex-color convention).
 */

export function svtTerrainColor(alt: number): [number, number, number] {
  if (alt < 2) {
    // Water — dark blue
    return [0.08, 0.12, 0.28];
  } else if (alt < 50) {
    // Coastal — dark green
    const t = (alt - 2) / 48;
    return [0.1 + t * 0.1, 0.3 + t * 0.15, 0.08 + t * 0.04];
  } else if (alt < 200) {
    // Lowland — saturated green
    const t = (alt - 50) / 150;
    return [0.2 + t * 0.15, 0.45 + t * 0.1, 0.12];
  } else if (alt < 500) {
    // Hills — olive / yellow-green
    const t = (alt - 200) / 300;
    return [0.35 + t * 0.25, 0.55 - t * 0.05, 0.12 - t * 0.02];
  } else if (alt < 800) {
    // Mid mountain — tan / khaki (Garmin signature)
    const t = (alt - 500) / 300;
    return [0.6 + t * 0.1, 0.5 - t * 0.08, 0.1 + t * 0.05];
  } else if (alt < 1200) {
    // High mountain — warm brown
    const t = (alt - 800) / 400;
    return [0.7 - t * 0.1, 0.42 - t * 0.08, 0.15 + t * 0.05];
  } else if (alt < 1600) {
    // Very high — darker brown
    const t = (alt - 1200) / 400;
    return [0.55 - t * 0.08, 0.32 - t * 0.02, 0.2 + t * 0.05];
  } else {
    // Peaks — gray rock
    const t = Math.min(1, Math.max(0, (alt - 1600) / 600));
    return [0.47 + t * 0.2, 0.3 + t * 0.25, 0.25 + t * 0.3];
  }
}
