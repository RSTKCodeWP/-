import type { ContactRecord } from "../types/wire";
import type { Status } from "./status";

/* Map a contact's actionability + priority tier to the closed status set
 * (DESIGN-SYSTEM §2.4 / §6.4) — the single encoding the pin, row, and panel all share.
 *
 * Crucially this NEVER returns `critical`: that hue (magenta) is reserved for SYSTEM-
 * integrity failure (link-lost), not for any contact, no matter how urgent (P0 rule). A
 * survivor that needs you is `warning` (orange); a contact with no usable fix is `stale`. */

export function contactStatus(r: ContactRecord): Status {
  if (r.actionability_class === "CUE_ONLY") return "stale";
  if (r.actionability_class === "PINPOINT" && r.priority_tier === "strong") return "warning";
  if (r.actionability_class === "SWEEP") return "caution";
  if (r.actionability_class === "PINPOINT") return "caution"; // PINPOINT but not yet strong
  return "info"; // AREA and the remaining candidate/contact states
}
