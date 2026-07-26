"use client";

/**
 * @module components/command/SigningStatusBadge
 * @description MAVLink signing state pill for a drone.
 *
 * Six variants, each with a distinct icon, color, and aria-label so the
 * state is legible to both sighted users and screen readers:
 *
 *   Signed              — browser key present, FC enrolled, require=off
 *   Signed + required   — same, plus FC rejects unsigned commands
 *   Unsigned            — firmware supports signing but no browser key
 *   Key missing         — FC requires signing but this browser has no key
 *   Mismatch            — browser has a key but FC rejected recent frames
 *   Not available       — firmware does not expose a signing key store
 *
 * @license GPL-3.0-only
 */

import { Lock, Unlock, MinusCircle, ShieldAlert, AlertTriangle, type LucideIcon } from "lucide-react";
import { useSigningStore } from "@/stores/signing-store";

interface Props {
  droneId: string;
  /** Hide the text label and only show the icon. */
  compact?: boolean;
}

export type SigningBadgeVariant =
  | "signed"
  | "signed_required"
  | "unsigned"
  | "key_missing"
  | "mismatch"
  | "na"
  | "loading";

export const MISMATCH_WINDOW_MS = 30_000;

export interface BadgeClassifyInput {
  capability: { supported: boolean } | null;
  hasBrowserKey: boolean;
  enrollmentState?: string;
  requireOnFc?: boolean | null;
  rxInvalidCount?: number;
  lastSignedFrameAt?: number | null;
}

export function SigningStatusBadge({ droneId, compact = false }: Props) {
  const state = useSigningStore((s) => s.drones[droneId]);
  const variant = classifyVariant(state);
  const config = VARIANTS[variant];

  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] font-medium ${config.className}`}
      role="status"
      aria-label={config.ariaLabel}
      title={config.tooltip}
    >
      <config.Icon size={11} aria-hidden="true" />
      {!compact && <span>{config.label}</span>}
    </span>
  );
}

/**
 * Pure variant classifier. Exported so unit tests can drive every branch
 * without mounting React.
 */
export function classifyVariant(
  state: BadgeClassifyInput | undefined,
  now: number = Date.now(),
): SigningBadgeVariant {
  if (!state || state.capability === null) return "loading";
  if (!state.capability.supported) return "na";
  if (state.enrollmentState === "key_missing") return "key_missing";

  // Mismatch: we have a key and the FC has rejected frames in the recent
  // window. The parser increments rxInvalidCount; the window guard keeps
  // old failures from sticking forever.
  if (
    state.hasBrowserKey &&
    (state.rxInvalidCount ?? 0) > 0 &&
    state.lastSignedFrameAt !== null &&
    state.lastSignedFrameAt !== undefined &&
    now - state.lastSignedFrameAt < MISMATCH_WINDOW_MS
  ) {
    return "mismatch";
  }

  if (state.hasBrowserKey && state.enrollmentState === "enrolled") {
    return state.requireOnFc === true ? "signed_required" : "signed";
  }
  return "unsigned";
}

interface VariantConfig {
  label: string;
  ariaLabel: string;
  tooltip: string;
  className: string;
  Icon: LucideIcon;
}

export const VARIANTS: Record<SigningBadgeVariant, VariantConfig> = {
  signed: {
    label: "Signed",
    ariaLabel: "MAVLink signing enabled",
    tooltip: "Every command to this drone is signed with HMAC-SHA256.",
    className: "text-status-success",
    Icon: Lock,
  },
  signed_required: {
    label: "Signed · required",
    ariaLabel: "MAVLink signing enabled, require mode on",
    tooltip:
      "Every command is signed. The flight controller rejects unsigned commands.",
    className: "text-status-success border border-status-success/60 px-1",
    Icon: Lock,
  },
  unsigned: {
    label: "Unsigned",
    ariaLabel: "MAVLink signing supported but not enabled",
    tooltip: "This drone supports MAVLink signing but it is not enabled.",
    className: "text-text-tertiary",
    Icon: Unlock,
  },
  key_missing: {
    label: "Key missing",
    ariaLabel: "MAVLink signing key is missing on this browser",
    tooltip:
      "The flight controller requires signing but this browser has no matching key.",
    className: "text-status-warning",
    Icon: ShieldAlert,
  },
  mismatch: {
    label: "Mismatch",
    ariaLabel: "MAVLink signing mismatch, recent frames rejected",
    tooltip:
      "The flight controller has recently rejected signed frames. Check for a second GCS on a stale key.",
    className: "text-status-error",
    Icon: AlertTriangle,
  },
  na: {
    label: "No signing",
    ariaLabel: "MAVLink signing not supported on this firmware",
    tooltip: "This firmware does not expose a signing key store.",
    className: "text-text-tertiary opacity-70",
    Icon: MinusCircle,
  },
  loading: {
    label: "…",
    ariaLabel: "MAVLink signing state loading",
    tooltip: "Checking signing capability…",
    className: "text-text-tertiary opacity-50",
    Icon: Unlock,
  },
};
