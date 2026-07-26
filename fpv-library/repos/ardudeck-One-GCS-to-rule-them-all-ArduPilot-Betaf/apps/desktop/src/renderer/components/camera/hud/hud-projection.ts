/**
 * The fighter HUD's SVG projection geometry, extracted so both FighterHud and
 * the module host API (host.hud) share one source of truth. A `cameraOverlay`
 * module draws its own SVG in this same viewBox (with preserveAspectRatio
 * 'xMidYMid meet' and the `scale` group) so its symbology lines up with the
 * pitch ladder.
 */

export const HUD_VIEWBOX_W = 1600;
export const HUD_VIEWBOX_H = 900;
export const HUD_CENTER_X = HUD_VIEWBOX_W / 2;
export const HUD_CENTER_Y = HUD_VIEWBOX_H / 2;

const PITCH_HALF_SPAN = 18;
const PITCH_BAND = 250;
/** viewBox units per degree of pitch / azimuth. */
export const HUD_PX_PER_DEG = PITCH_BAND / PITCH_HALF_SPAN;

import type { HudProjection } from '@ardudeck/module-sdk';
import type { HudConfig } from './hud-config';
import { HUD_COLORS } from './hud-config';

/** Build the HUD projection (geometry + resolved style) from a HUD config. The
 *  single source of truth for both the live host.hud projection and the
 *  module-instrument renderer, so module symbology matches the built-in HUD. */
export function buildHudProjection(config: HudConfig): HudProjection {
  return {
    viewBoxW: HUD_VIEWBOX_W,
    viewBoxH: HUD_VIEWBOX_H,
    centerX: HUD_CENTER_X,
    centerY: HUD_CENTER_Y,
    pxPerDeg: HUD_PX_PER_DEG,
    scale: config.scale,
    color: HUD_COLORS[config.color],
    lineWeight: config.lineWeight,
  };
}
