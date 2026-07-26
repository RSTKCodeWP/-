/**
 * @module agent/stale-local-identity
 * @description Pure predicate behind the locally-paired-card self-heal.
 * A LAN-only fleet card is dropped ONLY on a definitive "reachable but
 * not ours" signal from the agent's pairing-info probe, never on an
 * unreachable probe (an offline-but-paired drone) or an empty reported
 * id. Extracted from CommandFleetLocalBridge so this data-safety
 * decision is unit-tested independently of the polling component.
 * @license GPL-3.0-only
 */

import type { ProbeResult } from "./local-pair/types";

/**
 * True when a locally-paired card should self-heal (drop) because the
 * box at its hostname is reachable but is no longer the same paired
 * agent: it reports a different non-empty device id (re-flashed or
 * reassigned), or it reports itself unpaired (unpaired from its own
 * webapp, another browser, or the CLI). An empty reported id is treated
 * as "no signal" and never drops the row. An unreachable probe never
 * reaches this predicate — the caller swallows it as transient.
 */
export function isStaleLocalIdentity(
  info: Pick<ProbeResult, "deviceId" | "paired">,
  expectedDeviceId: string,
): boolean {
  return (
    (info.deviceId.length > 0 && info.deviceId !== expectedDeviceId) ||
    info.paired === false
  );
}
