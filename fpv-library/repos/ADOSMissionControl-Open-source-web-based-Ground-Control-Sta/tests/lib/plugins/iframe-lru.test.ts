import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { IframeLRU, type MountedIframe } from "@/lib/plugins/iframe-lru";
import type { PluginSlotName } from "@/lib/plugins/types";

interface BuildOptions {
  id: string;
  deviceId?: string;
  slot?: PluginSlotName;
  lastFocusedAt: number;
}

function buildEntry(
  opts: BuildOptions,
): MountedIframe & { unmount: ReturnType<typeof vi.fn> } {
  const unmount = vi.fn();
  return {
    pluginInstallId: opts.id,
    deviceId: opts.deviceId ?? "drone-a",
    slot: opts.slot ?? "node.detail.tab",
    lastFocusedAt: opts.lastFocusedAt,
    unmount,
  };
}

describe("IframeLRU.add", () => {
  let infoSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    infoSpy = vi.spyOn(console, "info").mockImplementation(() => {});
  });

  afterEach(() => {
    infoSpy.mockRestore();
  });

  it("accepts entries up to capacity without evicting", () => {
    const lru = new IframeLRU(8);
    const entries = Array.from({ length: 8 }, (_, i) =>
      buildEntry({ id: `p${i}`, lastFocusedAt: 1000 + i }),
    );
    for (const e of entries) lru.add(e);

    expect(lru.list()).toHaveLength(8);
    for (const e of entries) expect(e.unmount).not.toHaveBeenCalled();
    expect(infoSpy).not.toHaveBeenCalled();
  });

  it("evicts the least-recently-focused entry on the 9th add", () => {
    const lru = new IframeLRU(8);
    const entries = Array.from({ length: 8 }, (_, i) =>
      buildEntry({ id: `p${i}`, lastFocusedAt: 1000 + i }),
    );
    for (const e of entries) lru.add(e);

    const ninth = buildEntry({ id: "p8", lastFocusedAt: 2000 });
    lru.add(ninth);

    // p0 has the lowest lastFocusedAt and should be evicted.
    expect(entries[0]!.unmount).toHaveBeenCalledTimes(1);
    for (let i = 1; i < 8; i++) {
      expect(entries[i]!.unmount).not.toHaveBeenCalled();
    }
    expect(ninth.unmount).not.toHaveBeenCalled();

    const ids = lru.list().map((e) => e.pluginInstallId);
    expect(ids).not.toContain("p0");
    expect(ids).toContain("p8");
    expect(ids).toHaveLength(8);

    expect(infoSpy).toHaveBeenCalledWith("iframe_evicted", {
      pluginInstallId: "p0",
      slot: "node.detail.tab",
    });
  });

  it("eviction picks the lowest lastFocusedAt regardless of insertion order", () => {
    const lru = new IframeLRU(3);
    const a = buildEntry({ id: "a", lastFocusedAt: 500 });
    const b = buildEntry({ id: "b", lastFocusedAt: 100 }); // oldest
    const c = buildEntry({ id: "c", lastFocusedAt: 900 });
    lru.add(a);
    lru.add(b);
    lru.add(c);

    const d = buildEntry({ id: "d", lastFocusedAt: 1000 });
    lru.add(d);

    expect(b.unmount).toHaveBeenCalledTimes(1);
    expect(a.unmount).not.toHaveBeenCalled();
    expect(c.unmount).not.toHaveBeenCalled();
    expect(lru.list().map((e) => e.pluginInstallId)).toEqual(["a", "c", "d"]);
  });

  it("duplicate add is idempotent: refreshes metadata, no eviction, no double-mount", () => {
    const lru = new IframeLRU(2);
    const a = buildEntry({ id: "a", lastFocusedAt: 100 });
    const b = buildEntry({ id: "b", lastFocusedAt: 200 });
    lru.add(a);
    lru.add(b);

    const replay = buildEntry({ id: "a", lastFocusedAt: 999 });
    lru.add(replay);

    expect(a.unmount).not.toHaveBeenCalled();
    expect(replay.unmount).not.toHaveBeenCalled();
    expect(b.unmount).not.toHaveBeenCalled();
    expect(lru.list()).toHaveLength(2);

    const aEntry = lru.list().find((e) => e.pluginInstallId === "a");
    expect(aEntry?.lastFocusedAt).toBe(999);

    // Forcing the 3rd id must evict b (now the oldest at 200 vs a's 999).
    const c = buildEntry({ id: "c", lastFocusedAt: 1500 });
    lru.add(c);
    expect(b.unmount).toHaveBeenCalledTimes(1);
    expect(a.unmount).not.toHaveBeenCalled();
  });

  it("rejects a non-positive capacity", () => {
    expect(() => new IframeLRU(0)).toThrow(RangeError);
    expect(() => new IframeLRU(-1)).toThrow(RangeError);
    expect(() => new IframeLRU(Number.NaN)).toThrow(RangeError);
  });
});

