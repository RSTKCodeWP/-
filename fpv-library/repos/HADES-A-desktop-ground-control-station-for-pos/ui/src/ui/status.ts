/* The status encoding — a closed state-machine with ONE encoding everywhere
 * (DESIGN-SYSTEM §6.4). Every status maps to exactly one color token and one glyph shape
 * (§6.5), so the pin, list row, detail panel, and status strip can never disagree, and the
 * color is always backed by a non-color channel (CVD + glare survival). Warning vs critical
 * use maximally distinct shapes — under glare the glyph may be the only surviving channel,
 * and these two demand opposite operator actions (survivor vs system failure). */

export type Status = "nominal" | "info" | "caution" | "warning" | "critical" | "stale";

const TOKEN: Record<Status, string> = {
  nominal: "st-nominal",
  info: "st-info",
  caution: "st-caution",
  warning: "st-warning",
  critical: "st-critical",
  stale: "st-stale",
};

// §6.5 status-glyph alphabet (placeholder shapes; rendered via Lucide/custom in components).
const GLYPH: Record<Status, string> = {
  nominal: "●", // filled disc
  info: "◆", // filled diamond
  caution: "▲", // triangle
  warning: "◉", // filled target/reticle — world-urgency (survivor)
  critical: "■", // filled square — system-integrity failure
  stale: "◌", // dashed hollow ring — unknown/degraded
};

export function statusToken(s: Status): string {
  return TOKEN[s];
}

export function statusGlyph(s: Status): string {
  return GLYPH[s];
}

/** Tailwind text-color utility bound to the status token (DESIGN-SYSTEM §9.1). */
export function statusTextClass(s: Status): string {
  return `text-${TOKEN[s]}`;
}
