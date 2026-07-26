import { beforeEach, describe, expect, it, vi } from "vitest";

import { safeLocalRead, safeLocalWrite, safeParse } from "@/lib/storage/safe-parse";

// happy-dom's Storage is partial. Inject a fresh in-memory shim per test so
// localStorage.clear / removeItem work and tests stay isolated.
function installFakeStorage() {
  const data = new Map<string, string>();
  const fake = {
    getItem: (k: string) => (data.has(k) ? data.get(k)! : null),
    setItem: (k: string, v: string) => {
      data.set(k, String(v));
    },
    removeItem: (k: string) => {
      data.delete(k);
    },
    clear: () => {
      data.clear();
    },
    key: (i: number) => Array.from(data.keys())[i] ?? null,
    get length() {
      return data.size;
    },
  };
  vi.stubGlobal("localStorage", fake);
  return fake;
}

describe("safeParse", () => {
  it("returns parsed JSON on valid input", () => {
    expect(safeParse('{"a":1}', null)).toEqual({ a: 1 });
    expect(safeParse("[1,2,3]", [])).toEqual([1, 2, 3]);
    expect(safeParse("true", false)).toBe(true);
    expect(safeParse('"hi"', "")).toBe("hi");
  });

  it("returns fallback on null/undefined/empty", () => {
    expect(safeParse(null, "default")).toBe("default");
    expect(safeParse(undefined, 42)).toBe(42);
    expect(safeParse("", { x: 1 })).toEqual({ x: 1 });
  });

  it("returns fallback on malformed JSON", () => {
    expect(safeParse("{broken", { ok: true })).toEqual({ ok: true });
    expect(safeParse("not json at all", [])).toEqual([]);
    expect(safeParse("{", "fallback")).toBe("fallback");
  });
});

describe("safeLocalRead", () => {
  let store: ReturnType<typeof installFakeStorage>;

  beforeEach(() => {
    store = installFakeStorage();
  });

  it("returns parsed value when key exists with valid JSON", () => {
    store.setItem("a", '{"x":1}');
    expect(safeLocalRead("a", { x: 0 })).toEqual({ x: 1 });
  });

  it("returns fallback when key is missing", () => {
    expect(safeLocalRead("missing", "default")).toBe("default");
  });

  it("returns fallback when stored data is corrupted", () => {
    store.setItem("corrupted", "{not json");
    expect(safeLocalRead("corrupted", [])).toEqual([]);
  });

  it("returns fallback when localStorage.getItem throws", () => {
    const throwing = {
      ...store,
      getItem: () => {
        throw new Error("SecurityError");
      },
    };
    vi.stubGlobal("localStorage", throwing);
    expect(safeLocalRead("any", "fallback")).toBe("fallback");
  });
});

describe("safeLocalWrite", () => {
  let store: ReturnType<typeof installFakeStorage>;

  beforeEach(() => {
    store = installFakeStorage();
  });

  it("returns true and writes serialized JSON", () => {
    expect(safeLocalWrite("k", { v: 1 })).toBe(true);
    expect(store.getItem("k")).toBe('{"v":1}');
  });

  it("returns false on quota exceeded", () => {
    const throwing = {
      ...store,
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
    };
    vi.stubGlobal("localStorage", throwing);
    expect(safeLocalWrite("k", { v: 1 })).toBe(false);
  });
});

describe("round-trip", () => {
  let store: ReturnType<typeof installFakeStorage>;

  beforeEach(() => {
    store = installFakeStorage();
  });

  it("write then read returns original value", () => {
    interface Marker { id: string; lat: number; lon: number }
    const data: Marker[] = [
      { id: "a", lat: 12.5, lon: 77.6 },
      { id: "b", lat: 13.0, lon: 78.0 },
    ];
    expect(safeLocalWrite("ms", data)).toBe(true);
    const read = safeLocalRead<Marker[]>("ms", []);
    expect(read).toEqual(data);
  });

  it("survives subsequent corruption of the stored value", () => {
    safeLocalWrite("z", { v: 1 });
    store.setItem("z", "{corrupted");
    expect(safeLocalRead("z", { v: 0 })).toEqual({ v: 0 });
  });
});
