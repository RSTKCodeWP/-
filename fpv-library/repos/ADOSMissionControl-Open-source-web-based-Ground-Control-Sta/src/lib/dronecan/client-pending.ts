/**
 * @module client-pending
 * @description Request-correlation registry for the DroneCAN service client.
 * Each outbound request claims a (srcNodeId, dstNodeId, dataTypeId, transferId)
 * tuple, registers a deferred Promise plus a timeout, and waits for a response
 * frame that matches the same tuple. Separated from `client.ts` to keep that
 * file under the 500-LOC hard rule.
 * @license GPL-3.0-only
 */

import { TimeoutError } from "./client-errors";

/** Unique tuple identifying a pending service request. */
export interface PendingKey {
  /** Node we asked. Equals the response frame's source node. */
  srcNodeId: number;
  /** The self node ID at the time we asked. Equals the response's dest. */
  dstNodeId: number;
  /** Data type ID of the service. */
  dataTypeId: number;
  /** Transfer ID we claimed. */
  transferId: number;
}

interface PendingEntry {
  resolve(payload: Uint8Array): void;
  reject(err: Error): void;
  timer: ReturnType<typeof setTimeout>;
}

function keyToString(k: PendingKey): string {
  return `${k.srcNodeId}:${k.dstNodeId}:${k.dataTypeId}:${k.transferId}`;
}

/** In-memory map of pending requests. */
export class PendingRegistry {
  private readonly entries = new Map<string, PendingEntry>();

  /**
   * Register a pending request. The returned Promise resolves with the
   * response payload when {@link resolve} is called for the same key, or
   * rejects with a `TimeoutError` after `timeoutMs`.
   */
  register(key: PendingKey, timeoutMs: number): Promise<Uint8Array> {
    const stringKey = keyToString(key);
    return new Promise<Uint8Array>((resolveOuter, rejectOuter) => {
      const timer = setTimeout(() => {
        if (this.entries.delete(stringKey)) {
          rejectOuter(
            new TimeoutError(
              `service request timed out: type=${key.dataTypeId} node=${key.srcNodeId} tid=${key.transferId}`,
            ),
          );
        }
      }, timeoutMs);
      const entry: PendingEntry = {
        resolve: (payload) => {
          clearTimeout(timer);
          resolveOuter(payload);
        },
        reject: (err) => {
          clearTimeout(timer);
          rejectOuter(err);
        },
        timer,
      };
      this.entries.set(stringKey, entry);
    });
  }

  /** Resolve a pending request keyed by the given tuple. */
  resolve(key: PendingKey, payload: Uint8Array): boolean {
    const stringKey = keyToString(key);
    const entry = this.entries.get(stringKey);
    if (!entry) return false;
    this.entries.delete(stringKey);
    entry.resolve(new Uint8Array(payload));
    return true;
  }

  /** Drop a registration without resolving or rejecting. */
  discard(key: PendingKey): void {
    const stringKey = keyToString(key);
    const entry = this.entries.get(stringKey);
    if (!entry) return;
    clearTimeout(entry.timer);
    this.entries.delete(stringKey);
  }

  /** Reject every pending request with the given error. */
  rejectAll(err: Error): void {
    for (const entry of this.entries.values()) {
      clearTimeout(entry.timer);
      entry.reject(err);
    }
    this.entries.clear();
  }

  /** Diagnostic: how many requests are outstanding. */
  get size(): number {
    return this.entries.size;
  }
}
