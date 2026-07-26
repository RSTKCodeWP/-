/**
 * Single source of truth for the running build version, read from
 * package.json at build time. Used to stamp diagnostic exports (e.g. the
 * flash log header) so a downloaded log is self-describing.
 *
 * @module app-version
 */
import pkg from "../../package.json";

export const APP_VERSION: string = (pkg as { version?: string }).version ?? "0.0.0";
