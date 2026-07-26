"use client";

import {
  BadgeCheck,
  CheckCircle2,
  Code2,
  PackageOpen,
  ShieldOff,
  Star,
} from "lucide-react";

import { cn } from "@/lib/utils";

export type TrustSignal =
  | "signed"
  | "verified-publisher"
  | "first-party"
  | "open-source"
  | "vendor-binary"
  | "unsigned";

interface TrustBadgeProps {
  signal: TrustSignal;
  className?: string;
}

const TRUST_PRESET: Record<
  TrustSignal,
  { label: string; icon: typeof BadgeCheck; classes: string; tooltip: string }
> = {
  signed: {
    label: "Signed",
    icon: CheckCircle2,
    classes: "border-text-secondary/30 bg-surface-secondary text-text-primary",
    tooltip: "Archive carries an Ed25519 signature that verified at install.",
  },
  "verified-publisher": {
    label: "Verified",
    icon: BadgeCheck,
    classes:
      "border-accent-primary/40 bg-accent-primary/10 text-accent-primary",
    tooltip:
      "Signed by a publisher in the first-party allowlist. Treated as trusted code.",
  },
  "first-party": {
    label: "First-party",
    icon: Star,
    classes:
      "border-accent-primary/40 bg-accent-primary/10 text-accent-primary",
    tooltip: "Built and published by Altnautica. Held to the first-party bar.",
  },
  "open-source": {
    label: "Open source",
    icon: Code2,
    classes:
      "border-status-success/40 bg-status-success/10 text-status-success",
    tooltip: "Source repository declared in the manifest is publicly auditable.",
  },
  "vendor-binary": {
    label: "Vendor binary",
    icon: PackageOpen,
    classes:
      "border-status-warning/40 bg-status-warning/10 text-status-warning",
    tooltip:
      "Plugin ships at least one closed-source vendor binary. Operator approval required.",
  },
  unsigned: {
    label: "Unsigned",
    icon: ShieldOff,
    classes: "border-status-error/40 bg-status-error/10 text-status-error",
    tooltip:
      "No signature. Only allowed in developer mode. Not safe for production fleets.",
  },
};

export function TrustBadge({ signal, className }: TrustBadgeProps) {
  const preset = TRUST_PRESET[signal];
  const Icon = preset.icon;
  return (
    <span
      role="img"
      aria-label={preset.tooltip}
      title={preset.tooltip}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium",
        preset.classes,
        className,
      )}
    >
      <Icon className="h-3 w-3" aria-hidden />
      <span>{preset.label}</span>
    </span>
  );
}
