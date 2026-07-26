import type { ExpressionSpecification } from "maplibre-gl";

import type { Status } from "../ui/status";

/* Bespoke map layer paint — MapLibre data-driven expressions (DESIGN-SYSTEM §5.1). The map
 * canvas can't use Tailwind classes, so status → literal hex here MUST mirror tokens.css
 * §2.4. The pin and its uncertainty ring share the same status encoding; the selected pin
 * and ring read stronger. Status hex is theme-aware (§12): the DAY set is the luminance-
 * rechecked light palette (deepened so marks read as ink on light land and keep CVD/P0
 * separation); NIGHT is the original bright set. */

export type MapTheme = "day" | "night";

// Mirror of tokens.css §2.4 — the closed status set as literal hex for the GL canvas, per mode.
const STATUS_HEX_BY_THEME: Record<MapTheme, Record<Status, string>> = {
  night: {
    nominal: "#2FB67C",
    info: "#33C5E0",
    caution: "#E6A23C",
    warning: "#E8531F", // survivor world-urgency
    critical: "#F5326B", // system failure (not used for contacts)
    stale: "#7E78A8",
  },
  day: {
    nominal: "#117449",
    info: "#0F768E",
    caution: "#C58E10",
    warning: "#D03E10", // survivor world-urgency
    critical: "#C4164E", // system failure (not used for contacts)
    stale: "#68628C",
  },
};

// Back-compat default (the original bright set) for non-map callers (e.g. the video overlay).
export const STATUS_HEX: Record<Status, string> = STATUS_HEX_BY_THEME.night;

export function statusHex(theme: MapTheme = "night"): Record<Status, string> {
  return STATUS_HEX_BY_THEME[theme];
}

const STATUSES: Status[] = ["nominal", "info", "caution", "warning", "critical", "stale"];

function statusMatch(theme: MapTheme): ExpressionSpecification {
  const hex = STATUS_HEX_BY_THEME[theme];
  const cases: (string | string[])[] = [];
  for (const s of STATUSES) {
    cases.push(s, hex[s]);
  }
  return ["match", ["get", "status"], ...cases, hex.info] as unknown as ExpressionSpecification;
}

/** Pin (reticle center) fill color by status. */
export function pinColorExpr(theme: MapTheme = "night"): ExpressionSpecification {
  return statusMatch(theme);
}

/** Pin radius: the selected pin reads larger (the eye lands on it). */
export function pinRadiusExpr(): ExpressionSpecification {
  return ["case", ["get", "selected"], 8, 5] as unknown as ExpressionSpecification;
}

/** Uncertainty ring stroke color — same status hue as its pin. */
export function circleStrokeColorExpr(theme: MapTheme = "night"): ExpressionSpecification {
  return statusMatch(theme);
}

/** Uncertainty ring stroke width: stronger when selected (the edge carries the meaning). */
export function circleStrokeWidthExpr(): ExpressionSpecification {
  return ["case", ["get", "selected"], 2.2, 1.2] as unknown as ExpressionSpecification;
}
