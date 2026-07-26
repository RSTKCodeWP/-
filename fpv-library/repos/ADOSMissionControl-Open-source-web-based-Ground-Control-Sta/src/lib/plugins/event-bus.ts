/**
 * In-memory pub/sub transport for plugin events on the GCS side.
 *
 * Plugin RPC handlers (the postMessage bridge dispatches them outside the
 * React tree) need a way to fan a published event out to every interested
 * subscriber without a backend round-trip. This module is that transport: a
 * process-wide singleton mapping dotted topics to subscriber callbacks.
 *
 * Topics are dotted strings (`plugin.com.example.foo.result`,
 * `vehicle.armed`). A subscription is either an exact topic or a
 * trailing-wildcard pattern ending in `.*` (`plugin.foo.*`), which matches
 * any topic under that prefix. Mid-pattern and arbitrary-depth (`**`)
 * wildcards are intentionally unsupported — keep matching cheap.
 *
 * Delivery is synchronous and bounded. Each subscriber owns a queue capped at
 * {@link MAX_QUEUE}; if a callback re-enters publish (or floods its own topic)
 * faster than the queue drains, the oldest entries are dropped and a per-
 * subscriber counter is bumped rather than growing without bound or throwing.
 * Each callback is invoked inside try/catch so one misbehaving subscriber can
 * never break delivery for the others, nor for the publisher.
 *
 * This module is PURE TRANSPORT. It does not enforce capabilities — the bridge
 * and handler layer gate `event.subscribe` / `event.publish` before calling in.
 *
 * @license GPL-3.0-only
 */

/** Maximum buffered, undelivered events per subscriber before drop-oldest. */
export const MAX_QUEUE = 256;

/** Subscriber callback. Receives the event payload and the concrete topic. */
export type PluginEventCallback = (payload: unknown, topic: string) => void;

interface QueuedEvent {
  payload: unknown;
  topic: string;
}

interface Subscription {
  /** Literal topic to match exactly, or `null` when this is a wildcard. */
  exact: string | null;
  /** Prefix (incl. trailing dot) a topic must start with for a wildcard. */
  prefix: string | null;
  subscriberPluginId: string;
  cb: PluginEventCallback;
  queue: QueuedEvent[];
  dropped: number;
  /** Re-entrancy guard so a nested publish does not recurse the drain loop. */
  delivering: boolean;
}

const subscriptions = new Set<Subscription>();

function matches(sub: Subscription, topic: string): boolean {
  if (sub.exact !== null) return sub.exact === topic;
  if (sub.prefix !== null) return topic.startsWith(sub.prefix);
  return false;
}

function enqueue(sub: Subscription, event: QueuedEvent): void {
  if (sub.queue.length >= MAX_QUEUE) {
    sub.queue.shift();
    sub.dropped += 1;
  }
  sub.queue.push(event);
}

function drain(sub: Subscription): void {
  if (sub.delivering) return;
  sub.delivering = true;
  try {
    while (sub.queue.length > 0) {
      const event = sub.queue.shift();
      if (event === undefined) break;
      try {
        sub.cb(event.payload, event.topic);
      } catch {
        // A throwing subscriber must not break delivery for others.
      }
    }
  } finally {
    sub.delivering = false;
  }
}

/**
 * Publish an event to every matching subscriber. Synchronous and never throws.
 *
 * @param topic         Concrete dotted topic (no wildcards).
 * @param payload       Arbitrary event payload, passed through untouched.
 * @param fromPluginId  Origin plugin id. Recorded for the caller's context;
 *                      not used for routing (the bus does not self-filter).
 */
export function publishPluginEvent(
  topic: string,
  payload: unknown,
  fromPluginId: string,
): void {
  void fromPluginId;
  const targets: Subscription[] = [];
  for (const sub of subscriptions) {
    if (matches(sub, topic)) targets.push(sub);
  }
  for (const sub of targets) enqueue(sub, { payload, topic });
  for (const sub of targets) drain(sub);
}

/**
 * Subscribe to a topic or trailing-wildcard pattern.
 *
 * @param topic                A concrete topic, or a pattern ending in `.*`
 *                             (or the bare `*`) for prefix matching.
 * @param subscriberPluginId   The subscribing plugin's id (bookkeeping only).
 * @param cb                   Invoked synchronously per matching event.
 * @returns An idempotent unsubscribe function.
 */
export function subscribePluginEvent(
  topic: string,
  subscriberPluginId: string,
  cb: PluginEventCallback,
): () => void {
  let exact: string | null = topic;
  let prefix: string | null = null;
  if (topic === "*") {
    exact = null;
    prefix = "";
  } else if (topic.endsWith(".*")) {
    exact = null;
    prefix = topic.slice(0, -1); // keep trailing dot: "plugin.foo."
  }

  const sub: Subscription = {
    exact,
    prefix,
    subscriberPluginId,
    cb,
    queue: [],
    dropped: 0,
    delivering: false,
  };
  subscriptions.add(sub);

  return () => {
    subscriptions.delete(sub);
  };
}

/** Aggregate bus stats. For diagnostics and tests. */
export function pluginEventBusStats(): {
  subscriptions: number;
  droppedTotal: number;
} {
  let droppedTotal = 0;
  for (const sub of subscriptions) droppedTotal += sub.dropped;
  return { subscriptions: subscriptions.size, droppedTotal };
}

/** Drop every subscription and reset all counters. For tests. */
export function resetPluginEventBus(): void {
  subscriptions.clear();
}
