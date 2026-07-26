/* Degrade-visibly (impl-plan Task 5.7c / M12): localization confidence is DYNAMICALLY
 * coupled to telemetry freshness. A fix is only as trustworthy as the pose that produced
 * it; once telemetry goes stale, the contact's effective localization confidence collapses
 * toward zero — the UI shows that collapse live, rather than displaying a stale-but-high
 * number (the smug-filter lie the whole project guards against). Thresholds mirror the
 * status strip's telemetry severity (system.ts). */

const TEL_FRESH_S = 1.0; // full trust below this
const TEL_STALE_S = 6.0; // ~no trust at/above this

/** Reported loc-conf scaled down by telemetry age: full when fresh, ~0 when stale. */
export function effectiveLocConf(reported: number, telemetryAgeS: number): number {
  if (telemetryAgeS <= TEL_FRESH_S) return reported;
  if (telemetryAgeS >= TEL_STALE_S) return 0;
  const decay = 1 - (telemetryAgeS - TEL_FRESH_S) / (TEL_STALE_S - TEL_FRESH_S);
  return Math.max(0, reported * decay);
}

/** Whether a contact should be flagged STALE given the current telemetry age. */
export function isContactStale(telemetryAgeS: number): boolean {
  return telemetryAgeS >= TEL_STALE_S;
}
