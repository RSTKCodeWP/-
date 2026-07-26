/**
 * Render helpers for the vision-nav estimator mode.
 *
 * The fleet card, drone card, and dashboard summary all want a short
 * pill ("OF" / "VIO" / "Hybrid") plus a human-readable tooltip. The
 * mode key comes from the agent heartbeat verbatim, so this module is
 * the single place that turns a mode key into UI strings.
 *
 * The label set is intentionally English-only here; the full
 * translated copy lives in the `navigation.modeBadge.*` i18n keys and
 * is consumed by the in-iframe extension components. The fleet-level
 * card on the GCS side keeps these short, neutral pills because they
 * sit alongside other terse status badges (LCD, Local, Plugins).
 */

export type NavigationModeKey =
  | "off"
  | "optical_flow"
  | "optical_flow_degraded"
  | "vio_openvins"
  | "vio_vins_fusion"
  | "hybrid_of_plus_vio";

export interface NavigationModeBadge {
  /** Short text on the pill itself. */
  short: string;
  /** Long-form tooltip. */
  tooltip: string;
  /** "ok" | "warn" | "muted" — drives the badge colour variant. */
  tone: "ok" | "warn" | "muted";
}

const BADGES: Record<NavigationModeKey, NavigationModeBadge> = {
  off: {
    short: "Off",
    tooltip: "Vision navigation is loaded but disabled.",
    tone: "muted",
  },
  optical_flow: {
    short: "OF",
    tooltip: "Optical-flow GPS-denied navigation active.",
    tone: "ok",
  },
  optical_flow_degraded: {
    short: "OF*",
    tooltip:
      "Optical flow without a rangefinder. Scale comes from the " +
      "baro / GPS ladder; accuracy is reduced.",
    tone: "warn",
  },
  vio_openvins: {
    short: "VIO",
    tooltip: "Visual-inertial odometry active (OpenVINS).",
    tone: "ok",
  },
  vio_vins_fusion: {
    short: "VIO",
    tooltip: "Visual-inertial odometry active (VINS-Fusion).",
    tone: "ok",
  },
  hybrid_of_plus_vio: {
    short: "Hybrid",
    tooltip:
      "Hybrid optical flow + VIO. Two cameras feed the EKF in parallel.",
    tone: "ok",
  },
};

/**
 * Resolve a heartbeat mode value (free-form string) to a badge spec.
 * Returns ``null`` when no pill should be drawn — either the mode is
 * absent, ``"off"``, or unrecognised.
 */
export function navigationModeBadge(
  mode: string | undefined,
): NavigationModeBadge | null {
  if (!mode) return null;
  const lookup = BADGES[mode as NavigationModeKey];
  if (lookup === undefined) return null;
  if (mode === "off") return null;
  return lookup;
}

/** Map of every known mode → badge spec, for tests and storybook. */
export const NAVIGATION_MODE_BADGES = BADGES;
