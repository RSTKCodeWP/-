/**
 * @module client-subscriptions
 * @description Per-source-node listener registries for message broadcasts
 * decoded by the DroneCAN client. Pulled out of `client.ts` to keep that
 * file under the 500 LOC hard cap.
 *
 * Each subscription is keyed by the source node id (7-bit, 1..127). The
 * registry exposes `subscribe`, `unsubscribe`, and a fan-out `emit` that
 * isolates listener errors so one bad callback can never disrupt the
 * decoder loop.
 *
 * @license GPL-3.0-only
 */

/** Registry of per-node listeners for a single decoded broadcast type. */
export class NodeListenerRegistry<T> {
  private readonly listeners = new Map<number, Array<(value: T) => void>>();

  /** Add a listener for `nodeId`. Returns an unsubscribe function. */
  subscribe(nodeId: number, cb: (value: T) => void): () => void {
    const key = nodeId & 0x7f;
    let list = this.listeners.get(key);
    if (!list) {
      list = [];
      this.listeners.set(key, list);
    }
    list.push(cb);
    return () => {
      const arr = this.listeners.get(key);
      if (!arr) return;
      const i = arr.indexOf(cb);
      if (i >= 0) arr.splice(i, 1);
      if (arr.length === 0) this.listeners.delete(key);
    };
  }

  /** Fire all callbacks for `nodeId`, isolating listener errors. */
  emit(nodeId: number, value: T): void {
    const list = this.listeners.get(nodeId & 0x7f);
    if (!list) return;
    for (const l of list.slice()) {
      try {
        l(value);
      } catch {
        // listener errors are isolated
      }
    }
  }

  /** Drop every listener. Used on `stop`. */
  clear(): void {
    this.listeners.clear();
  }
}
