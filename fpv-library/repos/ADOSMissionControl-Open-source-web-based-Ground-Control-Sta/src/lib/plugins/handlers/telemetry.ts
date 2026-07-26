/**
 * Telemetry subscription handlers for the plugin bridge.
 *
 * `telemetry.subscribe` wires the protocol callback for a known topic on
 * the target drone and forwards every frame to the iframe as a host event
 * on `telemetry.<topic>`. `telemetry.unsubscribe` tears down one topic; the
 * builder's `dispose()` tears down all of them. The bridge has already
 * gated the per-topic `telemetry.subscribe.<topic>` capability before the
 * handler runs, so these never re-check capabilities.
 *
 * @module plugins/handlers/telemetry
 * @license GPL-3.0-only
 */

import type { DroneProtocol } from "@/lib/protocol/types";
import { useDroneManager } from "@/stores/drone-manager";
import type { BridgeHandler, BridgeHandlerContext } from "@/lib/plugins/bridge";

/**
 * A topic-specific subscription: wires the matching protocol callback and
 * returns its unsubscribe. `emit` is called with each raw telemetry frame.
 */
type TopicSubscriber = (
  protocol: DroneProtocol,
  emit: (data: unknown) => void,
) => () => void;

/**
 * Known telemetry topics a plugin may subscribe to, each mapped to the
 * protocol callback that feeds it. Both the dotted `mavlink.*` form (used by
 * the per-topic capability strings and the bridge tests) and the plain
 * channel name are accepted so a plugin can use either spelling. Unknown
 * topics are rejected by the handler. Every callback used here is part of
 * the required `DroneProtocol` surface, so no optional-chaining guard is
 * needed.
 */
const TOPIC_SUBSCRIBERS: Record<string, TopicSubscriber> = {
  "mavlink.attitude": (p, emit) => p.onAttitude(emit),
  attitude: (p, emit) => p.onAttitude(emit),
  "mavlink.position": (p, emit) => p.onPosition(emit),
  position: (p, emit) => p.onPosition(emit),
  "mavlink.battery": (p, emit) => p.onBattery(emit),
  battery: (p, emit) => p.onBattery(emit),
  "mavlink.gps": (p, emit) => p.onGps(emit),
  gps: (p, emit) => p.onGps(emit),
  "mavlink.vfr": (p, emit) => p.onVfr(emit),
  vfr: (p, emit) => p.onVfr(emit),
  "mavlink.rc": (p, emit) => p.onRc(emit),
  rc: (p, emit) => p.onRc(emit),
  "mavlink.SYS_STATUS": (p, emit) => p.onSysStatus(emit),
  sysStatus: (p, emit) => p.onSysStatus(emit),
  "mavlink.radio": (p, emit) => p.onRadio(emit),
  radio: (p, emit) => p.onRadio(emit),
  "mavlink.HEARTBEAT": (p, emit) => p.onHeartbeat(emit),
  heartbeat: (p, emit) => p.onHeartbeat(emit),
  "mavlink.STATUSTEXT": (p, emit) => p.onStatusText(emit),
  statustext: (p, emit) => p.onStatusText(emit),
  "mavlink.EVENT": (p, emit) => p.onEvent(emit),
  event: (p, emit) => p.onEvent(emit),
};

/** The set of known topics, for callers that want to advertise them. */
export const KNOWN_TELEMETRY_TOPICS: readonly string[] =
  Object.keys(TOPIC_SUBSCRIBERS);

/**
 * Resolve the protocol for the plugin's target drone. Prefer the managed
 * drone matching the plugin's deviceId; fall back to the selected drone so a
 * standalone connection without a separate device identity still works.
 */
function resolveProtocol(deviceId: string | null): DroneProtocol | null {
  const mgr = useDroneManager.getState();
  if (deviceId) {
    const drone = mgr.drones.get(deviceId);
    if (drone) return drone.protocol;
  }
  return mgr.getSelectedProtocol();
}

/** Read and validate the `topic` field off an untrusted args payload. */
function readTopic(args: unknown): string {
  const topic = (args as { topic?: unknown } | null | undefined)?.topic;
  if (typeof topic !== "string" || topic.length === 0) {
    throw new Error("telemetry topic must be a non-empty string");
  }
  return topic;
}

/**
 * Build the `telemetry.subscribe` / `telemetry.unsubscribe` handlers for one
 * plugin, plus a `dispose()` that drops every subscription. Subscriptions are
 * tracked per topic so a re-subscribe replaces the prior one (idempotent).
 */
export function buildTelemetryHandlers(deviceId: string | null): {
  handlers: Record<string, BridgeHandler>;
  dispose: () => void;
} {
  const subs = new Map<string, () => void>();

  const subscribe: BridgeHandler = (args, ctx: BridgeHandlerContext) => {
    const topic = readTopic(args);
    const sub = TOPIC_SUBSCRIBERS[topic];
    if (!sub) throw new Error(`unknown telemetry topic: ${topic}`);

    const protocol = resolveProtocol(deviceId);
    if (!protocol) {
      throw new Error("no connected drone for telemetry subscription");
    }

    // Replace any prior subscription to the same topic.
    subs.get(topic)?.();

    const capability = ctx.capability ?? "";
    const unsub = sub(protocol, (data) =>
      ctx.postEvent(`telemetry.${topic}`, capability, data),
    );
    subs.set(topic, unsub);
    return { ok: true };
  };

  const unsubscribe: BridgeHandler = (args) => {
    const topic = readTopic(args);
    const unsub = subs.get(topic);
    if (!unsub) return { ok: false };
    unsub();
    subs.delete(topic);
    return { ok: true };
  };

  const dispose = () => {
    for (const unsub of subs.values()) {
      try {
        unsub();
      } catch {
        // Best-effort teardown; a throwing unsubscribe must not wedge the rest.
      }
    }
    subs.clear();
  };

  return {
    handlers: {
      "telemetry.subscribe": subscribe,
      "telemetry.unsubscribe": unsubscribe,
    },
    dispose,
  };
}
