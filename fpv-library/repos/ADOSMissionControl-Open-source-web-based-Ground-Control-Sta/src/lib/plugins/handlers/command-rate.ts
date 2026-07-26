/**
 * Per-plugin fixed-window rate limit for confirmed `command.send` calls.
 *
 * A plugin that drives the vehicle is fenced both by operator confirmation
 * and by this cap, so a single approval can never be amplified into a flood
 * of MAV_CMD traffic. The window counts only calls that have already passed
 * the confirm gate (the handler calls in right before dispatching the
 * command), so the cap is on confirmed sends, not on attempts.
 *
 * `now` is injected so callers/tests own the clock — this never reads the
 * wall clock itself. Mirrors `checkCloudRateLimit` in `../cloud-allowlist.ts`.
 *
 * @module plugins/handlers/command-rate
 * @license GPL-3.0-only
 */

/** Max confirmed command.send calls per plugin per window. */
export const COMMAND_RATE_LIMIT_MAX = 10;
/** Rate-limit window length, in milliseconds. */
export const COMMAND_RATE_LIMIT_WINDOW_MS = 60_000;

interface RateWindow {
  windowStart: number;
  count: number;
}

const rateWindows = new Map<string, RateWindow>();

/**
 * Fixed-window rate limit. Returns `true` when the call is allowed (and counts
 * it), `false` when the plugin has exhausted its window.
 */
export function checkCommandRateLimit(pluginId: string, now: number): boolean {
  const existing = rateWindows.get(pluginId);
  if (
    existing === undefined ||
    now - existing.windowStart >= COMMAND_RATE_LIMIT_WINDOW_MS
  ) {
    rateWindows.set(pluginId, { windowStart: now, count: 1 });
    return true;
  }
  if (existing.count >= COMMAND_RATE_LIMIT_MAX) {
    return false;
  }
  existing.count += 1;
  return true;
}

/** Clear all per-plugin command rate-limit state. For tests. */
export function resetCommandRateLimits(): void {
  rateWindows.clear();
}
