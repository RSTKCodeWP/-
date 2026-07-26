/**
 * @module transfer-id
 * @description 5-bit transfer ID rotator. DroneCAN tracks one counter per
 * (target node, data type, kind) tuple. Each new outbound transfer claims the
 * next counter value modulo 32. Inbound parsers compare against the same
 * rotation to detect dropped or duplicate transfers.
 * @license GPL-3.0-only
 */

export type TransferKind = "msg" | "req" | "resp";

interface Key {
  targetNodeId: number;
  dataTypeId: number;
  kind: TransferKind;
}

function makeKey(k: Key): string {
  return `${k.kind}:${k.targetNodeId}:${k.dataTypeId}`;
}

/**
 * Per-key 5-bit transfer ID allocator. Thread-safe under the assumption that
 * a single JavaScript event loop owns the instance (no `Atomics`).
 */
export class TransferIdAllocator {
  private readonly counters = new Map<string, number>();

  /**
   * Return the next transfer ID for the given key and advance the counter.
   * IDs cycle 0..31 modulo 32.
   */
  next(key: Key): number {
    const k = makeKey(key);
    const current = this.counters.get(k) ?? 0;
    const value = current & 0x1f;
    this.counters.set(k, (current + 1) & 0x1f);
    return value;
  }

  /** Peek the next ID without advancing. */
  peek(key: Key): number {
    const k = makeKey(key);
    return (this.counters.get(k) ?? 0) & 0x1f;
  }

  /** Clear all counters. */
  reset(): void {
    this.counters.clear();
  }
}
