/**
 * One-click multi-vehicle discovery over UDP.
 *
 * Binds a primary UDP listener on `basePort` (this drives the "connected" state
 * and full single-vehicle compatibility for whichever vehicle is active) plus a
 * few background listeners on the next ports. Any ArduPilot vehicle that sends
 * telemetry to one of these ports - whether a single forwarder (MAVProxy-style)
 * fans the whole fleet into one port, or each vehicle lands on its own port -
 * self-registers and appears in the fleet. No port-by-port fiddling.
 */

import type { ConnectOptions } from '../../shared/ipc-channels';

export interface ListenOptions {
  /** First UDP port to bind as the primary listener. Default 14550. */
  basePort?: number;
  /** Extra consecutive ports to also listen on as background links. Default 3. */
  extraPorts?: number;
}

/**
 * @param connect the connection-store `connect` action (binds the primary link)
 * @returns the primary connect promise (resolves when the first heartbeat arrives)
 */
export async function listenForVehicles(
  connect: (options: ConnectOptions) => Promise<boolean>,
  opts: ListenOptions = {},
): Promise<boolean> {
  const basePort = opts.basePort ?? 14550;
  const extraPorts = opts.extraPorts ?? 3;

  // Background listeners first (they bind immediately and never block), so a
  // vehicle on any extra port is already being heard while the primary waits.
  for (let i = 1; i <= extraPorts; i++) {
    window.electronAPI?.addTransport?.({ type: 'udp', udpMode: 'listen', udpPort: basePort + i }).catch(() => undefined);
  }

  // Primary listener - resolves when the first vehicle's heartbeat arrives.
  return connect({ type: 'udp', udpMode: 'listen', udpPort: basePort });
}
