/**
 * @module AgentConnectionPollBackoff
 * @description Pure poll-cadence math for the agent connection client. Kept in
 * its own store-free module so it can be imported (and unit-tested) without
 * pulling in the full agent-connection store graph, whose aggregator builds the
 * Zustand store at import time — importing the client-manager slice directly
 * would otherwise trip a load-order cycle.
 * @license GPL-3.0-only
 */

/** Base poll cadence for a healthy/reachable agent. */
export const POLL_BASE_MS = 3000;
/** Failure count past which the loop stops hammering at the base cadence and
 * begins backing off. Matches the offline threshold in the staleness cascade
 * (`noteFetchFailure`), so backoff begins exactly when the header flips
 * offline. */
export const OFFLINE_FAILURE_THRESHOLD = 6;
/** Backoff ceiling once the agent is declared offline. */
export const POLL_MAX_MS = 30000;

/** Reschedule delay derived from the consecutive-failure count. Stays at the
 * base cadence until the agent is declared offline, then ramps geometrically
 * toward the ceiling so a dead host is not hammered. A small jitter avoids
 * synchronised retries across tabs/agents. The first `noteFetchSuccess` resets
 * `consecutiveFailures` to 0, which snaps this straight back to the base. */
export function nextPollDelay(consecutiveFailures: number): number {
  if (consecutiveFailures < OFFLINE_FAILURE_THRESHOLD) return POLL_BASE_MS;
  // 0 extra steps → 3s, then 6s, 12s, 24s … capped at 30s.
  const steps = consecutiveFailures - OFFLINE_FAILURE_THRESHOLD;
  const backoff = Math.min(POLL_BASE_MS * 2 ** (steps + 1), POLL_MAX_MS);
  const jitter = Math.floor(Math.random() * 1000);
  return backoff + jitter;
}
