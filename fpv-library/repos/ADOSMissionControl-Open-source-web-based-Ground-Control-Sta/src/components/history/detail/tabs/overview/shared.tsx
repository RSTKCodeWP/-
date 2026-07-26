/**
 * Shared row + coordinate formatter for the Overview tab cards.
 *
 * @module components/history/detail/tabs/overview/shared
 */

import { formatCoord } from "@/lib/i18n/format";
import type { Locale } from "@/i18n";

export function Row({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[11px] text-text-secondary">{label}</span>
      <span className={`text-xs text-text-primary ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  );
}

export function fmtCoord(lat?: number, lon?: number, locale?: Locale | string): string {
  if (lat === undefined || lon === undefined) return "—";
  return formatCoord(lat, lon, 5, locale ?? "en");
}
