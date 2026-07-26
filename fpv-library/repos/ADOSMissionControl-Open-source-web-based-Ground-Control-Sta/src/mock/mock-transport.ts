/**
 * Minimal Transport stub for demo mode.
 *
 * Always reports connected, all I/O methods are no-ops.
 * on()/off() are no-ops so DroneManager's close handler never fires.
 *
 * @license GPL-3.0-only
 */

import type { Transport } from "@/lib/protocol/types";

export class MockTransport implements Transport {
  readonly type = "websocket" as const;

  get isConnected(): boolean {
    return true;
  }

  async connect(): Promise<void> {
    // no-op
  }

  async disconnect(): Promise<void> {
    // no-op
  }

  send(): void {
    // no-op
  }

  on(): void {
    // no-op — prevents DroneManager close handler from registering
  }

  off(): void {
    // no-op
  }
}
