/**
 * Defensive readers for the `unknown` args every plugin RPC handler
 * receives from the sandboxed iframe. Shared across the handler modules
 * so each split file (index/control/cloud/events) parses args the same way.
 *
 * @module plugins/handlers/args
 * @license GPL-3.0-only
 */

/** Coerce an untrusted value to a record; non-objects become `{}`. */
export function asRecord(args: unknown): Record<string, unknown> {
  return args && typeof args === "object"
    ? (args as Record<string, unknown>)
    : {};
}

/** Read a string field, or `undefined` when missing / not a string. */
export function readString(args: unknown, key: string): string | undefined {
  const v = asRecord(args)[key];
  return typeof v === "string" ? v : undefined;
}

/** Read a nested record field, or `undefined` when missing / not an object. */
export function readRecord(
  args: unknown,
  key: string,
): Record<string, unknown> | undefined {
  const v = asRecord(args)[key];
  return v && typeof v === "object" ? (v as Record<string, unknown>) : undefined;
}