describe("IframeLRU.touch", () => {
  let infoSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    infoSpy = vi.spyOn(console, "info").mockImplementation(() => {});
  });
  afterEach(() => infoSpy.mockRestore());

  it("reorders eviction so the touched entry survives", () => {
    const lru = new IframeLRU(3);
    const a = buildEntry({ id: "a", lastFocusedAt: 100 });
    const b = buildEntry({ id: "b", lastFocusedAt: 200 });
    const c = buildEntry({ id: "c", lastFocusedAt: 300 });
    lru.add(a);
    lru.add(b);
    lru.add(c);

    // Without touch, the 4th add would evict a (lowest).
    // Touch a to make b the new oldest.
    lru.touch("a", 999);
    const d = buildEntry({ id: "d", lastFocusedAt: 1500 });
    lru.add(d);

    expect(b.unmount).toHaveBeenCalledTimes(1);
    expect(a.unmount).not.toHaveBeenCalled();
    expect(c.unmount).not.toHaveBeenCalled();
    expect(lru.list().map((e) => e.pluginInstallId)).toEqual(["a", "c", "d"]);
  });

  it("is a no-op for unknown ids", () => {
    const lru = new IframeLRU(2);
    const a = buildEntry({ id: "a", lastFocusedAt: 100 });
    lru.add(a);

    expect(() => lru.touch("does-not-exist", 555)).not.toThrow();
    expect(lru.list()[0]!.lastFocusedAt).toBe(100);
  });
});

describe("IframeLRU.remove", () => {
  it("unmounts and drops the entry", () => {
    const lru = new IframeLRU(4);
    const a = buildEntry({ id: "a", lastFocusedAt: 100 });
    const b = buildEntry({ id: "b", lastFocusedAt: 200 });
    lru.add(a);
    lru.add(b);

    lru.remove("a");
    expect(a.unmount).toHaveBeenCalledTimes(1);
    expect(b.unmount).not.toHaveBeenCalled();
    expect(lru.list().map((e) => e.pluginInstallId)).toEqual(["b"]);
  });

  it("is a no-op for unknown ids", () => {
    const lru = new IframeLRU(4);
    expect(() => lru.remove("nope")).not.toThrow();
    expect(lru.list()).toHaveLength(0);
  });
});

describe("IframeLRU.clear", () => {
  it("unmounts all entries in reverse insertion order", () => {
    const lru = new IframeLRU(4);
    const order: string[] = [];
    const make = (id: string, ts: number) => {
      const entry = buildEntry({ id, lastFocusedAt: ts });
      entry.unmount.mockImplementation(() => {
        order.push(id);
      });
      return entry;
    };
    const a = make("a", 100);
    const b = make("b", 200);
    const c = make("c", 300);
    lru.add(a);
    lru.add(b);
    lru.add(c);

    lru.clear();

    expect(order).toEqual(["c", "b", "a"]);
    expect(lru.list()).toHaveLength(0);
  });

  it("continues unmounting siblings even if one throws", () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const lru = new IframeLRU(3);
    const a = buildEntry({ id: "a", lastFocusedAt: 100 });
    const b = buildEntry({ id: "b", lastFocusedAt: 200 });
    const c = buildEntry({ id: "c", lastFocusedAt: 300 });
    b.unmount.mockImplementation(() => {
      throw new Error("plugin panicked");
    });
    lru.add(a);
    lru.add(b);
    lru.add(c);

    expect(() => lru.clear()).not.toThrow();
    expect(a.unmount).toHaveBeenCalledTimes(1);
    expect(b.unmount).toHaveBeenCalledTimes(1);
    expect(c.unmount).toHaveBeenCalledTimes(1);
    expect(lru.list()).toHaveLength(0);
    expect(errSpy).toHaveBeenCalled();
    errSpy.mockRestore();
  });
});

describe("IframeLRU defaults", () => {
  it("defaults capacity to 8", () => {
    const lru = new IframeLRU();
    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => {});
    const entries = Array.from({ length: 9 }, (_, i) =>
      buildEntry({ id: `p${i}`, lastFocusedAt: i }),
    );
    for (const e of entries) lru.add(e);

    expect(lru.list()).toHaveLength(8);
    expect(entries[0]!.unmount).toHaveBeenCalledTimes(1);
    infoSpy.mockRestore();
  });
});
