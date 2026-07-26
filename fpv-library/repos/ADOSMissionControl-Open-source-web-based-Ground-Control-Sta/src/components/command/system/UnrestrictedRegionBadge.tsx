"use client";

/**
 * @module command/system/UnrestrictedRegionBadge
 * @description An amber pill that marks the radio as running with no
 * pinned operating region. Unrestricted is never silent: the radio comes
 * up and transmits without a verified regulatory domain, so this badge and
 * its caveat tooltip make the posture visible and remind the operator they
 * are responsible for local RF compliance. Reused by the region control
 * card, the radio-health indicator, and the onboarding region step.
 * @license GPL-3.0-only
 */

import { ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import { Tooltip } from "@/components/ui/tooltip";

interface Props {
  /** Compact rendering: smaller text + tighter padding for inline rows. */
  compact?: boolean;
}

export function UnrestrictedRegionBadge({ compact = false }: Props) {
  const t = useTranslations("operatingRegion");
  return (
    <Tooltip content={t("unrestrictedCaveat")}>
      <span
        className={
          compact
            ? "inline-flex items-center gap-1 rounded border border-status-warning/40 bg-status-warning/10 px-1.5 py-0.5 text-[10px] font-medium text-status-warning"
            : "inline-flex items-center gap-1.5 rounded border border-status-warning/40 bg-status-warning/10 px-2.5 py-1 text-xs font-medium text-status-warning"
        }
      >
        <ShieldAlert size={compact ? 11 : 13} />
        {t("unrestrictedBadge")}
      </span>
    </Tooltip>
  );
}
