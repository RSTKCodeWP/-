/**
 * @module storage/safe-parse
 * @description Helpers for reading and parsing localStorage without crashing
 * on corrupted or missing data. Use these instead of bare
 * `JSON.parse(localStorage.getItem(key))`.
 * @license GPL-3.0-only
 */

/**
 * Try to parse `raw` as JSON. Returns `fallback` on null, undefined,
 * empty string, or any parse failure.
 */
export function safeParse<T>(raw: string | null | undefined, fallback: T): T {
  if (raw === null || raw === undefined || raw === "") return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

/**
 * Read `key` from localStorage and parse as JSON. SSR-safe (returns
 * `fallback` when `window` is undefined). Returns `fallback` on missing
 * key, corrupted data, or any storage access failure (e.g., SecurityError
 * in private mode).
 */
export function safeLocalRead<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    return safeParse(window.localStorage.getItem(key), fallback);
  } catch {
    return fallback;
  }
}

/**
 * Serialize `value` to JSON and write to localStorage. Returns false on
 * storage quota exceeded, security error, or any other failure. Never
 * throws.
 */
export function safeLocalWrite<T>(key: string, value: T): boolean {
  if (typeof window === "undefined") return false;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}
