import { describe, it, expect, beforeEach, vi } from "vitest";
import type { StateStorage } from "zustand/middleware";

function makeMemoryStorage(): StateStorage & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (name) => data.get(name) ?? null,
    setItem: (name, value) => {
      data.set(name, value);
    },
    removeItem: (name) => {
      data.delete(name);
    },
  };
}

const memory = makeMemoryStorage();

vi.mock("@/lib/storage", () => ({
  indexedDBStorage: {
    storage: () => memory,
  },
}));

// Import AFTER the mock so the factory picks up the in-memory backend.
import { createPersistentStore } from "@/lib/stores/create-persistent-store";

type Hydratable = { persist: { hasHydrated: () => boolean } };

function waitForHydration(store: Hydratable): Promise<void> {
  return new Promise((resolve) => {
    if (store.persist.hasHydrated()) {
      resolve();
      return;
    }
    // Simple poll — hydration is async but resolves within a microtask when the
    // storage backend is synchronous.
    const start = Date.now();
    const tick = () => {
      if (store.persist.hasHydrated() || Date.now() - start > 500) {
        resolve();
        return;
      }
      setTimeout(tick, 4);
    };
    tick();
  });
}

interface CounterState {
  value: number;
  label: string;
  set: (v: number) => void;
}

describe("createPersistentStore", () => {
  beforeEach(() => {
    memory.data.clear();
  });

  it("persists state to the provided storage backend", async () => {
    const useStore = createPersistentStore<CounterState>({
      name: "test:counter-basic",
      version: 1,
      initializer: (set) => ({
        value: 0,
        label: "init",
        set: (v) => set({ value: v }),
      }),
    });

    await waitForHydration(useStore);
    useStore.getState().set(7);

    // Zustand writes the persisted payload synchronously through the backend.
    // The in-memory StateStorage has no async gap.
    const raw = memory.data.get("test:counter-basic");
    expect(raw).toBeDefined();
    const parsed = JSON.parse(raw as string) as { state: { value: number }; version: number };
    expect(parsed.state.value).toBe(7);
    expect(parsed.version).toBe(1);
  });

  it("rehydrates previously persisted state on next store creation", async () => {
    memory.data.set(
      "test:counter-rehydrate",
      JSON.stringify({ state: { value: 42, label: "saved" }, version: 1 }),
    );

    const useStore = createPersistentStore<CounterState>({
      name: "test:counter-rehydrate",
      version: 1,
      initializer: (set) => ({
        value: 0,
        label: "init",
        set: (v) => set({ value: v }),
      }),
    });

    await waitForHydration(useStore);
    expect(useStore.getState().value).toBe(42);
    expect(useStore.getState().label).toBe("saved");
  });

  it("runs the legacy cascade migrate fn with (persisted, version)", async () => {
    memory.data.set(
      "test:counter-migrate-cascade",
      JSON.stringify({ state: { value: 1 }, version: 0 }),
    );
    const migrate = vi.fn((persisted: unknown, version: number) => {
      const s = persisted as Record<string, unknown>;
      // v1 added a label field. Return a fresh object so vi.fn's recorded
      // argument snapshot stays non-mutated.
      if (version < 1) {
        return { ...s, label: "migrated" } as unknown as CounterState;
      }
      return s as unknown as CounterState;
    });

    const useStore = createPersistentStore<CounterState>({
      name: "test:counter-migrate-cascade",
      version: 1,
      migrate,
      initializer: (set) => ({
        value: 0,
        label: "init",
        set: (v) => set({ value: v }),
      }),
    });

    await waitForHydration(useStore);
    expect(migrate).toHaveBeenCalledWith({ value: 1 }, 0);
    expect(useStore.getState().label).toBe("migrated");
    expect(useStore.getState().value).toBe(1);
  });

  it("composes a stepwise migrations dict into a cascade", async () => {
    memory.data.set(
      "test:counter-migrations",
      JSON.stringify({ state: { value: 1 }, version: 0 }),
    );

    const useStore = createPersistentStore<CounterState>({
      name: "test:counter-migrations",
      version: 3,
      migrations: {
        1: (prev) => ({ ...prev, label: "v1" }),
        2: (prev) => ({ ...prev, value: (prev.value as number) * 10 }),
        3: (prev) => ({ ...prev, label: `${prev.label as string}/v3` }),
      },
      initializer: (set) => ({
        value: 0,
        label: "init",
        set: (v) => set({ value: v }),
      }),
    });

    await waitForHydration(useStore);
    expect(useStore.getState().value).toBe(10);
    expect(useStore.getState().label).toBe("v1/v3");
  });

  it("skips migrations whose target is <= persisted version", async () => {
    memory.data.set(
      "test:counter-migrations-partial",
      JSON.stringify({ state: { value: 5, label: "from-v1" }, version: 1 }),
    );

    const v1 = vi.fn((prev: Record<string, unknown>) => ({ ...prev, label: "v1" }));
    const v2 = vi.fn((prev: Record<string, unknown>) => ({ ...prev, value: (prev.value as number) * 2 }));

    const useStore = createPersistentStore<CounterState>({
      name: "test:counter-migrations-partial",
      version: 2,
      migrations: { 1: v1, 2: v2 },
      initializer: (set) => ({
        value: 0,
        label: "init",
        set: (v) => set({ value: v }),
      }),
    });

    await waitForHydration(useStore);
    expect(v1).not.toHaveBeenCalled();
    expect(v2).toHaveBeenCalledTimes(1);
    expect(useStore.getState().value).toBe(10);
    expect(useStore.getState().label).toBe("from-v1");
  });

  it("prefers `migrate` over `migrations` when both are supplied", async () => {
    memory.data.set(
      "test:counter-both",
      JSON.stringify({ state: { value: 1 }, version: 0 }),
    );
    const migrate = vi.fn((persisted: unknown) => {
      const s = persisted as Record<string, unknown>;
      return { ...s, label: "from-cascade" } as unknown as CounterState;
    });
    const stepwise = vi.fn((prev: Record<string, unknown>) => ({ ...prev, label: "from-stepwise" }));

    const useStore = createPersistentStore<CounterState>({
      name: "test:counter-both",
      version: 1,
      migrate,
      migrations: { 1: stepwise },
      initializer: (set) => ({
        value: 0,
        label: "init",
        set: (v) => set({ value: v }),
      }),
    });

    await waitForHydration(useStore);
    expect(migrate).toHaveBeenCalledTimes(1);
    expect(stepwise).not.toHaveBeenCalled();
    expect(useStore.getState().label).toBe("from-cascade");
  });

  it("calls onRehydrate with the hydrated state", async () => {
    memory.data.set(
      "test:counter-rehydrate-cb",
      JSON.stringify({ state: { value: 99, label: "cb" }, version: 1 }),
    );
    const onRehydrate = vi.fn();

    const useStore = createPersistentStore<CounterState>({
      name: "test:counter-rehydrate-cb",
      version: 1,
      onRehydrate,
      initializer: (set) => ({
        value: 0,
        label: "init",
        set: (v) => set({ value: v }),
      }),
    });

    await waitForHydration(useStore);
    expect(onRehydrate).toHaveBeenCalledTimes(1);
    const [state] = onRehydrate.mock.calls[0];
    expect((state as CounterState).value).toBe(99);
  });

  it("respects partialize when persisting", async () => {
    const useStore = createPersistentStore<CounterState, Pick<CounterState, "value">>({
      name: "test:counter-partialize",
      version: 1,
      partialize: (s) => ({ value: s.value }),
      initializer: (set) => ({
        value: 3,
        label: "not-persisted",
        set: (v) => set({ value: v }),
      }),
    });

    await waitForHydration(useStore);
    useStore.getState().set(11);

    const raw = memory.data.get("test:counter-partialize");
    expect(raw).toBeDefined();
    const parsed = JSON.parse(raw as string) as { state: Record<string, unknown> };
    expect(parsed.state.value).toBe(11);
    expect(parsed.state.label).toBeUndefined();
  });

  it("accepts a custom storage override that bypasses the default backend", async () => {
    const custom = makeMemoryStorage();
    const useStore = createPersistentStore<CounterState>({
      name: "test:counter-storage-override",
      version: 1,
      storage: {
        getItem: (name) => {
          const raw = custom.data.get(name);
          return raw ? JSON.parse(raw) : null;
        },
        setItem: (name, value) => {
          custom.data.set(name, JSON.stringify(value));
        },
        removeItem: (name) => {
          custom.data.delete(name);
        },
      },
      initializer: (set) => ({
        value: 0,
        label: "init",
        set: (v) => set({ value: v }),
      }),
    });

    await waitForHydration(useStore);
    useStore.getState().set(25);

    expect(memory.data.get("test:counter-storage-override")).toBeUndefined();
    expect(custom.data.get("test:counter-storage-override")).toBeDefined();
  });
});
