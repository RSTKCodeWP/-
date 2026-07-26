export type { FcAdapter, FcType, FlightMode } from './interface';
export { ardupilotAdapter } from './ardupilot';
export { px4Adapter } from './px4';

import type { FcAdapter } from './interface';
import { ardupilotAdapter } from './ardupilot';
import { px4Adapter } from './px4';

const adapters: FcAdapter[] = [ardupilotAdapter, px4Adapter];

/**
 * Detect FC type from HEARTBEAT autopilot field and return the appropriate adapter.
 * Defaults to ArduPilot if unknown.
 */
export function detectAdapter(autopilot: number): FcAdapter {
  for (const a of adapters) {
    if (a.matches(autopilot)) return a;
  }
  return ardupilotAdapter;
}
