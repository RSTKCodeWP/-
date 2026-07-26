/**
 * @module agent/local-pair/errors
 * @description Structured error classes for the local-first pair flow.
 * Kept in their own module so the credential-exchange helpers can throw
 * them without a runtime dependency on the network code.
 * @license GPL-3.0-only
 */

export class AgentAlreadyPairedError extends Error {
  constructor(message?: string) {
    super(message || "Agent is already paired. Unpair from the agent first.");
    this.name = "AgentAlreadyPairedError";
  }
}

/** Structured error class for pair-client failures. The ``code``
 * field maps to an i18n key under ``command.addNode.*`` so the
 * consuming component can render a translated message; the
 * ``message`` is kept as a dev-readable fallback. ``details`` is
 * spread into the translation interpolation context, so values are
 * filtered to ``string | number`` at construction. Object-valued
 * fields (which the agent shouldn't return but might in error
 * paths) are stringified to ``[object Object]``-resistant strings
 * via ``JSON.stringify`` so the t() call never blows up. */
export class PairClientError extends Error {
  readonly code: string;
  readonly details: Record<string, string | number>;
  constructor(
    code: string,
    message: string,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "PairClientError";
    this.code = code;
    const filtered: Record<string, string | number> = {};
    for (const [k, v] of Object.entries(details)) {
      if (typeof v === "string" || typeof v === "number") {
        filtered[k] = v;
      } else if (v == null) {
        filtered[k] = "";
      } else {
        try {
          filtered[k] = JSON.stringify(v);
        } catch {
          filtered[k] = String(v);
        }
      }
    }
    this.details = filtered;
  }
}
