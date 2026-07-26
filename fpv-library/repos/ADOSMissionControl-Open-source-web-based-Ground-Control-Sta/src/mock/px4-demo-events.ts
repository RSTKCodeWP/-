/**
 * @module mock/px4-demo-events
 * @description Demo-mode PX4 events: a tiny events-metadata map + a few EVENT
 * frames the PX4 mock emits, so the Logs → Events feed renders decoded text
 * (with argument substitution) in `npm run demo`. Loaded only under demo mode.
 * @license GPL-3.0-only
 */

import type { EventMeta } from "@/lib/protocol/param-metadata/px4-event-metadata";

/** Component 1, sub-ids 100–102 → full ids `(1<<24)|sub`. */
export const DEMO_EVENT_BATTERY_LOW = 0x01000064;
export const DEMO_EVENT_TAKEOFF = 0x01000065;
export const DEMO_EVENT_RC_LOSS = 0x01000066;

/** Metadata the demo store seeds instead of an FC fetch. */
export const DEMO_PX4_EVENT_METADATA: Map<number, EventMeta> = new Map([
  [
    DEMO_EVENT_BATTERY_LOW,
    { name: "battery_low", message: "Battery low: {1:.1V}", args: [{ type: "float", name: "voltage" }] },
  ],
  [DEMO_EVENT_TAKEOFF, { name: "takeoff_detected", message: "Takeoff detected", args: [] }],
  [DEMO_EVENT_RC_LOSS, { name: "manual_control_lost", message: "Manual control lost", args: [] }],
]);

/** One demo EVENT frame (matches the RawEvent shape the store consumes). */
export interface DemoEventFrame {
  id: number;
  logLevels: number;
  arguments: Uint8Array;
  eventTimeBootMs: number;
}

function floatArg(value: number): Uint8Array {
  const buf = new Uint8Array(40);
  new DataView(buf.buffer).setFloat32(0, value, true);
  return buf;
}

/** The cycle of frames the demo px4 mock emits (external log level in low nibble). */
export const DEMO_PX4_EVENT_FRAMES: DemoEventFrame[] = [
  { id: DEMO_EVENT_TAKEOFF, logLevels: 0x06, arguments: new Uint8Array(40), eventTimeBootMs: 12000 },
  { id: DEMO_EVENT_BATTERY_LOW, logLevels: 0x04, arguments: floatArg(14.2), eventTimeBootMs: 45000 },
  { id: DEMO_EVENT_RC_LOSS, logLevels: 0x03, arguments: new Uint8Array(40), eventTimeBootMs: 61000 },
];
