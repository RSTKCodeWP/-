"use client";

import { createElement } from "react";
import {
  Plane,
  CircuitBoard,
  Radio,
  Server,
  Car,
  Ship,
  Waves,
  Fan,
  type LucideIcon,
} from "lucide-react";
import { NODE_ACCENT_VAR, type EffProfile } from "@/lib/nodes/node-profile";

/** The airframe-specific glyph for a drone (rover = car, boat = ship, sub =
 * waves, heli = rotor, everything else = plane) so the sidebar reads the actual
 * vehicle at a glance instead of a plane for everything. */
function airframeGlyph(frameType?: string): LucideIcon {
  switch (frameType) {
    case "Rover":
      return Car;
    case "Boat":
      return Ship;
    case "Sub":
      return Waves;
    case "Heli":
      return Fan;
    default:
      // Copter / Plane / VTOL / Tailsitter / Tiltrotor / Wing / FPV
      return Plane;
  }
}

/** One canonical glyph per node profile + airframe. Ground/compute use their
 * profile glyph; a drone uses its airframe glyph. Resolved at call time (not a
 * module-load const) so importing this module does not eagerly touch the icon
 * bindings. */
export function nodeGlyph(profile: EffProfile, frameType?: string): LucideIcon {
  switch (profile) {
    case "ground-station":
      return Radio;
    case "workstation":
      return Server;
    case "flight-controller":
      // FC-only: use the airframe glyph when known, else the neutral board glyph.
      return frameType ? airframeGlyph(frameType) : CircuitBoard;
    default:
      return airframeGlyph(frameType);
  }
}

/** A profile/airframe glyph tinted with its identity accent. Type is one
 * channel; pass a separate StatusDot/ring for health (never conflate the two). */
export function NodeGlyph({
  profile,
  frameType,
  size = 16,
  className,
}: {
  profile: EffProfile;
  frameType?: string;
  size?: number;
  className?: string;
}) {
  return createElement(nodeGlyph(profile, frameType), {
    size,
    className,
    style: { color: `var(${NODE_ACCENT_VAR[profile]})` },
  });
}
