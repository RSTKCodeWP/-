/**
 * @module create-persistent-store
 * @description Factory for Zustand stores with IndexedDB persistence.
 * Centralizes the `persist` + `createJSONStorage` + `indexedDBStorage`
 * boilerplate that roughly half a dozen stores in the GCS reimplement.
 *
 * Supports two migration styles:
 *
 * - Cascade: a single `migrate(persisted, version) => state` function with
 *   internal version checks. This matches what existing stores already use
 *   and lets them adopt the factory with zero rewriting of their migration
 *   logic.
 *
 * - Stepwise: `migrations: { [targetVersion]: (prev) => next }`. Each entry
 *   transforms the shape produced by the previous version into the target
 *   version. The factory composes them into a cascade internally. Prefer
 *   this form for new stores.
 *
 * If both are supplied, `migrate` wins.
 *
 * @license GPL-3.0-only
 */

import {
  create,
  type Mutate,
  type StateCreator,
  type StoreApi,
  type UseBoundStore,
} from "zustand";
import {
  persist,
  createJSONStorage,
  type PersistOptions,
  type PersistStorage,
} from "zustand/middleware";
import { indexedDBStorage } from "@/lib/storage";

/**
 * Return type of `createPersistentStore`. Same shape as
 * `create<T>()(persist(...))` — includes the `persist` store mutator so
 * callers can access `.persist.hasHydrated()`, `.persist.rehydrate()`, etc.
 */
export type PersistentStore<T, PersistedT = T> = UseBoundStore<
  Mutate<StoreApi<T>, [["zustand/persist", PersistedT]]>
>;

/**
 * Legacy cascade migrate fn, matching the shape of Zustand's
 * `PersistOptions.migrate`. Called with the raw persisted payload (which
 * reflects the previous `partialize` output when one was configured).
 */
export type MigrateFn<PersistedT> = (
  persisted: unknown,
  version: number,
) => PersistedT;

/**
 * Stepwise migrations. Keys are the target schema version; values transform
 * the shape produced by the previous version. Non-contiguous keys are fine —
 * any key strictly greater than the persisted version is applied, in order.
 */
export type MigrationsMap = Record<
  number,
  (prev: Record<string, unknown>) => Record<string, unknown>
>;

export interface CreatePersistentStoreOptions<T, PersistedT = T> {
  /**
   * Persist key in IndexedDB. Conventionally prefixed with `altcmd:`.
   * Never change for a deployed store — doing so orphans user data.
   */
  name: string;
  /**
   * Schema version. Bump when the persisted shape changes, and supply a
   * `migrate` or `migrations` to carry existing data forward.
   */
  version: number;
  /** Zustand state creator (state + actions), as you would pass to `persist()`. */
  initializer: StateCreator<T, [], [["zustand/persist", PersistedT]]>;
  /**
   * Cascade migrate function. Use when migrating an existing store to the
   * factory without rewriting its version checks.
   */
  migrate?: MigrateFn<PersistedT>;
  /**
   * Stepwise migrations dict. Composed into a cascade internally. Prefer
   * this for new stores.
   */
  migrations?: MigrationsMap;
  /** Subset of state to persist. Same semantics as Zustand's `persist.partialize`. */
  partialize?: (state: T) => PersistedT;
  /**
   * Called after rehydration completes. `state` is undefined on first load
   * (no prior persisted data). `error` is non-null if deserialization failed.
   */
  onRehydrate?: (state: T | undefined, error?: unknown) => void;
  /**
   * Override the storage backend. Defaults to IndexedDB via
   * `indexedDBStorage` from `@/lib/storage`. Tests can inject a mock here.
   */
  storage?: PersistStorage<PersistedT>;
  /** Defer hydration (SSR, deferred load). */
  skipHydration?: boolean;
}

/**
 * Compose a stepwise `migrations` map into a cascade `migrate` fn. Applies
 * every migration whose key is strictly greater than `fromVersion`, in
 * ascending key order.
 */
function composeMigrations<PersistedT>(migrations: MigrationsMap): MigrateFn<PersistedT> {
  const targets = Object.keys(migrations)
    .map((k) => Number(k))
    .sort((a, b) => a - b);
  return (persisted, fromVersion) => {
    let state = (persisted ?? {}) as Record<string, unknown>;
    for (const target of targets) {
      if (target > fromVersion) {
        state = migrations[target](state);
      }
    }
    return state as unknown as PersistedT;
  };
}

/**
 * Create a Zustand store persisted to IndexedDB under the given name. The
 * returned hook has the same `UseBoundStore<StoreApi<T>>` shape as
 * `create<T>()(persist(...))`, so consumers need no import changes.
 *
 * @example
 * export const useMyStore = createPersistentStore<State>({
 *   name: "altcmd:my-store",
 *   version: 1,
 *   initializer: (set) => ({
 *     value: 0,
 *     set: (v: number) => set({ value: v }),
 *   }),
 * });
 */
export function createPersistentStore<T, PersistedT = T>(
  options: CreatePersistentStoreOptions<T, PersistedT>,
): PersistentStore<T, PersistedT> {
  const effectiveMigrate: MigrateFn<PersistedT> | undefined =
    options.migrate ??
    (options.migrations ? composeMigrations<PersistedT>(options.migrations) : undefined);

  const persistOptions: PersistOptions<T, PersistedT> = {
    name: options.name,
    version: options.version,
    storage:
      options.storage ??
      (createJSONStorage(indexedDBStorage.storage) as PersistStorage<PersistedT>),
  };

  if (effectiveMigrate) {
    persistOptions.migrate = effectiveMigrate;
  }
  if (options.partialize) {
    persistOptions.partialize = options.partialize;
  }
  if (options.skipHydration) {
    persistOptions.skipHydration = options.skipHydration;
  }
  if (options.onRehydrate) {
    const cb = options.onRehydrate;
    persistOptions.onRehydrateStorage = () => (state, error) => cb(state, error);
  }

  return create<T>()(persist(options.initializer, persistOptions));
}
