/**
 * @module client-errors
 * @description Error classes used by the DroneCAN client and its pending-
 * request registry. Kept in their own file to avoid circular imports between
 * `client.ts` and `client-pending.ts`.
 * @license GPL-3.0-only
 */

/** Thrown when a service call exhausts its retries without a response. */
export class TimeoutError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TimeoutError";
  }
}
